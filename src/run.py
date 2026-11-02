"""Run tasks × effort levels × samples and append raw rows to results/<run_id>.jsonl.

Resumable: rows already in the file (by task, effort, sample, variant) are skipped,
so a crashed or rate-limited run can be restarted with the same command.

    python -m src.run --run-id pilot --limit 2
    python -m src.run --run-id full-2026-10-27 --samples 3 --token-budget 900000
    python -m src.run --run-id ablation-ollama --backend ollama --categories tools --efforts low high --samples 3 --preserve-thinking both
"""

import argparse
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from tqdm import tqdm

from .client import ALLOWANCE_EXHAUSTED, EFFORTS, assistant_message, chat

TASKS_DIR = Path("tasks")
RESULTS_DIR = Path("results")
MAIN_RUN = "full-2026-10-27"  # the benchmark; analyze and router default to it
MAX_TOOL_TURNS = 8


def load_tasks(categories=None, limit=None, tier=None):
    tasks = []
    for path in sorted(TASKS_DIR.glob("*.jsonl")):
        if path.name.startswith("_"):  # scratch files, not part of the benchmark
            continue
        with path.open() as f:
            tasks += [json.loads(line) for line in f if line.strip()]
    if categories:
        tasks = [t for t in tasks if t["category"] in categories]
    if tier:
        tasks = [t for t in tasks if t.get("tier", "core") == tier]
    if limit:
        # take the first `limit` per category so a pilot covers every category
        seen, picked = {}, []
        for t in tasks:
            seen[t["category"]] = seen.get(t["category"], 0) + 1
            if seen[t["category"]] <= limit:
                picked.append(t)
        tasks = picked
    return tasks


def lookup_tool(task, name, arguments):
    """Canned tool output: first entry under tool_responses[name] whose `match` is a subset of the args."""
    for entry in task.get("tool_responses", {}).get(name, []):
        if all(arguments.get(k) == v for k, v in entry.get("match", {}).items()):
            return entry["output"]
    return {"error": f"no record found for {name} with {json.dumps(arguments)}"}


def run_single(task, effort, backend):
    messages = task.get("messages") or [{"role": "user", "content": task["prompt"]}]
    c = chat(messages, effort, backend=backend)
    return {**c.to_dict(), "turns": 1}


def run_tools(task, effort, backend, preserve_thinking):
    """Multi-turn loop: send canned tool outputs back until the model stops calling tools."""
    messages = list(task["messages"])
    calls, reasoning = [], []
    totals = {"prompt_tokens": 0, "completion_tokens": 0, "reasoning_tokens": 0, "latency_s": 0.0}
    c = None
    for turn in range(1, MAX_TOOL_TURNS + 1):
        c = chat(messages, effort, tools=task["tools"], backend=backend)
        for k in totals:
            totals[k] += getattr(c, k) or 0
        if c.reasoning:
            reasoning.append(c.reasoning)
        if c.error or not c.tool_calls:
            break
        messages.append(assistant_message(c, preserve_thinking))
        for tc in c.tool_calls:
            try:
                args, parse_error = json.loads(tc["arguments"] or "{}"), None
            except json.JSONDecodeError as e:
                args, parse_error = {}, str(e)
            calls.append({"name": tc["name"], "arguments": args, "raw_arguments": tc["arguments"], "parse_error": parse_error})
            output = {"error": f"could not parse arguments: {parse_error}"} if parse_error else lookup_tool(task, tc["name"], args)
            messages.append({"role": "tool", "tool_call_id": tc["id"], "content": json.dumps(output)})
    row = c.to_dict()
    row.update(totals, tool_calls=calls, reasoning="\n\n---\n\n".join(reasoning) or None, turns=turn)
    if row["reasoning_tokens"] == 0 and c.reasoning_tokens is None:
        row["reasoning_tokens"] = None
    return row


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--efforts", nargs="+", default=EFFORTS, choices=EFFORTS)
    parser.add_argument("--samples", type=int, default=1)
    parser.add_argument("--categories", nargs="+")
    parser.add_argument("--limit", type=int, help="max tasks per category")
    parser.add_argument("--tier", choices=["core", "hard"])
    parser.add_argument("--backend", default=os.getenv("BACKEND", "reflection"))
    parser.add_argument("--workers", type=int, default=4, help="keep below the beta rate limit")
    parser.add_argument("--preserve-thinking", choices=["on", "off", "both"], default="on")
    parser.add_argument("--token-budget", type=int, default=None,
                        help="stop starting new calls after this many output tokens (beta allowance: 1M/day)")
    args = parser.parse_args()

    RESULTS_DIR.mkdir(exist_ok=True)
    out = RESULTS_DIR / f"{args.run_id}.jsonl"
    done = set()
    if out.exists():
        with out.open() as f:
            for line in f:
                r = json.loads(line)
                if not r.get("error"):  # failed rows are retried
                    done.add((r["task_id"], r["effort"], r["sample"], r["variant"]))

    variants = {"on": [True], "off": [False], "both": [False, True]}[args.preserve_thinking]
    jobs = []
    for task in load_tasks(args.categories, args.limit, args.tier):
        is_tools = task["grader"] == "tools"
        for effort in args.efforts:
            for sample in range(args.samples):
                for preserve in variants if is_tools else [False]:
                    variant = ("preserve" if preserve else "drop") if is_tools else "default"
                    if (task["id"], effort, sample, variant) not in done:
                        jobs.append((task, effort, sample, preserve, variant))

    print(f"{len(jobs)} calls to make ({len(done)} already done) -> {out}")
    lock = threading.Lock()
    stop = threading.Event()
    used = {"tokens": 0}

    def work(job):
        if stop.is_set():
            return None
        task, effort, sample, preserve, variant = job
        try:
            row = run_tools(task, effort, args.backend, preserve) if task["grader"] == "tools" else \
                run_single(task, effort, args.backend)
        except Exception:
            stop.set()  # a bug would otherwise fail (and pay for) every queued call before the run exits
            raise
        if row["error"] and ALLOWANCE_EXHAUSTED in row["error"]:
            stop.set()  # every further call would fail until 00:00 UTC; don't record it
            return None
        row = {
            "run_id": args.run_id, "task_id": task["id"], "category": task["category"],
            "effort": effort, "sample": sample, "variant": variant,
            **row, "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        with lock:
            with out.open("a") as f:
                f.write(json.dumps(row) + "\n")
            used["tokens"] += row["completion_tokens"] or 0
            if args.token_budget and used["tokens"] >= args.token_budget:
                stop.set()
        return row

    errors = written = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for fut in tqdm(as_completed([pool.submit(work, j) for j in jobs]), total=len(jobs)):
            row = fut.result()
            if row is not None:
                written += 1
                errors += bool(row["error"])
    print(f"{written} rows written, {errors} errors, {used['tokens']:,} output tokens")
    if stop.is_set():
        print("stopped early (token budget reached or daily allowance exhausted); rerun the same command to continue")
    elif errors:
        print("rerun the same command to retry the errors")


if __name__ == "__main__":
    main()
