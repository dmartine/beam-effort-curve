"""One chat() call for both inference routes (Reflection API and HF router).

Every call returns a Completion that records which backend, provider, and
settings produced it, so result rows are traceable.
"""

import os
import time
from dataclasses import asdict, dataclass

from dotenv import load_dotenv
from openai import (
    APIConnectionError,
    APITimeoutError,
    InternalServerError,
    OpenAI,
    RateLimitError,
)

from beam_autoeffort import REASONING_PLACEHOLDER

load_dotenv()

EFFORTS = ["low", "medium", "high", "xhigh", "max"]

# 429 code when the organization's daily output-token allowance (1M in the beta) is used up
ALLOWANCE_EXHAUSTED = "daily_allowance_exhausted"

# Settings Reflection used for the model card evals. Kept fixed across runs.
TEMPERATURE = 0.7
TOP_P = 0.99


def _backends():
    return {
        "reflection": {
            "base_url": os.getenv("REFLECTION_BASE_URL", "https://api.reflection.ai/openai/v1"),
            "api_key": os.getenv("REFLECTION_API_KEY"),
            "model": os.getenv("REFLECTION_MODEL", "Beam-1.0-501B-A23B"),
        },
        "hf": {
            "base_url": "https://router.huggingface.co/v1",
            "api_key": os.getenv("HF_TOKEN"),
            "model": os.getenv("HF_MODEL_ID", "reflection/Beam-1.0-501B-A23B:baseten"),
        },
        "ollama": {
            "base_url": "https://ollama.com/v1",
            "api_key": os.getenv("OLLAMA_API_KEY"),
            "model": os.getenv("OLLAMA_MODEL", "beam"),
        },
    }


_clients = {}


def _client(backend):
    if backend not in _clients:
        cfg = _backends()[backend]
        if not cfg["api_key"]:
            raise RuntimeError(f"No API key set for backend '{backend}'. Fill in .env.")
        _clients[backend] = OpenAI(base_url=cfg["base_url"], api_key=cfg["api_key"], timeout=600)  # 32k tokens took at most ~410 s
    return _clients[backend]


@dataclass
class Completion:
    backend: str
    provider: str
    model: str
    effort: str | None
    max_tokens: int
    temperature: float = TEMPERATURE
    top_p: float = TOP_P
    model_version: str | None = None
    content: str | None = None
    reasoning: str | None = None
    tool_calls: list | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    reasoning_tokens: int | None = None
    finish_reason: str | None = None
    latency_s: float = 0.0
    error: str | None = None

    def to_dict(self):
        return asdict(self)


def _field(obj, *names):
    """Read a field the SDK may or may not model (vendor extras land in model_extra)."""
    if obj is None:
        return None
    extra = getattr(obj, "model_extra", None) or {}
    for name in names:
        value = getattr(obj, name, None)
        if value is None:
            value = extra.get(name)
        if value is not None:
            return value
    return None


def _provider(backend, model, response):
    reported = _field(response, "provider")
    if reported:
        return str(reported)
    if backend == "hf" and ":" in model:
        return model.rsplit(":", 1)[1]
    return backend


def chat(messages, effort, *, tools=None, backend=None, max_tokens=None, retries=6):
    """Send one chat completion. effort=None omits the parameter (to observe the default)."""
    backend = backend or os.getenv("BACKEND", "reflection")
    model = _backends()[backend]["model"]
    max_tokens = max_tokens or int(os.getenv("MAX_TOKENS", "32768"))

    # a raw body field, so values outside the SDK's typed list (xhigh, max) pass through
    kwargs = dict(model=model, messages=messages, temperature=TEMPERATURE, top_p=TOP_P, max_tokens=max_tokens,
                  extra_body={"reasoning_effort": effort} if effort is not None else None)
    if tools:
        kwargs["tools"] = tools

    def result(**fields):
        return Completion(**{"provider": backend, **fields}, backend=backend, model=model, effort=effort,
                          max_tokens=max_tokens)

    start = time.monotonic()
    for attempt in range(retries):
        try:
            response = _client(backend).chat.completions.create(**kwargs)
            break
        except (RateLimitError, APITimeoutError, APIConnectionError, InternalServerError) as e:
            # the daily output-token allowance won't come back by retrying (renews 00:00 UTC);
            # a timeout means up to 32k tokens generated and lost, so retry it only once
            if (attempt == retries - 1 or ALLOWANCE_EXHAUSTED in str(e)
                    or (isinstance(e, APITimeoutError) and attempt >= 1)):
                return result(latency_s=time.monotonic() - start, error=f"{type(e).__name__}: {e}")
            time.sleep(min(2 ** attempt * 2, 60))
        except Exception as e:  # bad request, auth, etc.: not worth retrying
            return result(latency_s=time.monotonic() - start, error=f"{type(e).__name__}: {e}")
    latency = time.monotonic() - start

    choice = response.choices[0]
    msg = choice.message
    usage = response.usage
    tool_calls = [{"id": tc.id, "name": tc.function.name, "arguments": tc.function.arguments}
                  for tc in msg.tool_calls] if msg.tool_calls else None

    return result(
        provider=_provider(backend, model, response),
        model_version=_field(response, "system_fingerprint", "model_version") or response.model,
        content=msg.content,
        reasoning=_field(msg, "reasoning_content", "reasoning"),
        tool_calls=tool_calls,
        prompt_tokens=getattr(usage, "prompt_tokens", None),
        completion_tokens=getattr(usage, "completion_tokens", None),
        reasoning_tokens=_field(getattr(usage, "completion_tokens_details", None), "reasoning_tokens"),
        finish_reason=choice.finish_reason,
        latency_s=round(latency, 3),
    )



def assistant_message(c, preserve_thinking=True):
    """The assistant turn to append before sending tool results back.

    Reflection's API requires `reasoning_content` on every earlier assistant message
    (400 if missing or empty). preserve_thinking=False is the ablation condition: it
    sends a fixed placeholder instead of the real reasoning.
    """
    m = {"role": "assistant", "content": c.content or "",
         "reasoning_content": (c.reasoning if preserve_thinking else None) or REASONING_PLACEHOLDER}
    if c.tool_calls:
        m["tool_calls"] = [
            {"id": tc["id"], "type": "function", "function": {"name": tc["name"], "arguments": tc["arguments"]}}
            for tc in c.tool_calls
        ]
    return m
