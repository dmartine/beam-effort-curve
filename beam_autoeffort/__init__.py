"""Drop-in reasoning-effort picker for Beam on any OpenAI-compatible client.

    from openai import OpenAI
    from beam_autoeffort import auto_effort

    client = auto_effort(OpenAI(base_url="https://api.reflection.ai/openai/v1", api_key=...))
    r = client.chat.completions.create(model="Beam-1.0-501B-A23B", messages=[...], tools=[...])
    print(client.last_effort)  # the level that was used

Each request is sorted into a bucket using only what is visible before the call
(attached tools, a JSON response format, the prompt text), and gets the cheapest
effort level that matched the best accuracy for that bucket in the Beam Effort
Curve benchmark. An explicit `reasoning_effort` always wins.
"""

import json
from pathlib import Path

__all__ = ["auto_effort", "bucket", "load_policy", "with_reasoning"]

EFFORTS = ["low", "medium", "high", "xhigh", "max"]
POLICY_FILE = Path(__file__).with_name("policy.json")
REASONING_PLACEHOLDER = "(reasoning omitted)"  # accepted where the API requires the field


def load_policy(path=POLICY_FILE):
    return json.loads(Path(path).read_text())["policy"]


def _text(messages):
    parts = []
    for m in messages or []:
        content = m.get("content") if isinstance(m, dict) else getattr(m, "content", None)
        if isinstance(content, str):
            parts.append(content)
        elif isinstance(content, list):  # content parts
            parts += [p.get("text", "") for p in content if isinstance(p, dict)]
    return "\n".join(parts)


def bucket(request):
    """Bucket a request: a task dict (prompt/messages/tools) or chat.completions.create kwargs."""
    if request.get("tools"):
        return "tools"
    fmt = request.get("response_format") or {}
    if isinstance(fmt, dict) and fmt.get("type") in ("json_schema", "json_object"):
        return "structured"
    text = request.get("prompt") or _text(request.get("messages"))
    if "JSON Schema" in text or "Reply with JSON" in text:
        return "structured"
    if "```python" in text or text.lstrip().startswith("Write `") or "Write a class" in text:
        return "code"
    return "reasoning"


def with_reasoning(message):
    """Assistant turn to send back on the next call. Reflection's API requires
    `reasoning_content` on every earlier assistant message (400 without it), and the
    model reads it within a tool loop. Providers return it as `reasoning_content`
    (Reflection) or `reasoning` (Ollama); both accept `reasoning_content` back."""
    extra = getattr(message, "model_extra", None) or {}
    reasoning = next(filter(None, (getattr(message, k, None) or extra.get(k)
                                   for k in ("reasoning_content", "reasoning"))), None)
    m = {"role": "assistant", "content": message.content or "", "reasoning_content": reasoning or REASONING_PLACEHOLDER}
    if message.tool_calls:
        m["tool_calls"] = [{"id": tc.id, "type": "function",
                            "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                           for tc in message.tool_calls]
    return m


class _Completions:
    def __init__(self, owner, completions):
        self._owner, self._completions = owner, completions

    def create(self, **kwargs):
        extra = dict(kwargs.pop("extra_body", None) or {})
        explicit = kwargs.pop("reasoning_effort", None) or extra.get("reasoning_effort")
        effort = explicit or self._owner.policy.get(bucket(kwargs), self._owner.default)
        extra["reasoning_effort"] = effort
        self._owner.last_effort = effort
        return self._completions.create(extra_body=extra, **kwargs)

    def __getattr__(self, name):
        return getattr(self._completions, name)


class _Chat:
    def __init__(self, owner, chat):
        self.completions = _Completions(owner, chat.completions)
        self._chat = chat

    def __getattr__(self, name):
        return getattr(self._chat, name)


class _AutoEffortClient:
    def __init__(self, client, policy, default):
        self._client, self.policy, self.default, self.last_effort = client, policy, default, None
        self.chat = _Chat(self, client.chat)

    def __getattr__(self, name):
        return getattr(self._client, name)


def auto_effort(client, policy=None, default="medium"):
    """Wrap an OpenAI-compatible client so chat.completions.create picks reasoning_effort per request."""
    policy = policy or load_policy()
    unknown = {v for v in policy.values() if v not in EFFORTS} | ({default} - set(EFFORTS))
    if unknown:
        raise ValueError(f"unknown effort level(s): {unknown}")
    return _AutoEffortClient(client, policy, default)
