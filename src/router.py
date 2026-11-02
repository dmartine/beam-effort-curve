"""Effort router: pick a reasoning-effort level per request, using only what is
visible before the call (the prompt text and whether tools are attached).

Policy: route each request to a bucket, then use the cheapest effort level whose
accuracy in that bucket is within `tolerance` of the best level. Scored with
k-fold cross-validation over tasks, so every task is routed by a policy that
never saw it, and compared against every fixed effort level.

    python -m src.router                 # the main run
    python -m src.router --tolerance 0.01

Also scores the wrapper's shipped policy (beam_autoeffort/policy.json) on all
data and writes a tolerance sweep of the cross-validated router.
"""

import argparse
import json

import numpy as np
import pandas as pd

from beam_autoeffort import bucket, load_policy

from .client import EFFORTS
from .run import MAIN_RUN, RESULTS_DIR, load_tasks


def per_task_table(df, tasks):
    """One row per (task, effort): mean accuracy over samples and mean tokens."""
    g = df.groupby(["task_id", "effort"]).agg(acc=("correct", "mean"), tokens=("completion_tokens", "mean")).reset_index()
    g["bucket"] = g["task_id"].map(lambda t: bucket(tasks[t]))
    return g


def learn_policy(table, tolerance):
    policy = {}
    for b, g in table.groupby("bucket"):
        acc = g.groupby("effort")["acc"].mean().reindex(EFFORTS).dropna()
        best = acc.max()
        policy[b] = next(e for e in EFFORTS if e in acc.index and acc[e] >= best - tolerance)
    return policy


def evaluate(table, tolerance, folds=5, seed=0):
    rng = np.random.default_rng(seed)
    task_ids = np.array(sorted(table["task_id"].unique()))
    rng.shuffle(task_ids)
    fold_of = {t: i % folds for i, t in enumerate(task_ids)}
    routed, policies = [], []
    for k in range(folds):
        train = table[table["task_id"].map(fold_of) != k]
        test = table[table["task_id"].map(fold_of) == k]
        policy = learn_policy(train, tolerance)
        policies.append(policy)
        chosen = test[test["effort"] == test["bucket"].map(policy)]
        routed.append(chosen)
    routed = pd.concat(routed)
    rows = [{"strategy": f"fixed: {e}", "acc": table[table.effort == e]["acc"].mean(),
             "tokens": table[table.effort == e]["tokens"].mean()} for e in EFFORTS if e in set(table.effort)]
    rows.append({"strategy": "router (cross-validated)", "acc": routed["acc"].mean(), "tokens": routed["tokens"].mean()})
    return pd.DataFrame(rows), learn_policy(table, tolerance), policies


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", nargs="+", default=[MAIN_RUN])
    parser.add_argument("--tolerance", type=float, default=0.03, help="accuracy the router may give up per bucket")
    args = parser.parse_args()

    df = pd.read_parquet(RESULTS_DIR / "graded.parquet")
    df = df[df["run_id"].isin(args.runs) & (df["variant"] != "drop")]
    tasks = {t["id"]: t for t in load_tasks()}
    table = per_task_table(df, tasks)
    missing = table.groupby("task_id")["effort"].nunique() < len(EFFORTS)
    if missing.any():
        print(f"note: {missing.sum()} tasks lack some effort levels; they are scored only where present")

    results, policy, fold_policies = evaluate(table, args.tolerance)
    shipped = table[table["effort"] == table["bucket"].map(load_policy())]
    results.loc[len(results)] = {"strategy": "wrapper policy (beam_autoeffort)", "acc": shipped["acc"].mean(),
                                 "tokens": shipped["tokens"].mean()}
    best_fixed = results[results.strategy.str.startswith("fixed")].sort_values(["acc", "tokens"], ascending=[False, True]).iloc[0]
    print(results.round(3).to_string(index=False))
    print(f"\npolicy on all data: {policy}")
    for _, r in results.iloc[-2:].iterrows():
        print(f"{r.strategy} vs best fixed level ({best_fixed.strategy}): accuracy {r.acc - best_fixed.acc:+.3f}, "
              f"tokens {r.tokens / best_fixed.tokens:.0%} of best fixed")
    results.to_csv(RESULTS_DIR / "router_eval.csv", index=False)
    sweep = pd.DataFrame([{"tolerance": tol, **evaluate(table, tol)[0].iloc[-1][["acc", "tokens"]].to_dict(),
                           "policy": json.dumps(learn_policy(table, tol))} for tol in (0, 0.01, 0.02, 0.03, 0.05)])
    sweep.to_csv(RESULTS_DIR / "router_sweep.csv", index=False)
    (RESULTS_DIR / "router_policy.json").write_text(json.dumps({"tolerance": args.tolerance, "policy": policy,
                                                                "fold_policies": fold_policies}, indent=2))


if __name__ == "__main__":
    main()
