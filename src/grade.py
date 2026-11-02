"""Grade raw rows in results/*.jsonl and write results/graded.parquet.

Rows for the same (run, task, effort, sample, variant) can repeat when a run
was resumed after errors; the last successful row wins.

    python -m src.grade                  # every run
    python -m src.grade --runs pilot
"""

import argparse
import json

import pandas as pd

from .graders import code, math, structured, tools
from .run import MAIN_RUN, RESULTS_DIR, load_tasks

GRADERS = {"math": math.grade, "code": code.grade, "tools": tools.grade, "structured": structured.grade}
KEY = ["run_id", "task_id", "effort", "sample", "variant"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", nargs="+", help="run ids (default: all non-smoke runs)")
    args = parser.parse_args()

    paths = [RESULTS_DIR / f"{r}.jsonl" for r in args.runs] if args.runs else [
        p for p in RESULTS_DIR.glob("*.jsonl") if not p.name.startswith("smoke-")
    ]
    rows = [json.loads(line) for p in paths for line in p.open() if line.strip()]
    if not rows:
        raise SystemExit("no result rows found")
    df = pd.DataFrame(rows)
    df["_ok"] = df["error"].isna()
    df = df.sort_values(["_ok", "ts"]).drop_duplicates(KEY, keep="last").drop(columns="_ok")
    df = df.astype(object).where(df.notna(), None)  # NaN would read as truthy in `if row["error"]`

    tasks = {t["id"]: t for t in load_tasks()}
    graded = []
    for row in df.to_dict("records"):
        task = tasks[row["task_id"]]
        if row["error"]:
            g = {"correct": False, "format_ok": None}
        else:
            g = GRADERS[task["grader"]](task, row)
        row["truncated"] = row.get("finish_reason") == "length"
        row["grade"] = json.dumps(g)
        row["correct"] = bool(g["correct"])
        row["format_ok"] = g.get("format_ok")
        row["tool_calls"] = json.dumps(row.get("tool_calls"))
        graded.append(row)

    out = pd.DataFrame(graded)
    out.to_parquet(RESULTS_DIR / "graded.parquet", index=False)
    summary = out[(out["run_id"] == MAIN_RUN) & (out["variant"] != "drop")].groupby(["category", "effort"]).agg(
        acc=("correct", "mean"), n=("correct", "size"), tokens=("completion_tokens", "median"),
        truncated=("truncated", "mean"), errors=("error", lambda s: s.notna().sum()),
    )
    print(summary.round(3).to_string())
    print(f"\nwrote {len(out)} rows to {RESULTS_DIR / 'graded.parquet'}")


if __name__ == "__main__":
    main()
