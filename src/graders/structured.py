"""Structured-output grader: JSON Schema validation plus field-level accuracy.

Fields listed in the task's `ignore_fields` (free text such as titles) must still
pass the schema but are left out of the accuracy score.
"""

import json
import re

from jsonschema import Draft202012Validator


def extract_json(text):
    if not text:
        return None
    fenced = re.findall(r"```(?:json)?\s*\n(.*?)```", text, re.DOTALL)
    candidate = fenced[-1] if fenced else text[text.find("{"): text.rfind("}") + 1]
    try:
        return json.loads(candidate)
    except (json.JSONDecodeError, ValueError):
        return None


def leaves(obj, prefix=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from leaves(v, f"{prefix}.{k}" if prefix else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from leaves(v, f"{prefix}[{i}]")
    else:
        yield prefix, obj


def grade(task, row):
    data = extract_json(row.get("content"))
    if data is None:
        return {"correct": False, "format_ok": False, "field_accuracy": 0.0, "schema_errors": None}
    errors = [e.message for e in Draft202012Validator(task["schema"]).iter_errors(data)]
    ignored = task.get("ignore_fields", [])  # free-text fields: schema-checked, not scored
    skip = lambda path: any(path == f or path.startswith((f + ".", f + "[")) for f in ignored)
    expected = {k: v for k, v in leaves(task["expected"]) if not skip(k)}
    got = dict(leaves(data))
    hits = sum(got.get(k) == v for k, v in expected.items())
    acc = hits / len(expected) if expected else 1.0
    return {"correct": not errors and acc == 1.0, "format_ok": True, "field_accuracy": acc,
            "schema_errors": errors[:5] or None}
