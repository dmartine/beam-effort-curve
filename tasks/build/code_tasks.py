"""Build tasks/code.jsonl. Each task ships a reference solution that must pass its
hidden tests, and a stub that must fail them, before the task is written out.

    python -m tasks.build.code_tasks
"""

import json
import re
from pathlib import Path

from src.graders import code as code_grader

SUFFIX = "\n\nReply with the complete implementation in a single ```python code block. Use only the standard library."
SOURCE = "written for this repo (2026-10); reference solution verified against the tests in tasks/build/code_tasks.py"
TASKS = []


def task(prompt, tests, reference, tier="core"):
    TASKS.append((prompt.strip(), tests.strip() + "\n", reference.strip() + "\n", tier))


task(
    """Write `parse_duration(s: str) -> int` that converts a duration like "1h30m", "2d 4h", "45s" or "1d2h3m4s" to seconds.
Units are d, h, m, s. Each unit may appear at most once and units must appear in that order (d before h before m before s).
Whitespace between parts is allowed. Raise ValueError for an empty string, an unknown unit, a repeated or out-of-order unit,
or a number without a unit.""",
    """
def test_basic():
    assert parse_duration("1h30m") == 5400
    assert parse_duration("45s") == 45
    assert parse_duration("1d2h3m4s") == 93784
    assert parse_duration("2d 4h") == 187200
    assert parse_duration("0s") == 0

def test_errors():
    for bad in ["", "1x", "30m1h", "1h1h", "10", "h", "1h 2"]:
        try:
            parse_duration(bad)
        except ValueError:
            continue
        raise AssertionError(bad)
""",
    """
import re

def parse_duration(s):
    s = s.strip()
    if not s:
        raise ValueError("empty")
    parts = re.findall(r"(\\d+)\\s*([a-z]?)\\s*", s)
    if "".join(re.findall(r"\\S", s)) != "".join(n + u for n, u in parts):
        raise ValueError(s)
    order, total, last = "dhms", 0, -1
    mult = {"d": 86400, "h": 3600, "m": 60, "s": 1}
    for n, u in parts:
        if u not in mult or order.index(u) <= last:
            raise ValueError(s)
        last = order.index(u)
        total += int(n) * mult[u]
    return total
""",
)

task(
    """Write `semver_compare(a: str, b: str) -> int` returning -1, 0 or 1 by Semantic Versioning 2.0.0 precedence.
Versions look like "1.2.3", "1.2.3-alpha.1" or "1.2.3-rc.1+build.5". Build metadata (after +) is ignored.
A version with a pre-release has lower precedence than the same version without one. Pre-release identifiers are compared
left to right: numeric identifiers numerically, alphanumeric ones in ASCII order, numeric lower than alphanumeric, and a
shorter set of identifiers is lower if all earlier ones are equal.""",
    """
def test_core():
    assert semver_compare("1.0.0", "2.0.0") == -1
    assert semver_compare("2.10.0", "2.9.0") == 1
    assert semver_compare("1.2.3", "1.2.3") == 0

def test_prerelease_order():
    chain = ["1.0.0-alpha", "1.0.0-alpha.1", "1.0.0-alpha.beta", "1.0.0-beta", "1.0.0-beta.2",
             "1.0.0-beta.11", "1.0.0-rc.1", "1.0.0"]
    for x, y in zip(chain, chain[1:]):
        assert semver_compare(x, y) == -1, (x, y)
        assert semver_compare(y, x) == 1, (y, x)

def test_build_ignored():
    assert semver_compare("1.0.0+build.1", "1.0.0+build.2") == 0
    assert semver_compare("1.0.0-rc.1+x", "1.0.0-rc.1") == 0
""",
    """
def semver_compare(a, b):
    def parse(v):
        v = v.split("+", 1)[0]
        core, _, pre = v.partition("-")
        return tuple(int(x) for x in core.split(".")), pre.split(".") if pre else []

    def ident_key(i):
        return (0, int(i), "") if i.isdigit() else (1, 0, i)

    (ca, pa), (cb, pb) = parse(a), parse(b)
    if ca != cb:
        return -1 if ca < cb else 1
    if not pa or not pb:
        return (not pa) - (not pb) if pa != pb else 0
    ka, kb = [ident_key(i) for i in pa], [ident_key(i) for i in pb]
    return (ka > kb) - (ka < kb)
""",
)

task(
    """Write `evaluate(expr: str) -> int` that evaluates an arithmetic expression with non-negative integer literals,
+, -, *, /, parentheses, unary minus and arbitrary spaces. * and / bind tighter than + and -, operators of equal precedence
are left-associative, and / is integer division that truncates toward zero (so 7 / -2 == -3). Do not use eval or exec.""",
    """
def test_precedence():
    assert evaluate("2 + 3 * 4") == 14
    assert evaluate("(2 + 3) * 4") == 20
    assert evaluate("10 - 4 - 3") == 3
    assert evaluate("100 / 10 / 5") == 2

def test_unary_and_truncation():
    assert evaluate("2 - -3") == 5
    assert evaluate("-(2 + 3) * 4") == -20
    assert evaluate("7 / -2") == -3
    assert evaluate("-7 / 2") == -3
    assert evaluate("--4") == 4

def test_spaces_and_nesting():
    assert evaluate(" ((1+2) * (3 - (4/2))) ") == 3
""",
    """
def evaluate(expr):
    tokens = [c for c in expr.replace(" ", "")]
    pos = 0

    def peek():
        return tokens[pos] if pos < len(tokens) else None

    def take():
        nonlocal pos
        pos += 1
        return tokens[pos - 1]

    def expr_():
        v = term()
        while peek() in ("+", "-"):
            v = v + term() if take() == "+" else v - term()
        return v

    def term():
        v = unary()
        while peek() in ("*", "/"):
            if take() == "*":
                v *= unary()
            else:
                d = unary()
                q = abs(v) // abs(d)
                v = q if (v >= 0) == (d > 0) else -q
        return v

    def unary():
        if peek() == "-":
            take()
            return -unary()
        if peek() == "(":
            take()
            v = expr_()
            take()
            return v
        n = ""
        while peek() is not None and peek().isdigit():
            n += take()
        return int(n)

    return expr_()
""",
)

task(
    """Write `split_csv_line(line: str) -> list[str]` that splits one CSV line into fields. Fields are separated by commas.
A field may be wrapped in double quotes, in which case it can contain commas, and a doubled quote ("") inside it stands for
one quote character. Quotes inside an unquoted field are kept literally. An empty line is one empty field.
Raise ValueError if a quoted field is not closed or if a closing quote is followed by anything other than a comma or the
end of the line. Do not use the csv module.""",
    '''
def test_basic():
    assert split_csv_line("a,b,c") == ["a", "b", "c"]
    assert split_csv_line("") == [""]
    assert split_csv_line("a,,") == ["a", "", ""]

def test_quotes():
    assert split_csv_line('"a,b",c') == ["a,b", "c"]
    assert split_csv_line('"say ""hi""",x') == ['say "hi"', "x"]
    assert split_csv_line('""') == [""]
    assert split_csv_line('ab"c,d') == ['ab"c', "d"]

def test_errors():
    for bad in ['"abc', '"a"b,c']:
        try:
            split_csv_line(bad)
        except ValueError:
            continue
        raise AssertionError(bad)
''',
    """
def split_csv_line(line):
    fields, i, n = [], 0, len(line)
    while True:
        if i < n and line[i] == '"':
            i += 1
            buf = []
            while True:
                if i >= n:
                    raise ValueError("unclosed quote")
                if line[i] == '"':
                    if i + 1 < n and line[i + 1] == '"':
                        buf.append('"')
                        i += 2
                        continue
                    i += 1
                    break
                buf.append(line[i])
                i += 1
            if i < n and line[i] != ",":
                raise ValueError("text after closing quote")
            fields.append("".join(buf))
        else:
            j = line.find(",", i)
            j = n if j == -1 else j
            fields.append(line[i:j])
            i = j
        if i >= n:
            return fields
        i += 1
""",
)

task(
    """Write a class `TTLCache` with `__init__(self, ttl: float, clock)`, `set(self, key, value)` and `get(self, key, default=None)`.
`clock` is a zero-argument function returning the current time in seconds. An entry set at time t is visible while
clock() < t + ttl and gone from then on (get returns default). Setting an existing key replaces its value and restarts its
timer. Also implement `__len__` returning the number of entries that have not expired.""",
    """
class FakeClock:
    def __init__(self):
        self.t = 0.0
    def __call__(self):
        return self.t

def test_expiry():
    c = FakeClock()
    cache = TTLCache(10, c)
    cache.set("a", 1)
    c.t = 9.99
    assert cache.get("a") == 1
    c.t = 10
    assert cache.get("a") is None
    assert cache.get("a", "x") == "x"

def test_reset_and_len():
    c = FakeClock()
    cache = TTLCache(5, c)
    cache.set("a", 1)
    cache.set("b", 2)
    c.t = 4
    cache.set("a", 3)
    assert len(cache) == 2
    c.t = 6
    assert cache.get("a") == 3 and cache.get("b") is None
    assert len(cache) == 1
""",
    """
class TTLCache:
    def __init__(self, ttl, clock):
        self.ttl, self.clock, self.data = ttl, clock, {}

    def set(self, key, value):
        self.data[key] = (value, self.clock() + self.ttl)

    def get(self, key, default=None):
        item = self.data.get(key)
        if item is None or self.clock() >= item[1]:
            self.data.pop(key, None)
            return default
        return item[0]

    def __len__(self):
        now = self.clock()
        return sum(1 for _, exp in self.data.values() if now < exp)
""",
)

task(
    """Write `free_slots(busy: list[tuple[str, str]], day_start: str, day_end: str, min_minutes: int) -> list[tuple[str, str]]`.
Times are "HH:MM" strings. `busy` holds possibly overlapping, unsorted meeting intervals (start inclusive, end exclusive),
which may extend outside the day. Return the free intervals within [day_start, day_end) that last at least `min_minutes`,
sorted, as ("HH:MM", "HH:MM") tuples.""",
    """
def test_basic():
    busy = [("09:30", "10:00"), ("12:00", "13:00"), ("09:45", "10:30")]
    assert free_slots(busy, "09:00", "17:00", 30) == [("09:00", "09:30"), ("10:30", "12:00"), ("13:00", "17:00")]

def test_min_length_and_edges():
    busy = [("08:00", "09:10"), ("09:30", "16:50"), ("16:55", "18:00")]
    assert free_slots(busy, "09:00", "17:00", 15) == [("09:10", "09:30")]
    assert free_slots(busy, "09:00", "17:00", 25) == []

def test_empty():
    assert free_slots([], "09:00", "10:00", 60) == [("09:00", "10:00")]
""",
    """
def free_slots(busy, day_start, day_end, min_minutes):
    to_m = lambda s: int(s[:2]) * 60 + int(s[3:])
    fmt = lambda m: f"{m // 60:02d}:{m % 60:02d}"
    start, end = to_m(day_start), to_m(day_end)
    out, cur = [], start
    for s, e in sorted((to_m(a), to_m(b)) for a, b in busy):
        if s > cur and min(s, end) - cur >= min_minutes:
            out.append((fmt(cur), fmt(min(s, end))))
        cur = max(cur, e)
        if cur >= end:
            break
    if end - cur >= min_minutes:
        out.append((fmt(cur), fmt(end)))
    return out
""",
)

task(
    """Write `topo_order(deps: dict[str, list[str]]) -> list[str]`. `deps[x]` lists the prerequisites of x. Nodes that only
appear as prerequisites are also part of the graph. Return the lexicographically smallest ordering in which every node comes
after all of its prerequisites. Raise ValueError if there is a cycle.""",
    """
def test_order():
    assert topo_order({"b": ["a"], "c": ["a"], "d": ["b", "c"]}) == ["a", "b", "c", "d"]
    assert topo_order({"z": [], "a": ["z"], "m": []}) == ["m", "z", "a"]
    assert topo_order({}) == []

def test_implicit_nodes():
    assert topo_order({"x": ["q", "p"]}) == ["p", "q", "x"]

def test_cycle():
    try:
        topo_order({"a": ["b"], "b": ["c"], "c": ["a"]})
    except ValueError:
        return
    raise AssertionError("cycle not detected")
""",
    """
import heapq

def topo_order(deps):
    nodes = set(deps) | {p for ps in deps.values() for p in ps}
    indeg = {n: 0 for n in nodes}
    children = {n: [] for n in nodes}
    for n, ps in deps.items():
        for p in set(ps):
            indeg[n] += 1
            children[p].append(n)
    heap = [n for n in nodes if indeg[n] == 0]
    heapq.heapify(heap)
    out = []
    while heap:
        n = heapq.heappop(heap)
        out.append(n)
        for c in children[n]:
            indeg[c] -= 1
            if indeg[c] == 0:
                heapq.heappush(heap, c)
    if len(out) != len(nodes):
        raise ValueError("cycle")
    return out
""",
)

task(
    """Write `number_to_words(n: int) -> str` for 0 <= n < 1,000,000,000 in lowercase American English without "and".
Examples: 0 -> "zero", 21 -> "twenty-one", 105 -> "one hundred five", 1000 -> "one thousand",
1_000_021 -> "one million twenty-one", 999_999_999 -> "nine hundred ninety-nine million nine hundred ninety-nine thousand nine hundred ninety-nine".""",
    """
def test_words():
    cases = {0: "zero", 7: "seven", 13: "thirteen", 21: "twenty-one", 40: "forty", 105: "one hundred five",
             110: "one hundred ten", 1000: "one thousand", 1001: "one thousand one",
             12_345: "twelve thousand three hundred forty-five", 1_000_021: "one million twenty-one",
             200_000_000: "two hundred million",
             999_999_999: "nine hundred ninety-nine million nine hundred ninety-nine thousand nine hundred ninety-nine"}
    for n, w in cases.items():
        assert number_to_words(n) == w, (n, number_to_words(n))
""",
    """
ONES = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()

def _under_1000(n):
    words = []
    if n >= 100:
        words += [ONES[n // 100], "hundred"]
        n %= 100
    if n >= 20:
        words.append(TENS[n // 10] + (f"-{ONES[n % 10]}" if n % 10 else ""))
    elif n:
        words.append(ONES[n])
    return words

def number_to_words(n):
    if n == 0:
        return "zero"
    words = []
    for value, name in ((1_000_000, "million"), (1000, "thousand"), (1, "")):
        chunk, n = divmod(n, value)
        if chunk:
            words += _under_1000(chunk) + ([name] if name else [])
    return " ".join(words)
""",
)

task(
    """Write `rle_encode(s: str) -> str` and `rle_decode(s: str) -> str`. Encoding replaces each run of a repeated character
with the character followed by the run length, omitting the length when it is 1: "aaabcc" -> "a3bc2". Runs longer than 9
use multi-digit counts ("a" * 12 -> "a12"). The input to rle_encode must not contain digits; raise ValueError if it does.
rle_decode inverts rle_encode and raises ValueError if the string starts with a digit.""",
    """
def test_roundtrip():
    for s in ["", "a", "aaabcc", "abc", "z" * 12 + "y", "aabbaa"]:
        assert rle_decode(rle_encode(s)) == s

def test_format():
    assert rle_encode("aaabcc") == "a3bc2"
    assert rle_encode("a" * 12) == "a12"
    assert rle_decode("x10y") == "x" * 10 + "y"

def test_errors():
    for f, bad in [(rle_encode, "ab1"), (rle_decode, "3a")]:
        try:
            f(bad)
        except ValueError:
            continue
        raise AssertionError(bad)
""",
    """
import re
from itertools import groupby

def rle_encode(s):
    if any(c.isdigit() for c in s):
        raise ValueError("digits not allowed")
    return "".join(c + (str(n) if (n := len(list(g))) > 1 else "") for c, g in groupby(s))

def rle_decode(s):
    if s[:1].isdigit():
        raise ValueError("starts with digit")
    return "".join(c * int(n or 1) for c, n in re.findall(r"(\\D)(\\d*)", s))
""",
)

task(
    """Write `spiral(matrix: list[list[int]]) -> list[int]` returning the elements in clockwise spiral order starting at the
top-left. The matrix may be empty, a single row, a single column, or rectangular.""",
    """
def test_spiral():
    assert spiral([]) == []
    assert spiral([[1, 2, 3]]) == [1, 2, 3]
    assert spiral([[1], [2], [3]]) == [1, 2, 3]
    assert spiral([[1, 2], [3, 4]]) == [1, 2, 4, 3]
    assert spiral([[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12]]) == [1, 2, 3, 4, 8, 12, 11, 10, 9, 5, 6, 7]
    assert spiral([[1, 2, 3], [4, 5, 6], [7, 8, 9], [10, 11, 12]]) == [1, 2, 3, 6, 9, 12, 11, 10, 7, 4, 5, 8]
""",
    """
def spiral(matrix):
    out = []
    m = [row[:] for row in matrix]
    while m:
        out += m.pop(0)
        m = [list(r) for r in zip(*m)][::-1]
    return out
""",
)

task(
    """Write `lcs(a: str, b: str) -> str` returning a longest common subsequence of a and b. If several longest common
subsequences exist, return the lexicographically smallest one.""",
    """
def test_lcs():
    assert lcs("", "abc") == ""
    assert lcs("abcde", "ace") == "ace"
    assert lcs("ab", "ba") == "a"
    assert lcs("abcbdab", "bdcaba") == "bcab"
    assert lcs("xyz", "abc") == ""
    assert lcs("aaa", "aa") == "aa"
""",
    """
from functools import lru_cache

def lcs(a, b):
    @lru_cache(maxsize=None)
    def best(i, j):
        if i == len(a) or j == len(b):
            return ""
        if a[i] == b[j]:
            return a[i] + best(i + 1, j + 1)
        x, y = best(i + 1, j), best(i, j + 1)
        if len(x) != len(y):
            return x if len(x) > len(y) else y
        return min(x, y)
    return best(0, 0)
""",
)

task(
    """Write a class `SlidingWindowLimiter` with `__init__(self, limit: int, window: float)` and `allow(self, t: float) -> bool`.
`allow` is called with non-decreasing timestamps. It returns True and records the request if fewer than `limit` requests
were allowed in the half-open window (t - window, t]; otherwise it returns False and does not record anything.""",
    """
def test_limiter():
    rl = SlidingWindowLimiter(2, 10)
    assert rl.allow(0) is True
    assert rl.allow(1) is True
    assert rl.allow(5) is False
    assert rl.allow(9.99) is False
    assert rl.allow(10) is True   # request at 0 left the window (10-10, 10]
    assert rl.allow(10.5) is False
    assert rl.allow(11) is True
    assert rl.allow(11) is False

def test_rejections_not_recorded():
    rl = SlidingWindowLimiter(1, 5)
    assert rl.allow(0)
    for t in (1, 2, 3, 4):
        assert not rl.allow(t)
    assert rl.allow(5)
""",
    """
from collections import deque

class SlidingWindowLimiter:
    def __init__(self, limit, window):
        self.limit, self.window, self.q = limit, window, deque()

    def allow(self, t):
        while self.q and self.q[0] <= t - self.window:
            self.q.popleft()
        if len(self.q) < self.limit:
            self.q.append(t)
            return True
        return False
""",
)

task(
    """Write `add_business_days(date: str, n: int, holidays: set[str]) -> str`. Dates are "YYYY-MM-DD". Move n business days
forward (or backward if n is negative), where business days are Monday to Friday and not in `holidays`. If n is 0, return
the date unchanged even if it is not a business day.""",
    """
def test_forward():
    assert add_business_days("2026-10-23", 1, set()) == "2026-10-26"   # Fri -> Mon
    assert add_business_days("2026-10-21", 3, set()) == "2026-10-26"
    assert add_business_days("2026-12-24", 1, {"2026-12-25"}) == "2026-12-28"

def test_backward_and_zero():
    assert add_business_days("2026-10-26", -1, set()) == "2026-10-23"
    assert add_business_days("2026-01-02", -1, {"2026-01-01"}) == "2025-12-31"
    assert add_business_days("2026-10-24", 0, set()) == "2026-10-24"

def test_from_weekend():
    assert add_business_days("2026-10-24", 1, set()) == "2026-10-26"
""",
    """
from datetime import date, timedelta

def add_business_days(d, n, holidays):
    cur = date.fromisoformat(d)
    step = 1 if n > 0 else -1
    remaining = abs(n)
    while remaining:
        cur += timedelta(days=step)
        if cur.weekday() < 5 and cur.isoformat() not in holidays:
            remaining -= 1
    return cur.isoformat()
""",
)

task(
    """Write `flatten(obj) -> dict` that flattens nested dicts and lists into a single dict with dotted keys. List items use
their index as the key part. Empty dicts and empty lists are kept as values. Example:
{"a": {"b": 1, "c": [10, {"d": 2}]}, "e": {}} -> {"a.b": 1, "a.c.0": 10, "a.c.1.d": 2, "e": {}}.
A top-level value that is not a dict or list is returned as {"": value}.""",
    """
def test_flatten():
    assert flatten({"a": {"b": 1, "c": [10, {"d": 2}]}, "e": {}}) == {"a.b": 1, "a.c.0": 10, "a.c.1.d": 2, "e": {}}
    assert flatten({}) == {}
    assert flatten({"x": [], "y": None}) == {"x": [], "y": None}
    assert flatten([1, [2]]) == {"0": 1, "1.0": 2}
    assert flatten(5) == {"": 5}
""",
    """
def flatten(obj):
    out = {}

    def walk(value, prefix):
        items = value.items() if isinstance(value, dict) else enumerate(value) if isinstance(value, list) else None
        if items is None or not value:
            out[prefix] = value
            return
        for k, v in items:
            walk(v, f"{prefix}.{k}" if prefix else str(k))

    if isinstance(obj, (dict, list)) and not obj:
        return {}
    walk(obj, "")
    return out
""",
)

task(
    """Write `determinant(m: list[list[int]]) -> int` returning the exact determinant of a square integer matrix of size
0 to 10 (the determinant of the 0 by 0 matrix is 1). The result must be exact, so floating point is not acceptable.""",
    """
def test_det():
    assert determinant([]) == 1
    assert determinant([[7]]) == 7
    assert determinant([[1, 2], [3, 4]]) == -2
    assert determinant([[0, 1], [1, 0]]) == -1
    assert determinant([[2, 0, 0], [0, 3, 0], [0, 0, 4]]) == 24
    assert determinant([[1, 2, 3], [4, 5, 6], [7, 8, 9]]) == 0
    big = [[(i * 7 + j * 3) % 11 - 5 + (10**12 if i == j else 0) for j in range(10)] for i in range(10)]
    from fractions import Fraction
    def ref(a):
        a = [[Fraction(x) for x in r] for r in a]; n = len(a); d = Fraction(1)
        for c in range(n):
            p = next(r for r in range(c, n) if a[r][c] != 0)
            if p != c: a[c], a[p] = a[p], a[c]; d = -d
            d *= a[c][c]
            for r in range(c + 1, n):
                f = a[r][c] / a[c][c]
                a[r] = [x - f * y for x, y in zip(a[r], a[c])]
        return int(d)
    assert determinant(big) == ref(big)
""",
    """
from fractions import Fraction

def determinant(m):
    a = [[Fraction(x) for x in row] for row in m]
    n, d = len(a), Fraction(1)
    for c in range(n):
        p = next((r for r in range(c, n) if a[r][c] != 0), None)
        if p is None:
            return 0
        if p != c:
            a[c], a[p] = a[p], a[c]
            d = -d
        d *= a[c][c]
        for r in range(c + 1, n):
            f = a[r][c] / a[c][c]
            a[r] = [x - f * y for x, y in zip(a[r], a[c])]
    return int(d)
""",
)

task(
    """Write `cheapest_route(n: int, flights: list[tuple[int, int, int]], src: int, dst: int, max_stops: int) -> int`.
Cities are 0..n-1 and each flight is (from, to, price). Return the cheapest total price from src to dst using at most
max_stops intermediate cities, or -1 if impossible. If src == dst the answer is 0.""",
    """
def test_routes():
    f = [(0, 1, 100), (1, 2, 100), (0, 2, 500), (2, 3, 100), (1, 3, 600)]
    assert cheapest_route(4, f, 0, 2, 1) == 200
    assert cheapest_route(4, f, 0, 2, 0) == 500
    assert cheapest_route(4, f, 0, 3, 1) == 600
    assert cheapest_route(4, f, 0, 3, 2) == 300
    assert cheapest_route(4, f, 3, 0, 5) == -1
    assert cheapest_route(4, f, 2, 2, 0) == 0
""",
    """
def cheapest_route(n, flights, src, dst, max_stops):
    INF = float("inf")
    cost = [INF] * n
    cost[src] = 0
    for _ in range(max_stops + 1):
        nxt = cost[:]
        for a, b, p in flights:
            if cost[a] + p < nxt[b]:
                nxt[b] = cost[a] + p
        cost = nxt
    return -1 if cost[dst] == INF else cost[dst]
""",
)

task(
    """Write `min_insertions(s: str) -> int` returning the minimum number of bracket characters that must be inserted
anywhere in s so that it becomes a balanced string over the three bracket types (), [] and {}. s contains only those six
characters and has length at most 40.""",
    """
def test_min_insertions():
    assert min_insertions("") == 0
    assert min_insertions("()[]{}") == 0
    assert min_insertions("(") == 1
    assert min_insertions("(]") == 2
    assert min_insertions("([)]") == 2
    assert min_insertions("((") == 2
    assert min_insertions("{[(])}") == 2
    assert min_insertions(")(") == 2
    assert min_insertions("([{}])}") == 1
""",
    """
from functools import lru_cache

def min_insertions(s):
    pairs = {"(": ")", "[": "]", "{": "}"}

    @lru_cache(maxsize=None)
    def f(i, j):  # min insertions to balance s[i:j]
        if i >= j:
            return 0
        best = 1 + f(i + 1, j)  # match s[i] with an inserted partner
        if s[i] in pairs:
            for k in range(i + 1, j):
                if s[k] == pairs[s[i]]:
                    best = min(best, f(i + 1, k) + f(k + 1, j))
        return best

    return f(0, len(s))
""",
)

task(
    """Write `parse_query(qs: str) -> dict[str, list[str]]` that parses a URL query string such as "a=1&b=x+y&a=%2F&flag".
Pairs are separated by &. A key without = gets the value "". Empty pairs (from "&&" or a leading or trailing &) are skipped.
Values and keys are decoded: + becomes a space and %XX becomes the byte with that hex value, decoded as UTF-8. Repeated keys
keep all values in order. Do not use urllib.""",
    """
def test_query():
    assert parse_query("a=1&b=x+y&a=%2F&flag") == {"a": ["1", "/"], "b": ["x y"], "flag": [""]}
    assert parse_query("") == {}
    assert parse_query("&&k=v&") == {"k": ["v"]}
    assert parse_query("name=Jos%C3%A9&eq=a%3Db") == {"name": ["José"], "eq": ["a=b"]}
    assert parse_query("x=1=2") == {"x": ["1=2"]}
    assert parse_query("sp%20ace=1") == {"sp ace": ["1"]}
""",
    """
import re

def _decode(s):
    s = s.replace("+", " ")
    out = bytearray()
    i = 0
    while i < len(s):
        if s[i] == "%" and re.fullmatch(r"[0-9A-Fa-f]{2}", s[i + 1:i + 3]):
            out.append(int(s[i + 1:i + 3], 16))
            i += 3
        else:
            out += s[i].encode()
            i += 1
    return out.decode("utf-8")

def parse_query(qs):
    result = {}
    for pair in qs.split("&"):
        if not pair:
            continue
        k, _, v = pair.partition("=")
        result.setdefault(_decode(k), []).append(_decode(v))
    return result
""",
)

task(
    """Write `count_islands(grid: list[str], diagonal: bool = False) -> int`. Each string is a row of '#' (land) and '.'
(water). Count connected groups of land cells. Cells connect horizontally and vertically, and also diagonally when
`diagonal` is True. Rows all have the same length; the grid may be empty.""",
    """
def test_islands():
    g = ["#..#",
         ".#..",
         "...#",
         "##.#"]
    assert count_islands(g) == 5
    assert count_islands(g, diagonal=True) == 4
    assert count_islands([]) == 0
    assert count_islands(["...."]) == 0
    assert count_islands(["####"]) == 1
""",
    """
def count_islands(grid, diagonal=False):
    seen, count = set(), 0
    steps = [(1, 0), (-1, 0), (0, 1), (0, -1)]
    if diagonal:
        steps += [(1, 1), (1, -1), (-1, 1), (-1, -1)]
    for r, row in enumerate(grid):
        for c, ch in enumerate(row):
            if ch == "#" and (r, c) not in seen:
                count += 1
                stack = [(r, c)]
                seen.add((r, c))
                while stack:
                    y, x = stack.pop()
                    for dy, dx in steps:
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < len(grid) and 0 <= nx < len(grid[0]) and grid[ny][nx] == "#" and (ny, nx) not in seen:
                            seen.add((ny, nx))
                            stack.append((ny, nx))
    return count
""",
)

task(
    """Write `kth_permutation(n: int, k: int) -> list[int]` returning the k-th permutation (1-indexed) of [1, 2, ..., n] in
lexicographic order, for 1 <= n <= 20. Raise ValueError if k is less than 1 or greater than n!. It must run fast even
for n = 20.""",
    """
from itertools import permutations
from math import factorial

def test_small():
    for n in range(1, 6):
        for k, p in enumerate(permutations(range(1, n + 1)), 1):
            assert kth_permutation(n, k) == list(p)

def test_large_and_errors():
    assert kth_permutation(20, factorial(20)) == list(range(20, 0, -1))
    assert kth_permutation(20, 1) == list(range(1, 21))
    for k in (0, factorial(4) + 1):
        try:
            kth_permutation(4, k)
        except ValueError:
            continue
        raise AssertionError(k)
""",
    """
from math import factorial

def kth_permutation(n, k):
    if not 1 <= k <= factorial(n):
        raise ValueError(k)
    pool, k, out = list(range(1, n + 1)), k - 1, []
    for i in range(n, 0, -1):
        idx, k = divmod(k, factorial(i - 1))
        out.append(pool.pop(idx))
    return out
""",
)

task(
    """Write `top_completions(counts: dict[str, int], prefix: str, k: int) -> list[str]`. `counts` maps words to how often they
were used. Return up to k words that start with prefix (case-sensitive), ordered by count descending, ties broken
alphabetically. A word equal to the prefix counts as a completion.""",
    """
def test_completions():
    counts = {"car": 5, "cart": 5, "care": 9, "cat": 1, "dog": 50, "ca": 2, "Car": 100}
    assert top_completions(counts, "ca", 3) == ["care", "car", "cart"]
    assert top_completions(counts, "ca", 10) == ["care", "car", "cart", "ca", "cat"]
    assert top_completions(counts, "car", 2) == ["care", "car"]
    assert top_completions(counts, "x", 3) == []
    assert top_completions(counts, "", 1) == ["Car"]
    assert top_completions(counts, "ca", 0) == []
""",
    """
def top_completions(counts, prefix, k):
    words = [w for w in counts if w.startswith(prefix)]
    return sorted(words, key=lambda w: (-counts[w], w))[:max(k, 0)]
""",
)

task(
    """Write `to_base(n: int, base: int) -> str` and `from_base(s: str, base: int) -> int` for bases 2 to 36, using digits
0-9 then lowercase a-z. Negative numbers get a leading "-". from_base accepts upper or lower case letters and raises
ValueError for an empty string or a digit not valid in the base. Do not use int(s, base).""",
    """
def test_roundtrip():
    for base in (2, 3, 7, 16, 36):
        for n in (0, 1, -1, 35, 36, 255, -1000, 10**20):
            assert from_base(to_base(n, base), base) == n

def test_values():
    assert to_base(255, 16) == "ff"
    assert to_base(-10, 2) == "-1010"
    assert to_base(0, 7) == "0"
    assert to_base(35, 36) == "z"
    assert from_base("FF", 16) == 255
    assert from_base("-z", 36) == -35

def test_errors():
    for s, b in [("", 10), ("12", 2), ("g", 16), ("-", 10)]:
        try:
            from_base(s, b)
        except ValueError:
            continue
        raise AssertionError((s, b))
""",
    """
DIGITS = "0123456789abcdefghijklmnopqrstuvwxyz"

def to_base(n, base):
    if n == 0:
        return "0"
    sign, n, out = "-" if n < 0 else "", abs(n), []
    while n:
        n, r = divmod(n, base)
        out.append(DIGITS[r])
    return sign + "".join(reversed(out))

def from_base(s, base):
    neg = s.startswith("-")
    body = s[1:] if neg else s
    if not body:
        raise ValueError("empty")
    n = 0
    for ch in body.lower():
        d = DIGITS.find(ch)
        if d < 0 or d >= base:
            raise ValueError(ch)
        n = n * base + d
    return -n if neg else n
""",
)

task(
    """Write `assign_rooms(meetings: list[tuple[int, int]]) -> list[int]`. Each meeting is a half-open interval [start, end).
Return a list where element i is the room number (starting at 0) for meeting i, using the minimum number of rooms. Process
meetings in order of start time (ties by original index) and give each one the lowest-numbered room that is free at its
start.""",
    """
def test_rooms():
    assert assign_rooms([]) == []
    assert assign_rooms([(0, 10), (10, 20)]) == [0, 0]
    assert assign_rooms([(0, 30), (5, 10), (15, 20)]) == [0, 1, 1]
    assert assign_rooms([(5, 10), (0, 30), (5, 8), (8, 12)]) == [1, 0, 2, 2]
    rooms = assign_rooms([(1, 4), (2, 5), (3, 6), (4, 7), (5, 8)])
    assert rooms == [0, 1, 2, 0, 1]
""",
    """
import heapq

def assign_rooms(meetings):
    order = sorted(range(len(meetings)), key=lambda i: (meetings[i][0], i))
    busy, free, out, next_room = [], [], [0] * len(meetings), 0
    for i in order:
        start, end = meetings[i]
        while busy and busy[0][0] <= start:
            heapq.heappush(free, heapq.heappop(busy)[1])
        if free:
            room = heapq.heappop(free)
        else:
            room, next_room = next_room, next_room + 1
        out[i] = room
        heapq.heappush(busy, (end, room))
    return out
""",
)

task(
    """Write `solve_sudoku(grid: list[str]) -> list[str]`. The input is 9 strings of 9 characters, digits 1-9 or '.' for
empty. Return the solved grid in the same format. Every puzzle given has exactly one solution. It must finish within a
few seconds for hard puzzles.""",
    """
def valid(g):
    rows = [set(r) for r in g]
    cols = [set(g[r][c] for r in range(9)) for c in range(9)]
    boxes = [set(g[r][c] for r in range(br, br + 3) for c in range(bc, bc + 3)) for br in (0, 3, 6) for bc in (0, 3, 6)]
    return all(s == set("123456789") for s in rows + cols + boxes)

def test_easy():
    p = ["53..7....", "6..195...", ".98....6.", "8...6...3", "4..8.3..1", "7...2...6", ".6....28.", "...419..5", "....8..79"]
    s = solve_sudoku(p)
    assert valid(s) and all(p[r][c] == "." or s[r][c] == p[r][c] for r in range(9) for c in range(9))

def test_hard():
    p = ["8........", "..36.....", ".7..9.2..", ".5...7...", "....457..", "...1...3.", "..1....68", "..85...1.", ".9....4.."]
    s = solve_sudoku(p)
    assert valid(s)
    assert all(p[r][c] == "." or s[r][c] == p[r][c] for r in range(9) for c in range(9))
""",
    """
def solve_sudoku(grid):
    g = [list(r) for r in grid]
    rows = [set(r) - {"."} for r in g]
    cols = [set(g[r][c] for r in range(9)) - {"."} for c in range(9)]
    boxes = [set() for _ in range(9)]
    for r in range(9):
        for c in range(9):
            if g[r][c] != ".":
                boxes[r // 3 * 3 + c // 3].add(g[r][c])
    empty = [(r, c) for r in range(9) for c in range(9) if g[r][c] == "."]

    def solve():
        if not empty:
            return True
        best = min(empty, key=lambda p: 9 - len(rows[p[0]] | cols[p[1]] | boxes[p[0] // 3 * 3 + p[1] // 3]))
        r, c = best
        b = r // 3 * 3 + c // 3
        empty.remove(best)
        for d in "123456789":
            if d not in rows[r] and d not in cols[c] and d not in boxes[b]:
                g[r][c] = d
                rows[r].add(d); cols[c].add(d); boxes[b].add(d)
                if solve():
                    return True
                rows[r].discard(d); cols[c].discard(d); boxes[b].discard(d)
        g[r][c] = "."
        empty.append(best)
        return False

    solve()
    return ["".join(r) for r in g]
""",
)

task(
    """Write `interval_union_length(intervals: list[tuple[float, float]]) -> float` returning the total length covered by
the union of closed intervals [a, b]. Intervals may overlap, be nested, be given in any order, or have a > b (treat those
as [b, a]).""",
    """
def test_union():
    assert interval_union_length([]) == 0
    assert interval_union_length([(0, 1), (2, 3)]) == 2
    assert interval_union_length([(0, 5), (1, 2), (4, 7)]) == 7
    assert interval_union_length([(3, 1), (0, 2)]) == 3
    assert abs(interval_union_length([(0.5, 1.25), (1.0, 2.0)]) - 1.5) < 1e-9
    assert interval_union_length([(1, 1)]) == 0
""",
    """
def interval_union_length(intervals):
    total, cur_s, cur_e = 0, None, None
    for a, b in sorted((min(a, b), max(a, b)) for a, b in intervals):
        if cur_e is None or a > cur_e:
            if cur_e is not None:
                total += cur_e - cur_s
            cur_s, cur_e = a, b
        else:
            cur_e = max(cur_e, b)
    if cur_e is not None:
        total += cur_e - cur_s
    return total
""",
)


from .code_tasks_hard import register_hard  # noqa: E402

register_hard(task)


def stub_for(reference):
    """Same signatures as the reference, every body replaced with `return None`."""
    lines = []
    for line in reference.splitlines():
        m = re.match(r"^(\s*)(def \w+\(.*\):|class \w+.*:)\s*$", line)
        if m:
            lines.append(line)
            lines.append(m.group(1) + "    " + ("pass" if line.lstrip().startswith("class") else "return None"))
    return "\n".join(lines) or "pass"


def main():
    out = Path(__file__).resolve().parents[1] / "code.jsonl"
    rows, problems = [], []
    for k, (prompt, tests, reference, tier) in enumerate(TASKS, 1):
        tid = f"code-{k:03d}"
        t = {"tests": tests}
        ok = code_grader.grade(t, {"content": f"```python\n{reference}```"})
        bad = code_grader.grade(t, {"content": f"```python\n{stub_for(reference)}\n```"})
        if not ok["correct"]:
            problems.append(f"{tid}: reference fails\n{ok['detail']}")
        if bad["correct"]:
            problems.append(f"{tid}: stub passes (tests too weak)")
        rows.append({"id": tid, "category": "code", "grader": "code", "tier": tier, "prompt": prompt + SUFFIX,
                     "tests": tests, "source": SOURCE})
        print(tid, "ok" if ok["correct"] and not bad["correct"] else "PROBLEM")
    if problems:
        raise SystemExit("\n\n".join(problems))
    with out.open("w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    print(f"{len(rows)} tasks -> {out}")


if __name__ == "__main__":
    main()
