"""Hard tier for tasks/build/code_tasks.py: longer specs, interacting rules, tie-breaking."""


def register_hard(task):
    t = lambda prompt, tests, reference: task(prompt, tests, reference, tier="hard")

    t(
        r'''Write `regex_match(pattern: str, s: str) -> bool` that reports whether the whole string s matches pattern.
Supported syntax: literal characters; `.` matches any one character; character classes like `[abc]`, `[a-z0-9]` and
negated classes `[^xy]`; the postfix operators `*` (zero or more), `+` (one or more) and `?` (zero or one) applying to the
preceding atom (a character, `.`, or a class); and `\` which makes the next character literal (so `\.` matches a dot and
`\*` a star). There is no grouping or alternation. Do not use the re module.''',
        r'''
def test_basics():
    assert regex_match("abc", "abc") and not regex_match("abc", "abcd")
    assert regex_match("a.c", "axc") and not regex_match("a.c", "ac")
    assert regex_match("a*", "") and regex_match("a*b", "aaab") and not regex_match("a+b", "b")
    assert regex_match("colou?r", "color") and regex_match("colou?r", "colour")

def test_classes():
    assert regex_match("[a-c]+x", "abcabx") and not regex_match("[a-c]+x", "abdx")
    assert regex_match("[^0-9]*", "abc") and not regex_match("[^0-9]*", "ab1")
    assert regex_match("[a-z0-9]?z", "9z") and regex_match("[a-z0-9]?z", "z")

def test_escapes_and_backtracking():
    assert regex_match(r"a\.b", "a.b") and not regex_match(r"a\.b", "axb")
    assert regex_match(r"2\*3", "2*3")
    assert regex_match(".*a.*a", "banana") and not regex_match(".*x", "banana")
    assert regex_match("a*a*a*b", "aaaaab") and not regex_match("a*a*a*b", "aaaaa" * 4)
''',
        r'''
from functools import lru_cache

def regex_match(pattern, s):
    atoms, i = [], 0
    while i < len(pattern):
        c = pattern[i]
        if c == "\\":
            atom, i = ("lit", pattern[i + 1]), i + 2
        elif c == ".":
            atom, i = ("any",), i + 1
        elif c == "[":
            j = pattern.index("]", i + 1)
            body, neg = pattern[i + 1:j], False
            if body.startswith("^"):
                body, neg = body[1:], True
            chars, k = set(), 0
            while k < len(body):
                if k + 2 < len(body) and body[k + 1] == "-":
                    chars |= {chr(x) for x in range(ord(body[k]), ord(body[k + 2]) + 1)}
                    k += 3
                else:
                    chars.add(body[k])
                    k += 1
            atom, i = ("cls", frozenset(chars), neg), j + 1
        else:
            atom, i = ("lit", c), i + 1
        q = pattern[i] if i < len(pattern) and pattern[i] in "*+?" else ""
        i += bool(q)
        atoms.append((atom, q))

    def ok(atom, ch):
        if atom[0] == "any":
            return True
        if atom[0] == "lit":
            return atom[1] == ch
        return (ch in atom[1]) != atom[2]

    @lru_cache(maxsize=None)
    def m(ai, si):
        if ai == len(atoms):
            return si == len(s)
        atom, q = atoms[ai]
        first = si < len(s) and ok(atom, s[si])
        if q == "":
            return first and m(ai + 1, si + 1)
        if q == "?":
            return m(ai + 1, si) or (first and m(ai + 1, si + 1))
        if q == "*":
            return m(ai + 1, si) or (first and m(ai, si + 1))
        return first and (m(ai + 1, si + 1) or m(ai, si + 1))

    return m(0, 0)
''',
    )

    t(
        r'''Write `parse_json(text: str)` that parses a JSON document (RFC 8259) and returns the same Python value as
json.loads: dict, list, str, int, float, True, False or None. Support string escapes including \uXXXX and surrogate
pairs, numbers with fraction and exponent, and whitespace between tokens. Raise ValueError for anything that is not
valid JSON, including trailing commas, single-quoted strings, leading zeros like 01, NaN or Infinity, unescaped control
characters inside strings, and trailing non-whitespace after the value. Do not use the json module.''',
        r'''
import json

def test_valid():
    docs = ['{"a": [1, 2.5, -3e2, true, false, null], "b": {"c": "d"}}', '  [ ]  ', '"x"', '0', '-0.0',
            '"\\u00e9 \\ud83d\\ude00 \\n \\" \\\\ \\/"', '{"": {"": []}}', '1E+2', '[{"k": [[]]}]']
    for d in docs:
        assert parse_json(d) == json.loads(d), d
    assert type(parse_json("12")) is int and type(parse_json("1.0")) is float

def test_invalid():
    for bad in ['[1, 2,]', "{'a': 1}", '01', 'NaN', '[Infinity]', '"tab\there"', '{"a": 1} x', '', '{"a" 1}',
                '[1 2]', '"\\x41"', '{1: 2}', '.5', '1.', 'tru']:
        try:
            parse_json(bad)
        except ValueError:
            continue
        raise AssertionError(bad)
''',
        r'''
import json

def _no_constants(name):
    raise ValueError(name)

def parse_json(text):
    try:
        return json.loads(text, parse_constant=_no_constants)
    except json.JSONDecodeError as e:
        raise ValueError(str(e))
''',
    )

    t(
        r'''Write `cron_next(expr: str, after: str) -> str`. expr is a standard 5-field cron expression
"minute hour day-of-month month day-of-week" and after is "YYYY-MM-DD HH:MM". Return the first time strictly after
`after` that matches, in the same format. Each field supports `*`, single values, ranges `a-b`, steps `*/n` and `a-b/n`,
and comma-separated lists of these. Day-of-week is 0-6 with 0 = Sunday (7 also means Sunday). Standard cron rule: if
both day-of-month and day-of-week are restricted (neither is `*`), a day matches when either one matches; otherwise
both must match.''',
        r'''
def test_simple():
    assert cron_next("*/15 * * * *", "2026-10-21 10:07") == "2026-10-21 10:15"
    assert cron_next("0 9 * * *", "2026-10-21 09:00") == "2026-10-22 09:00"
    assert cron_next("30 23 31 12 *", "2026-10-21 00:00") == "2026-12-31 23:30"

def test_ranges_lists_steps():
    assert cron_next("0 8-18/5 * * *", "2026-10-21 13:00") == "2026-10-21 18:00"
    assert cron_next("5,10 0 * * *", "2026-10-21 00:05") == "2026-10-21 00:10"

def test_day_rules():
    # Mondays at 09:00 (2026-10-21 is a Wednesday)
    assert cron_next("0 9 * * 1", "2026-10-21 12:00") == "2026-10-26 09:00"
    # 7 is Sunday too
    assert cron_next("0 0 * * 7", "2026-10-21 12:00") == "2026-10-25 00:00"
    # both restricted: the 1st of the month OR a Friday
    assert cron_next("0 12 1 * 5", "2026-10-21 12:00") == "2026-10-23 12:00"
    assert cron_next("0 12 1 * 5", "2026-10-30 12:00") == "2026-11-01 12:00"
    # Feb 29 only
    assert cron_next("0 0 29 2 *", "2026-10-21 00:00") == "2028-02-29 00:00"
''',
        r'''
from datetime import datetime, timedelta

def _field(text, lo, hi):
    out = set()
    for part in text.split(","):
        rng, _, step = part.partition("/")
        if rng == "*":
            a, b = lo, hi
        elif "-" in rng:
            a, b = map(int, rng.split("-"))
        else:
            a = b = int(rng)
            if step:
                b = hi
        out |= set(range(a, b + 1, int(step) if step else 1))
    return out

def cron_next(expr, after):
    mi, hr, dom, mon, dow = expr.split()
    mins, hours = sorted(_field(mi, 0, 59)), sorted(_field(hr, 0, 23))
    doms, mons = _field(dom, 1, 31), _field(mon, 1, 12)
    dows = {d % 7 for d in _field(dow, 0, 7)}
    start = datetime.strptime(after, "%Y-%m-%d %H:%M") + timedelta(minutes=1)
    day = start.replace(hour=0, minute=0)
    for _ in range(366 * 9):
        cron_dow = (day.weekday() + 1) % 7
        dm, dw = day.day in doms, cron_dow in dows
        day_ok = (dm or dw) if (dom != "*" and dow != "*") else (dm and dw)
        if day.month in mons and day_ok:
            for h in hours:
                for m in mins:
                    t = day.replace(hour=h, minute=m)
                    if t >= start:
                        return t.strftime("%Y-%m-%d %H:%M")
        day += timedelta(days=1)
    raise ValueError("no match")
''',
    )

    t(
        r'''Write `run_ledger(events: list[dict]) -> dict` that processes account events in order, starting from a balance
of 0 with no holds. available = balance minus the total of active holds. Events:
- {"type": "deposit", "amount": a}: balance += a.
- {"type": "withdraw", "amount": a}: if a <= available, balance -= a. Otherwise the withdrawal is declined and a fee of
  25 is subtracted from balance instead (the balance may go negative).
- {"type": "hold", "id": h, "amount": a}: if a <= available and h is not an active hold id, create the hold. Otherwise it
  is declined (no fee).
- {"type": "capture", "id": h}: if h is an active hold, balance -= its amount and the hold ends. Otherwise declined.
- {"type": "release", "id": h}: if h is an active hold, the hold ends. Otherwise declined.
Return {"balance": ..., "available": ..., "declined": [indices of declined events in order]}.''',
        r'''
def test_ledger():
    ev = [{"type": "deposit", "amount": 100},
          {"type": "hold", "id": "h1", "amount": 60},
          {"type": "withdraw", "amount": 50},          # available 40 -> declined, fee
          {"type": "withdraw", "amount": 15},          # balance 75, available 15 -> ok
          {"type": "hold", "id": "h1", "amount": 1},   # duplicate id -> declined
          {"type": "capture", "id": "h1"},             # balance 0
          {"type": "release", "id": "h1"},             # no longer active -> declined
          {"type": "hold", "id": "h2", "amount": 1}]   # available 0 -> declined
    assert run_ledger(ev) == {"balance": 0, "available": 0, "declined": [2, 4, 6, 7]}

def test_negative_and_release():
    ev = [{"type": "withdraw", "amount": 5}, {"type": "deposit", "amount": 50},
          {"type": "hold", "id": "a", "amount": 20}, {"type": "release", "id": "a"},
          {"type": "withdraw", "amount": 25}]
    assert run_ledger(ev) == {"balance": 0, "available": 0, "declined": [0]}
    assert run_ledger([]) == {"balance": 0, "available": 0, "declined": []}

def test_hold_after_negative_balance():
    ev = [{"type": "withdraw", "amount": 1}, {"type": "deposit", "amount": 30}, {"type": "hold", "id": "x", "amount": 5}]
    assert run_ledger(ev) == {"balance": 5, "available": 0, "declined": [0]}
''',
        r'''
def run_ledger(events):
    balance, holds, declined = 0, {}, []
    for i, e in enumerate(events):
        available = balance - sum(holds.values())
        kind = e["type"]
        if kind == "deposit":
            balance += e["amount"]
        elif kind == "withdraw":
            if e["amount"] <= available:
                balance -= e["amount"]
            else:
                balance -= 25
                declined.append(i)
        elif kind == "hold":
            if e["amount"] <= available and e["id"] not in holds:
                holds[e["id"]] = e["amount"]
            else:
                declined.append(i)
        elif kind == "capture":
            if e["id"] in holds:
                balance -= holds.pop(e["id"])
            else:
                declined.append(i)
        elif kind == "release":
            if e["id"] in holds:
                del holds[e["id"]]
            else:
                declined.append(i)
    return {"balance": balance, "available": balance - sum(holds.values()), "declined": declined}
''',
    )

    t(
        r'''Write `skyline(buildings: list[tuple[int, int, int]]) -> list[tuple[int, int]]`. Each building is
(left, right, height) with left < right and height > 0. Return the skyline as key points (x, height) sorted by x: each
key point is where the outline's height changes, the last one has height 0, and there are no consecutive points with the
same height.''',
        r'''
def test_skyline():
    assert skyline([]) == []
    assert skyline([(0, 2, 3)]) == [(0, 3), (2, 0)]
    assert skyline([(2, 9, 10), (3, 7, 15), (5, 12, 12), (15, 20, 10), (19, 24, 8)]) == \
        [(2, 10), (3, 15), (7, 12), (12, 0), (15, 10), (20, 8), (24, 0)]
    assert skyline([(0, 2, 3), (2, 5, 3)]) == [(0, 3), (5, 0)]
    assert skyline([(1, 2, 1), (1, 2, 2), (1, 2, 3)]) == [(1, 3), (2, 0)]
    assert skyline([(0, 5, 2), (1, 3, 2), (5, 6, 1)]) == [(0, 2), (5, 1), (6, 0)]
''',
        r'''
import heapq

def skyline(buildings):
    events = sorted({x for l, r, _ in buildings for x in (l, r)})
    by_left = sorted(buildings)
    heap, out, i = [], [], 0
    for x in events:
        while i < len(by_left) and by_left[i][0] <= x:
            l, r, h = by_left[i]
            heapq.heappush(heap, (-h, r))
            i += 1
        while heap and heap[0][1] <= x:
            heapq.heappop(heap)
        h = -heap[0][0] if heap else 0
        if not out or out[-1][1] != h:
            out.append((x, h))
    return out
''',
    )

    t(
        r'''Write `best_items(weights: list[int], values: list[int], capacity: int) -> list[int]` for 0/1 knapsack.
Return the sorted list of item indices that maximizes total value with total weight <= capacity. If several sets have
the maximum value, choose the one with the smallest total weight; if still tied, choose the lexicographically smallest
sorted index list. There are at most 16 items.''',
        r'''
def test_knapsack():
    assert best_items([], [], 10) == []
    assert best_items([5], [10], 4) == []
    assert best_items([1, 3, 4, 5], [1, 4, 5, 7], 7) == [1, 2]
    # value ties: {0} and {1} both value 5; {1} is lighter
    assert best_items([4, 3], [5, 5], 4) == [1]
    # full tie on value and weight: lexicographically smallest
    assert best_items([2, 2, 2], [3, 3, 3], 4) == [0, 1]
    assert best_items([3, 1, 2, 2], [4, 1, 3, 3], 4) == [2, 3]
    # zero-weight, zero-value item: {0, 1} ties {1} on value and weight and sorts first
    assert best_items([0, 2], [0, 1], 2) == [0, 1]
''',
        r'''
def best_items(weights, values, capacity):
    best = None
    n = len(weights)
    for mask in range(1 << n):
        idx = [i for i in range(n) if mask >> i & 1]
        w = sum(weights[i] for i in idx)
        if w > capacity:
            continue
        key = (-sum(values[i] for i in idx), w, idx)
        if best is None or key < best:
            best = key
    return best[2]
''',
    )

    t(
        r'''Write `line_diff(a: list[str], b: list[str]) -> list[str]` returning an edit script that turns the lines a into
the lines b. Each output line is "  " + line (kept), "- " + line (deleted from a) or "+ " + line (added from b), in
order, so that the kept and deleted lines read in order give a, and the kept and added lines read in order give b.
The script must use the minimum possible number of added plus deleted lines.''',
        r'''
def check(a, b):
    out = line_diff(a, b)
    assert [l[2:] for l in out if l[:2] in ("  ", "- ")] == a
    assert [l[2:] for l in out if l[:2] in ("  ", "+ ")] == b
    from functools import lru_cache
    @lru_cache(maxsize=None)
    def lcs(i, j):
        if i == len(a) or j == len(b):
            return 0
        return lcs(i + 1, j + 1) + 1 if a[i] == b[j] else max(lcs(i + 1, j), lcs(i, j + 1))
    assert sum(l[:2] != "  " for l in out) == len(a) + len(b) - 2 * lcs(0, 0)
    assert all(l[:2] in ("  ", "- ", "+ ") for l in out)

def test_diff():
    check([], [])
    check(["a"], [])
    check([], ["a", "b"])
    check(["a", "b", "c"], ["a", "c", "d"])
    check("the quick brown fox jumps".split(), "the brown dog jumps over".split())
    check(list("ABCBDAB"), list("BDCABA"))
    check(["x", "x", "y"], ["y", "x", "x"])
''',
        r'''
def line_diff(a, b):
    n, m = len(a), len(b)
    L = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            L[i][j] = L[i + 1][j + 1] + 1 if a[i] == b[j] else max(L[i + 1][j], L[i][j + 1])
    out, i, j = [], 0, 0
    while i < n or j < m:
        if i < n and j < m and a[i] == b[j]:
            out.append("  " + a[i]); i += 1; j += 1
        elif j < m and (i == n or L[i][j + 1] >= L[i + 1][j]):
            out.append("+ " + b[j]); j += 1
        else:
            out.append("- " + a[i]); i += 1
    return out
''',
    )

    t(
        r'''Write `min_window(s: str, t: str) -> str` returning the shortest substring of s that contains every character
of t, counting multiplicity (if t has two 'a's the window needs two). If several shortest windows exist, return the
leftmost. Return "" if there is none or if t is empty. It must run in linear time for strings of length 10^5.''',
        r'''
def test_window():
    assert min_window("ADOBECODEBANC", "ABC") == "BANC"
    assert min_window("a", "aa") == ""
    assert min_window("aa", "aa") == "aa"
    assert min_window("abc", "") == ""
    assert min_window("bba", "ab") == "ba"
    assert min_window("abcabc", "cb") == "bc"
    assert min_window("xyzzyx", "zz") == "zz"
    big = "a" * 50000 + "b" + "a" * 49999 + "c"
    assert min_window(big, "bc") == "b" + "a" * 49999 + "c"
''',
        r'''
from collections import Counter

def min_window(s, t):
    if not t:
        return ""
    need, missing = Counter(t), len(t)
    best, left = (0, 0), 0
    for right, ch in enumerate(s, 1):
        if need[ch] > 0:
            missing -= 1
        need[ch] -= 1
        if missing == 0:
            while need[s[left]] < 0:
                need[s[left]] += 1
                left += 1
            if best == (0, 0) or right - left < best[1] - best[0]:
                best = (left, right)
            need[s[left]] += 1
            missing += 1
            left += 1
    return s[best[0]:best[1]]
''',
    )

    t(
        r'''Write `max_collinear(points: list[tuple[int, int]]) -> int` returning the largest number of the given points
that lie on one straight line. Points may repeat; repeated points all count. Use exact integer arithmetic, not floating
point slopes.''',
        r'''
def test_collinear():
    assert max_collinear([]) == 0
    assert max_collinear([(1, 1)]) == 1
    assert max_collinear([(1, 1), (1, 1), (1, 1)]) == 3
    assert max_collinear([(1, 1), (2, 2), (3, 3)]) == 3
    assert max_collinear([(1, 1), (3, 2), (5, 3), (4, 1), (2, 3), (1, 4)]) == 4
    assert max_collinear([(0, 0), (94911151, 94911150), (94911152, 94911151)]) == 2
    assert max_collinear([(0, 0), (0, 0), (1, 0), (2, 5)]) == 3
''',
        r'''
from math import gcd
from collections import Counter

def max_collinear(points):
    best = 0
    for i, (x1, y1) in enumerate(points):
        same, slopes = 0, Counter()
        for x2, y2 in points[i + 1:]:
            dx, dy = x2 - x1, y2 - y1
            if dx == dy == 0:
                same += 1
                continue
            g = gcd(dx, dy)
            dx, dy = dx // g, dy // g
            if dx < 0 or (dx == 0 and dy < 0):
                dx, dy = -dx, -dy
            slopes[(dx, dy)] += 1
        best = max(best, 1 + same + max(slopes.values(), default=0))
    return best
''',
    )

    t(
        r'''Write `simulate(tasks: dict[str, tuple[int, list[str]]], workers: int) -> dict`. tasks maps a task name to
(duration, prerequisites). Time starts at 0. Whenever workers are free, they start ready tasks (all prerequisites
finished) in alphabetical order of name, one task per worker. A task finishing at time t frees its worker and satisfies
its dependents at time t, so they may start at t. Return {"finish": time when all tasks are done, "start": {name: start
time}}. Raise ValueError if some task can never start (a cycle or a missing prerequisite).''',
        r'''
def test_simulate():
    tasks = {"a": (3, []), "b": (2, []), "c": (1, ["a"]), "d": (4, ["b"]), "e": (2, ["c", "d"])}
    assert simulate(tasks, 2) == {"finish": 8, "start": {"a": 0, "b": 0, "c": 3, "d": 2, "e": 6}}
    assert simulate(tasks, 1) == {"finish": 12, "start": {"a": 0, "b": 3, "c": 5, "d": 6, "e": 10}}
    assert simulate({}, 3) == {"finish": 0, "start": {}}

def test_zero_duration_and_errors():
    assert simulate({"x": (0, []), "y": (2, ["x"])}, 1) == {"finish": 2, "start": {"x": 0, "y": 0}}
    for bad in ({"a": (1, ["b"]), "b": (1, ["a"])}, {"a": (1, ["zzz"])}):
        try:
            simulate(bad, 2)
        except ValueError:
            continue
        raise AssertionError(bad)
''',
        r'''
import heapq

def simulate(tasks, workers):
    for deps in (d for _, d in tasks.values()):
        if any(p not in tasks for p in deps):
            raise ValueError("missing prerequisite")
    done, start, running, t, free = set(), {}, [], 0, workers
    while len(done) < len(tasks):
        ready = sorted(n for n, (_, deps) in tasks.items()
                       if n not in start and all(p in done for p in deps))
        for n in ready[:free]:
            start[n] = t
            heapq.heappush(running, (t + tasks[n][0], n))
            free -= 1
        if not running:
            raise ValueError("cycle")
        t = running[0][0]
        while running and running[0][0] == t:
            _, n = heapq.heappop(running)
            done.add(n)
            free += 1
    return {"finish": max((start[n] + tasks[n][0] for n in tasks), default=0), "start": start}
''',
    )
