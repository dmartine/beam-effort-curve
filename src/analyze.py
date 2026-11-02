"""Summary tables (bootstrap CIs over tasks), overthinking cases, and charts.

    python -m src.analyze                            # the main run
    python -m src.analyze --ablation ablation-ollama # also the preserve_thinking ablation

Writes results/summary.csv, results/overthinking.csv, results/charts/*.html,
and with --ablation, results/ablation.csv.
"""

import argparse

import numpy as np
import pandas as pd

from . import charts
from .client import EFFORTS
from .run import MAIN_RUN, RESULTS_DIR, load_tasks

N_BOOT = 2000


def bootstrap_ci(per_task, rng):
    """95% CI for mean accuracy, resampling tasks (not rows)."""
    values = per_task.to_numpy()
    if len(values) < 2:
        return np.nan, np.nan
    means = rng.choice(values, size=(N_BOOT, len(values)), replace=True).mean(axis=1)
    return np.percentile(means, 2.5), np.percentile(means, 97.5)


def summarize(df, keys):
    rng = np.random.default_rng(0)
    rows = []
    for key, g in df.groupby(keys + ["effort"]):
        per_task = g.groupby("task_id")["correct"].mean()  # average samples within a task first
        lo, hi = bootstrap_ci(per_task, rng)
        rows.append({
            **dict(zip(keys + ["effort"], key)), "acc": per_task.mean(), "ci_lo": lo, "ci_hi": hi,
            "tokens_mean": g["completion_tokens"].mean(), "tokens_median": g["completion_tokens"].median(),
            "latency_median": g["latency_s"].median(), "truncated": g["truncated"].mean(), "tasks": len(per_task),
        })
    table = pd.DataFrame(rows)
    table["effort"] = pd.Categorical(table["effort"], EFFORTS, ordered=True)
    return table.sort_values(keys + ["effort"]).reset_index(drop=True)


def overthinking(df):
    """Tasks where a higher effort level did worse than a lower one (per-task accuracy over samples)."""
    acc = df.pivot_table(index="task_id", columns="effort", values="correct", aggfunc="mean")
    acc = acc[[e for e in EFFORTS if e in acc.columns]]
    rows = []
    for task_id, r in acc.iterrows():
        best = r.idxmax()  # lowest level reaching the task's best accuracy
        worse = [e for e in r.index[r.index.get_loc(best) + 1:] if r[e] < r[best]]
        if worse:
            rows.append({"task_id": task_id, "best_effort": best, "best_acc": r[best], "worse_at": ",".join(worse),
                         **{f"acc_{e}": r[e] for e in r.index}})
    cols = ["task_id", "best_effort", "best_acc", "worse_at"] + [f"acc_{e}" for e in acc.columns]
    return pd.DataFrame(rows, columns=cols)  # keep the header even with no cases


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", nargs="+", default=[MAIN_RUN])
    parser.add_argument("--ablation", help="run id of a --preserve-thinking both run")
    args = parser.parse_args()

    graded = pd.read_parquet(RESULTS_DIR / "graded.parquet")
    if args.ablation:
        ab = graded[graded["run_id"] == args.ablation].groupby(["effort", "variant"]).agg(
            acc=("correct", "mean"), n=("correct", "size"), tokens=("completion_tokens", "mean"), turns=("turns", "mean"))
        print(ab.round(3).to_string(), "\n")
        ab.to_csv(RESULTS_DIR / "ablation.csv")
    df = graded[graded["run_id"].isin(args.runs) & (graded["variant"] != "drop")].copy()
    tiers = {t["id"]: t.get("tier", "core") for t in load_tasks()}
    df["tier"] = df["task_id"].map(tiers)

    table = summarize(df, ["category"])
    by_tier = summarize(df, ["category", "tier"])
    print(table.round(3).to_string(index=False))
    table.to_csv(RESULTS_DIR / "summary.csv", index=False)
    by_tier.to_csv(RESULTS_DIR / "summary_by_tier.csv", index=False)

    over = overthinking(df)
    over.to_csv(RESULTS_DIR / "overthinking.csv", index=False)
    print(f"\n{len(over)} tasks where higher effort did worse than a lower level")

    out = RESULTS_DIR / "charts"
    out.mkdir(exist_ok=True)
    for mode in ("light", "dark"):
        charts.pareto(table, mode).write_html(out / f"pareto-{mode}.html", include_plotlyjs="cdn")
        charts.by_effort(table, "acc", mode, "Accuracy by effort level (95% CI over tasks)", "Accuracy (%)",
                         ci=True, percent=True).write_html(out / f"accuracy-{mode}.html", include_plotlyjs="cdn")
        charts.by_effort(table, "tokens_mean", mode, "Mean completion tokens by effort level", "Tokens"
                         ).write_html(out / f"tokens-{mode}.html", include_plotlyjs="cdn")
    print(f"charts written to {out}")


if __name__ == "__main__":
    main()
