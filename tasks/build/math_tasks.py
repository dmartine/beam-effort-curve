"""Build tasks/math.jsonl. Every answer is computed here by brute force, not typed in.

    python -m tasks.build.math_tasks
"""

import json
from fractions import Fraction
from itertools import permutations, product
from math import gcd, isqrt
from pathlib import Path

from sympy import Matrix, factorint

SUFFIX = " Put the final answer in \\boxed{}."
SOURCE = "written for this repo (2026-10); answer computed by brute force in tasks/build/math_tasks.py"
TASKS = []


def task(prompt, tier="core"):
    def register(fn):
        TASKS.append((prompt, fn, tier))
        return fn
    return register


def squarefree(n):
    return all(e == 1 for e in factorint(n).values())


@task("How many ordered triples (a, b, c) of positive integers satisfy a + b + c = 30 and a < b < c?")
def _():
    return sum(1 for a in range(1, 30) for b in range(a + 1, 30) if 30 - a - b > b)


@task("Find the last three digits of 3^(3^2026). Give the answer as an integer from 0 to 999.")
def _():
    return pow(3, 3**2026, 1000)


@task("How many subsets of {1, 2, ..., 15} (including the empty set) have a sum divisible by 5?")
def _():
    return sum(1 for mask in range(1 << 15) if sum(i + 1 for i in range(15) if mask >> i & 1) % 5 == 0)


@task("How many positive divisors of 2026^4 are congruent to 1 modulo 3?")
def _():
    n = 2026**4  # 2^4 * 1013^4
    return sum(1 for i in range(5) for j in range(5) if (2**i * 1013**j) % 3 == 1 and n % (2**i * 1013**j) == 0)


@task(
    "Let Z(n) be the number of trailing zeros of n!. How many integers k with 1 <= k <= 2026 "
    "are not equal to Z(n) for any positive integer n?"
)
def _():
    def z(n):
        c, p = 0, 5
        while p <= n:
            c += n // p
            p *= 5
        return c
    seen, n = set(), 1
    while z(n) <= 2026:
        seen.add(z(n))
        n += 1
    return sum(1 for k in range(1, 2027) if k not in seen)


@task(
    "How many permutations s of {1, 2, ..., 8} satisfy s(i) != i for every i, "
    "and s(i) != i + 1 for every i from 1 to 7?"
)
def _():
    return sum(
        1 for p in permutations(range(1, 9))
        if all(p[i - 1] != i for i in range(1, 9)) and all(p[i - 1] != i + 1 for i in range(1, 8))
    )


@task("How many binary strings of length 20 contain no three consecutive 1s and have an even number of 1s?")
def _():
    return sum(1 for m in range(1 << 20) if "111" not in format(m, "020b") and bin(m).count("1") % 2 == 0)


@task("Find the sum of all positive integers n < 1000 such that n is a multiple of 7 and both n and n + 2 are squarefree.")
def _():
    return sum(n for n in range(7, 1000, 7) if squarefree(n) and squarefree(n + 2))


@task("How many ordered pairs of integers (x, y) satisfy x^2 + xy + y^2 = 2457?")
def _():
    return sum(1 for x in range(-60, 61) for y in range(-60, 61) if x * x + x * y + y * y == 2457)


@task(
    "Four fair six-sided dice are rolled. The probability that the product of the four numbers is a perfect square "
    "is m/n in lowest terms. Find m + n."
)
def _():
    hits = sum(1 for r in product(range(1, 7), repeat=4) if isqrt(r[0] * r[1] * r[2] * r[3]) ** 2 == r[0] * r[1] * r[2] * r[3])
    f = Fraction(hits, 6**4)
    return f.numerator + f.denominator


@task("In how many ways can a 4 by 8 rectangle be tiled with 1 by 2 dominoes?")
def _():
    rows, cols = 4, 8

    def fill(col_mask, row, next_mask, out):
        if row == rows:
            out.append(next_mask)
        elif col_mask >> row & 1:
            fill(col_mask, row + 1, next_mask, out)
        else:
            fill(col_mask, row + 1, next_mask | 1 << row, out)  # horizontal domino into next column
            if row + 1 < rows and not col_mask >> (row + 1) & 1:
                fill(col_mask, row + 2, next_mask, out)  # vertical domino

    ways = {0: 1}
    for _ in range(cols):
        nxt = {}
        for mask, w in ways.items():
            out = []
            fill(mask, 0, 0, out)
            for m in out:
                nxt[m] = nxt.get(m, 0) + w
        ways = nxt
    return ways.get(0, 0)


@task(
    "Each face of a cube is painted one of 4 colors so that every pair of opposite faces gets two different colors. "
    "Two colorings are the same if one can be rotated to give the other. How many distinct colorings are there?"
)
def _():
    # faces: 0 up, 1 down, 2 front, 3 back, 4 left, 5 right
    spin = (0, 1, 5, 4, 2, 3)   # about the up-down axis: front->right->back->left->front
    tilt = (2, 3, 1, 0, 4, 5)   # about the left-right axis: up->front->down->back->up
    group = {tuple(range(6))}
    while True:
        new = {tuple(g[s[i]] for i in range(6)) for g in group for s in (spin, tilt)} | group
        if new == group:
            break
        group = new
    assert len(group) == 24
    colorings = [c for c in product(range(4), repeat=6) if c[0] != c[1] and c[2] != c[3] and c[4] != c[5]]
    orbits = {min(tuple(c[g[i]] for i in range(6)) for g in group) for c in colorings}
    return len(orbits)


@task(
    "A permutation of {1, 2, ..., 10} is chosen uniformly at random. The expected number of its cycles whose length "
    "is a multiple of 3 is m/n in lowest terms. Find m + n."
)
def _():
    f = sum(Fraction(1, k) for k in (3, 6, 9))
    return f.numerator + f.denominator


@task(
    "How many integers k with 1 <= k <= 2026 can be written as floor(x) + floor(2x) + floor(4x) + floor(8x) "
    "for some real number x?"
)
def _():
    values = set()
    for n in range(0, 2026 // 15 + 2):
        for j in range(8):  # value is constant on [n + j/8, n + (j+1)/8)
            x = Fraction(8 * n + j, 8)
            values.add(sum((x * m).__floor__() for m in (1, 2, 4, 8)))
    return sum(1 for k in range(1, 2027) if k in values)


@task(
    "How many triangles with positive integer side lengths and perimeter 2026 are there, counting triangles that are "
    "congruent as the same?"
)
def _():
    return sum(1 for a in range(1, 2026) for b in range(a, 2026) if (c := 2026 - a - b) >= b and a + b > c)


@task("Find the sum of all positive integers n for which n^2 - 37n + 400 is a perfect square.")
def _():
    return sum(n for n in range(1, 10_000) if (v := n * n - 37 * n + 400) >= 0 and isqrt(v) ** 2 == v)


@task("How many 3 by 3 matrices with every entry in {0, 1, 2} have determinant exactly 1?")
def _():
    count = 0
    for e in product(range(3), repeat=9):
        a, b, c, d, f, g, h, i, j = e
        if a * (f * j - g * i) - b * (d * j - g * h) + c * (d * i - f * h) == 1:
            count += 1
    return count


@task("Find the remainder when 1^1 + 2^2 + 3^3 + ... + 2026^2026 is divided by 1000.")
def _():
    return sum(pow(k, k, 1000) for k in range(1, 2027)) % 1000


@task("How many positive integers at most 1,000,000 are palindromes both in base 10 and in base 3?")
def _():
    def b3(n):
        s = ""
        while n:
            s = str(n % 3) + s
            n //= 3
        return s
    return sum(1 for n in range(1, 1_000_001) if str(n) == str(n)[::-1] and b3(n) == b3(n)[::-1])


@task(
    "Consider the grid graph whose vertices are the 12 points (i, j) with 0 <= i <= 2 and 0 <= j <= 3, with an edge "
    "between points at distance 1. How many spanning trees does this graph have?"
)
def _():
    pts = [(i, j) for i in range(3) for j in range(4)]
    idx = {p: k for k, p in enumerate(pts)}
    lap = [[0] * 12 for _ in range(12)]
    for (i, j) in pts:
        for q in ((i + 1, j), (i, j + 1)):
            if q in idx:
                a, b = idx[(i, j)], idx[q]
                lap[a][b] -= 1
                lap[b][a] -= 1
                lap[a][a] += 1
                lap[b][b] += 1
    return int(Matrix(lap)[1:, 1:].det())


@task(
    "How many ordered pairs (a, b) of integers with 1 <= a <= 100 and 1 <= b <= 100 satisfy gcd(a, b) = 1 "
    "and a + b divides ab + 1?"
)
def _():
    return sum(1 for a in range(1, 101) for b in range(1, 101) if gcd(a, b) == 1 and (a * b + 1) % (a + b) == 0)


@task("In how many ways can 40 be written as a sum of distinct odd positive integers, where order does not matter?")
def _():
    ways = [1] + [0] * 40
    for part in range(1, 41, 2):
        for s in range(40, part - 1, -1):
            ways[s] += ways[s - part]
    return ways[40]


@task("How many points (x, y) with integer coordinates satisfy x^2 + y^2 < 2026?")
def _():
    return sum(1 for x in range(-46, 47) for y in range(-46, 47) if x * x + y * y < 2026)


@task(
    "How many strings of length 7 over the alphabet {A, B, C} do not contain ABC as a substring (three consecutive "
    "letters) and start and end with the same letter?"
)
def _():
    return sum(1 for s in product("ABC", repeat=7) if "ABC" not in "".join(s) and s[0] == s[-1])


@task("Find the sum of the distinct prime factors of 3^20 - 1.")
def _():
    return sum(factorint(3**20 - 1))


# ---------------------------------------------------------------- hard tier
# Targets the kinds of problems `low` failed in the 2026-10-21 sweep: careful enumeration,
# constraints that interact, and easy-to-miss edge cases.

@task("How many 4 by 4 matrices with every entry in {0, 1, 2} have every row sum and every column sum equal to 3?", "hard")
def _():
    rows = [r for r in product(range(3), repeat=4) if sum(r) == 3]
    return sum(1 for m in product(rows, repeat=4) if all(sum(r[j] for r in m) == 3 for j in range(4)))


@task("How many permutations s of {1, 2, ..., 10} satisfy |s(i) - i| <= 2 for every i?", "hard")
def _():
    from functools import lru_cache

    @lru_cache(maxsize=None)
    def count(i, used):
        if i > 10:
            return 1
        return sum(count(i + 1, used | 1 << v) for v in range(max(1, i - 2), min(10, i + 2) + 1) if not used >> v & 1)
    return count(1, 0)


@task("Each cell of a 4 by 4 grid is colored black or white. How many colorings contain no 2 by 2 block of four cells "
      "that are all the same color?", "hard")
def _():
    def bad(m):
        cell = lambda r, c: m >> (4 * r + c) & 1
        return any(cell(r, c) == cell(r, c + 1) == cell(r + 1, c) == cell(r + 1, c + 1) for r in range(3) for c in range(3))
    return sum(1 for m in range(1 << 16) if not bad(m))


@task("Find the sum of all positive integers n <= 10000 such that n divides 2^n + 1.", "hard")
def _():
    return sum(n for n in range(1, 10_001) if (pow(2, n, n) + 1) % n == 0)


@task("How many positive integers n <= 100000 have the property that n^2 has no repeated decimal digit?", "hard")
def _():
    return sum(1 for n in range(1, 100_001) if len(set(str(n * n))) == len(str(n * n)))


@task(
    "A frog starts at 0 on the number line. Each jump moves it forward 1 or 2 with probability 1/2 each, independently. "
    "The probability that the frog lands on 10 at some point without ever landing on 5 is m/n in lowest terms. "
    "Find m + n.", "hard")
def _():
    p = [Fraction(0)] * 11
    p[0] = Fraction(1)
    for x in range(1, 11):
        p[x] = 0 if x == 5 else (p[x - 1] + (p[x - 2] if x >= 2 else 0)) / 2
    return p[10].numerator + p[10].denominator


@task("How many subsets of {1, 2, ..., 12} (including the empty set) contain no two elements that differ by 2 or by 3?",
      "hard")
def _():
    return sum(1 for m in range(1 << 12)
               if not any(m >> i & 1 and m >> (i + d) & 1 for d in (2, 3) for i in range(12 - d)))


@task("How many ordered quadruples (a, b, c, d) of integers with 1 <= a, b, c, d <= 12 satisfy ab ≡ cd (mod 12)?", "hard")
def _():
    from collections import Counter
    prods = Counter(a * b % 12 for a in range(1, 13) for b in range(1, 13))
    return sum(v * v for v in prods.values())


@task("What is the largest positive integer that cannot be written as 9a + 13b + 17c with a, b, c non-negative integers?",
      "hard")
def _():
    reach = [False] * 1000
    reach[0] = True
    for n in range(1, 1000):
        reach[n] = any(n >= k and reach[n - k] for k in (9, 13, 17))
    return max(n for n in range(1000) if not reach[n])


@task(
    "A lattice path from (0, 0) to (6, 6) uses steps (1, 0), (0, 1) and (1, 1). How many such paths never pass "
    "through a point (x, y) with y > x, and do not pass through the point (3, 3)?", "hard")
def _():
    ways = {(0, 0): 1}
    for x in range(7):
        for y in range(7):
            if (x, y) == (0, 0):
                continue
            if y > x or (x, y) == (3, 3):
                ways[(x, y)] = 0
                continue
            ways[(x, y)] = ways.get((x - 1, y), 0) + ways.get((x, y - 1), 0) + ways.get((x - 1, y - 1), 0)
    return ways[(6, 6)]


def main():
    out = Path(__file__).resolve().parents[1] / "math.jsonl"
    with out.open("w") as f:
        for k, (prompt, fn, tier) in enumerate(TASKS, 1):
            row = {"id": f"math-{k:03d}", "category": "math", "grader": "math", "tier": tier,
                   "prompt": prompt + SUFFIX, "answer": str(fn()), "source": SOURCE}
            f.write(json.dumps(row) + "\n")
            print(row["id"], row["answer"])
    print(f"{len(TASKS)} tasks -> {out}")


if __name__ == "__main__":
    main()
