"""Tool grader: compare the calls made to the expected calls.

`expected_calls` is a list of steps. A step is one call {"name", "arguments"} or a group
{"any_order": [calls]} for independent calls whose order doesn't matter. Steps must be
matched in order. Arguments listed in an expected call must match exactly (after JSON
parsing); extra arguments are allowed unless the call has "exact": true.

Extra calls are allowed only for tools listed in the task's `read_only`; any other
unexpected call (a write the task didn't ask for) fails the task. If the task has
`answer_contains`, the final reply must contain each string (case-insensitive).
Partial credit = share of expected calls matched before the first missing step.
"""


def call_matches(expected, actual):
    if expected["name"] != actual["name"] or actual.get("parse_error"):
        return False
    args = actual.get("arguments") or {}
    if expected.get("exact"):
        return args == expected.get("arguments", {})
    return all(args.get(k) == v for k, v in expected.get("arguments", {}).items())


def grade(task, row):
    calls = row.get("tool_calls") or []
    read_only = set(task.get("read_only", []))
    steps = task["expected_calls"]
    total = sum(len(s["any_order"]) if "any_order" in s else 1 for s in steps)

    i, matched, unexpected, complete = 0, 0, [], True
    for step in steps:
        remaining = list(step["any_order"]) if "any_order" in step else [step]
        while remaining and i < len(calls):
            call = calls[i]
            i += 1
            hit = next((e for e in remaining if call_matches(e, call)), None)
            if hit:
                remaining.remove(hit)
                matched += 1
            elif call["name"] not in read_only:
                unexpected.append(call["name"])
        if remaining:
            complete = False
            break
    unexpected += [c["name"] for c in calls[i:] if c["name"] not in read_only]

    content = (row.get("content") or "").lower()
    answer_ok = all(s.lower() in content for s in task.get("answer_contains", []))
    return {
        "correct": complete and not unexpected and answer_ok,
        "format_ok": not any(c.get("parse_error") for c in calls),
        "partial": matched / total if total else 1.0,
        "n_calls": len(calls),
        "unexpected_calls": unexpected or None,
        "answer_ok": answer_ok,
    }
