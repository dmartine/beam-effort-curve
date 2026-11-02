"""Math grader: exact match on the last \\boxed{...} answer."""

import re

from sympy import nsimplify, simplify
from sympy.core.sympify import SympifyError


def last_boxed(text):
    """Contents of the last \\boxed{...}, with nested braces handled."""
    if not text:
        return None
    start = text.rfind("\\boxed{")
    if start == -1:
        return None
    i, depth = start + len("\\boxed{"), 1
    for j in range(i, len(text)):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                return text[i:j]
    return None


def normalize(s):
    s = s.strip().strip("$").replace(",", "").replace("\\!", "").replace(" ", "")
    s = re.sub(r"^\\text\{(.*)\}$", r"\1", s)
    if re.fullmatch(r"-?\d+", s):
        s = str(int(s))  # "083" == "83"
    return s


def equal(a, b):
    if a == b:
        return True
    try:
        return simplify(nsimplify(a) - nsimplify(b)) == 0
    except (SympifyError, TypeError, ValueError, SyntaxError):
        return False


def grade(task, row):
    extracted = last_boxed(row.get("content"))
    if extracted is None:
        return {"correct": False, "format_ok": False, "extracted": None}
    return {"correct": equal(normalize(extracted), normalize(str(task["answer"]))), "format_ok": True, "extracted": extracted}
