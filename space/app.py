"""Beam Effort Curve: Hugging Face Space.

Tabs: Curves, Router, Try it (visitor signs in with HF and pays with their own
credits), Overthinking, Findings. Data files in data/ are written by
`python -m src.export_space` from the benchmark repo.
"""

import json
import time
from pathlib import Path

import gradio as gr
import pandas as pd
from openai import OpenAI

import charts
from beam_autoeffort import POLICY_FILE, bucket
from charts import EFFORTS

DATA = Path(__file__).parent / "data"
MODEL = "reflection/Beam-1.0-501B-A23B:baseten"


def load(name):
    path = DATA / name
    try:
        df = pd.read_csv(path)
    except (FileNotFoundError, pd.errors.EmptyDataError):
        return pd.DataFrame()
    if "effort" in df:
        df["effort"] = pd.Categorical(df["effort"], EFFORTS, ordered=True)
    return df


SUMMARY = load("summary.csv")
OVER = load("overthinking.csv")
ROUTER_EVAL = load("router_eval.csv")
ROUTER_SWEEP = load("router_sweep.csv")
# the same policy file the drop-in wrapper ships, so the tab shows exactly what auto_effort does
POLICY = json.loads(POLICY_FILE.read_text())
FINDINGS = (DATA / "findings.md").read_text() if (DATA / "findings.md").exists() else "Findings are being written."

THEME_JS = "() => document.body.classList.contains('dark') ? 'dark' : 'light'"


def curves(mode):
    mode = mode if mode in ("light", "dark") else "light"
    return (charts.pareto(SUMMARY, mode),
            charts.by_effort(SUMMARY, "acc", mode, "Accuracy by effort level (95% CI over tasks)", "Accuracy (%)",
                             ci=True, percent=True),
            charts.by_effort(SUMMARY, "tokens_mean", mode, "Mean completion tokens by effort level", "Tokens"))


BUCKET_CATEGORY = {"tools": "tools", "structured": "structured", "code": "code", "reasoning": "math"}


def route(prompt, has_tools):
    if not prompt.strip():
        return "Paste a prompt to get a recommendation.", None
    b = bucket({"prompt": prompt, "tools": [{}] if has_tools else None})  # same rules as the drop-in wrapper
    effort = POLICY["policy"][b]
    rows = SUMMARY[SUMMARY["category"] == BUCKET_CATEGORY[b]][["effort", "acc", "ci_lo", "ci_hi", "tokens_mean"]].copy()
    rows["acc"] = (rows["acc"] * 100).round(1)
    rows["95% CI"] = rows.apply(lambda r: f"{r.ci_lo * 100:.0f}–{r.ci_hi * 100:.0f}", axis=1)
    rows["tokens_mean"] = rows["tokens_mean"].round(0).astype(int)
    rows = rows.rename(columns={"acc": "accuracy %", "tokens_mean": "mean tokens"})[["effort", "accuracy %", "95% CI", "mean tokens"]]
    md = (f"**Bucket:** {b}  \n**Recommended effort:** `{effort}`  \n"
          f"Chosen as the cheapest level within {POLICY['tolerance'] * 100:.0f} point(s) of the best "
          f"accuracy for this kind of request in the benchmark.")
    return md, rows


def try_it(prompt, oauth_token: gr.OAuthToken | None):
    if oauth_token is None:
        msg = "Sign in with Hugging Face first. Calls are billed to your own Inference Providers credits."
        return msg, msg, ""
    if not prompt.strip():
        return "", "", "Enter a prompt."
    client = OpenAI(base_url="https://router.huggingface.co/v1", api_key=oauth_token.token)
    out, stats = [], []
    for effort in ("low", "max"):
        start = time.monotonic()
        try:
            r = client.chat.completions.create(model=MODEL, messages=[{"role": "user", "content": prompt}],
                                               max_tokens=16384, extra_body={"reasoning_effort": effort})
            u = r.usage
            out.append(r.choices[0].message.content or "")
            stats.append(f"{effort}: {u.completion_tokens:,} completion tokens, {time.monotonic() - start:.1f}s")
        except Exception as e:
            out.append(f"Error: {e}")
            stats.append(f"{effort}: error")
    return out[0], out[1], " · ".join(stats)


with gr.Blocks(title="Beam Effort Curve") as demo:
    mode = gr.State("light")
    gr.Markdown("# Beam Effort Curve\nHow much reasoning does Reflection's Beam (501B MoE, 23B active) need? "
                "Accuracy, tokens and latency across all five effort levels, on 125 verified tasks.")
    with gr.Tab("Curves"):
        pareto_plot = gr.Plot()
        acc_plot = gr.Plot()
        tok_plot = gr.Plot()
        gr.Markdown("### Table view")
        gr.Dataframe(SUMMARY.round(3) if not SUMMARY.empty else None, interactive=False)
    with gr.Tab("Router"):
        gr.Markdown("Paste a prompt. The router sees only what is visible before the call (the text, and whether "
                    "tools are attached) and recommends an effort level. Cross-validated against fixed levels below.")
        prompt_in = gr.Textbox(lines=6, label="Prompt")
        tools_in = gr.Checkbox(label="Tools are attached to this request")
        route_btn = gr.Button("Recommend effort", variant="primary")
        route_md = gr.Markdown()
        route_table = gr.Dataframe(interactive=False)
        gr.Markdown("### Router vs. fixed effort levels")
        gr.Dataframe(ROUTER_EVAL.round(3) if not ROUTER_EVAL.empty else None, interactive=False)
        gr.Markdown("### Tolerance sweep\nHow much accuracy the learned router may give up per bucket, and what it buys.")
        gr.Dataframe(ROUTER_SWEEP.round(3) if not ROUTER_SWEEP.empty else None, interactive=False)
        route_btn.click(route, [prompt_in, tools_in], [route_md, route_table])
    with gr.Tab("Try it"):
        gr.Markdown("Run your own prompt at `low` and `max` side by side through HF Inference Providers. "
                    "Sign in so the calls use your own credits.")
        gr.LoginButton()
        try_prompt = gr.Textbox(lines=4, label="Prompt")
        try_btn = gr.Button("Run at low and max", variant="primary")
        try_stats = gr.Markdown()
        with gr.Row():
            latex = [{"left": "\\[", "right": "\\]", "display": True}, {"left": "\\(", "right": "\\)", "display": False}]
            low_out = gr.Markdown(label="low", latex_delimiters=latex, container=True)
            max_out = gr.Markdown(label="max", latex_delimiters=latex, container=True)
        try_btn.click(try_it, [try_prompt], [low_out, max_out, try_stats])
    with gr.Tab("Overthinking"):
        gr.Markdown("Tasks where a higher effort level scored worse than a lower one (accuracy averaged over samples: 3 per level, 1-2 for hard math).")
        gr.Dataframe(OVER if not OVER.empty else None, interactive=False)
    with gr.Tab("Findings"):
        gr.Markdown(FINDINGS)

    demo.load(None, None, mode, js=THEME_JS).then(curves, mode, [pareto_plot, acc_plot, tok_plot])

if __name__ == "__main__":
    demo.launch()
