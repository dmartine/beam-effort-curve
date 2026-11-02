"""Smoke test: one prompt at each effort level (plus no effort), one tool call.

Answers the open questions: does effort change token use, which field holds
reasoning, does usage split out reasoning tokens, what is the default effort,
and what shape do tool calls come back in.

    python -m src.smoke_test                 # Reflection API
    python -m src.smoke_test --backend hf    # HF router cross-check
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .client import EFFORTS, chat

# A trivially easy prompt uses the same ~400 reasoning tokens at every level (checked 2026-10-21),
# so the effort check needs one that takes real casework.
PROMPT = (
    "Each face of a cube is painted one of 4 colors so that every pair of opposite faces gets two different colors. "
    "Two colorings are the same if one can be rotated to give the other. How many distinct colorings are there? "
    "Put the final answer in \\boxed{}."
)  # answer: 76 (math-012)

TOOL = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Current weather for a city.",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string"},
                "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]},
            },
            "required": ["city"],
        },
    },
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", default=None)
    parser.add_argument("--max-tokens", type=int, default=32768)
    parser.add_argument("--samples", type=int, default=2)
    args = parser.parse_args()

    out = Path("results") / f"smoke-{datetime.now(timezone.utc):%Y%m%dT%H%M%S}.jsonl"
    out.parent.mkdir(exist_ok=True)
    rows = []

    print(f"{'effort':<10}{'compl':>8}{'reason':>8}{'r_text':>8}{'finish':>9}{'secs':>8}  answer")
    for effort in [e for e in [None, *EFFORTS] for _ in range(args.samples)]:
        c = chat([{"role": "user", "content": PROMPT}], effort, backend=args.backend, max_tokens=args.max_tokens)
        rows.append({"kind": "effort", **c.to_dict()})
        if c.error:
            print(f"{effort or '(none)':<10} ERROR {c.error}")
            continue
        tail = (c.content or "").strip().replace("\n", " ")[-40:]
        r_len = len(c.reasoning) if c.reasoning else 0
        print(
            f"{effort or '(none)':<10}{c.completion_tokens or 0:>8}{c.reasoning_tokens or '-':>8}"
            f"{r_len:>8}{c.finish_reason or '-':>9}{c.latency_s:>8.1f}  ...{tail}"
        )

    c = chat(
        [{"role": "user", "content": "What's the weather in Lisbon, in celsius?"}],
        "low", tools=[TOOL], backend=args.backend, max_tokens=args.max_tokens,
    )
    rows.append({"kind": "tool", **c.to_dict()})
    print("\ntool call:", c.error or json.dumps(c.tool_calls), "| finish:", c.finish_reason)
    print("provider:", c.provider, "| model_version:", c.model_version)

    with out.open("w") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")
    print(f"\nraw rows written to {out}")
    print("Check: token counts should rise with effort; (none) tells you the default.")


if __name__ == "__main__":
    main()
