# Findings

Beam-1.0-501B-A23B on Reflection's API, all five `reasoning_effort` levels, 125 tasks written after the model's knowledge cutoff, 1,775 graded runs (October 27 to November 1, 2026).

## Headline

**Use `high` for reasoning and `low` for everything else: the same accuracy as `max` with 64% of the output tokens.**

| Strategy | Accuracy | Mean output tokens | Tokens vs. `max` |
|---|---|---|---|
| fixed `low` | 87.5% | 776 | 19% |
| fixed `medium` | 93.3% | 1,747 | 42% |
| fixed `high` | 95.5% | 3,368 | 80% |
| fixed `xhigh` | 95.5% | 4,079 | 97% |
| fixed `max` | 95.7% | 4,185 | 100% |
| **`high` for reasoning, `low` otherwise** | **95.7%** | **2,671** | **64%** |

This rule was set on October 28 from a low-effort pilot, before the full run, and the full data confirmed it rather than producing it. A router that learns the rule from the data, cross-validated over tasks so no task is scored by a policy that saw it, picks `high` for reasoning and `low` for tool calling in all five folds; for code and structured output, where the levels differ by a point or two, its choice varies between folds. It scores 95.5% at 2,909 tokens. `beam_autoeffort` applies it to any OpenAI-compatible client, choosing from what is visible before the call: attached tools, a JSON response format, the prompt text.

## What effort buys

- **Reasoning is the only place effort matters.** On math, accuracy goes from 64% at `low` to 84% at `medium` and 93% at `high`. On the hard tier, `medium` reaches 70% and `high` 90%, so `medium` is not a safe default for hard problems.
- **`xhigh` and `max` never beat `high`.** On core math they score lower (89% and 91% against 95%) because 8 to 9% of their runs hit the 32k-token cap without answering. On hard math they tie `high` at 90% while spending about 14k tokens per run against 9k.
- **Code, tool calling and structured output are flat.** Code is 95 to 98% at every level, structured output 98 to 100%, tool schemas 90% (one task is never solved). On non-reasoning requests `low` uses 539 tokens against 1,826 at `max`, 3.4 times fewer, at 96.7% against 97.8%.
- **Tool calling is at the ceiling at every level** (95.6 to 100%, with `low` at 100%). More thinking did not make tool use more reliable.

## Overthinking

13 tasks score lower at a higher level than at a lower one. Most are single-sample noise, but a few are not:

- **math-017** (count 3x3 matrices over {0, 1, 2} with determinant 1): `low` answers in about 1k tokens; from `high` up the model starts enumerating by hand and hits the 32k cap in 7 of 9 runs. **math-019** never gets solved and also runs to the cap at `xhigh` and `max`.
- Runaway generations are the real cost of high effort: a run that hits the cap costs 32k tokens, takes 3 to 7 minutes, and returns nothing.

## Does sent-back reasoning matter?

Reflection's API rejects (400) any multi-turn request whose earlier assistant messages lack `reasoning_content`. A probe with a code word hidden only in that field shows the model **reads it within a tool-calling loop** (recalled 3 of 3) and **ignores it after a new user message** (0 of 3), on both Reflection and Ollama Cloud.

An ablation over the 30 tool-calling tasks (low and high, 3 samples, 360 runs, run on Ollama Cloud) replaced the earlier reasoning with a placeholder: **no accuracy difference** (97.8% vs. 98.9% at `low`, 100% vs. 98.9% at `high`). At `high`, dropping it costs slightly more turns (3.47 vs. 3.34) and tokens (670 vs. 641). These tasks sit near the ceiling, so the finding is that sent-back reasoning doesn't matter for tool tasks of this difficulty, not that it never matters.

## API notes

- **The default effort is not `medium`.** With `reasoning_effort` omitted, token use matched `xhigh`/`max` on Reflection and `max` on Ollama, not the `medium` stated for the chat template.
- **Effort passes through HF Inference Providers (Baseten).** On the cube-coloring problem, `low` used 2,289 completion tokens (4 s) and `max` 13,360 (28 s), both correct. Reflection's API used about 4k at `max` on the same problem; that is one run, not a measured difference between providers.
- **Providers differ.** Reflection rejects unknown effort levels and missing `reasoning_content` with 400; Ollama Cloud accepts both silently, returns reasoning as `reasoning` rather than `reasoning_content`, ignores `response_format: json_object`, and doesn't report reasoning tokens. `with_reasoning()` in the wrapper handles both.
- **Beta limits:** 1,000,000 output tokens per organization per day, plus a request rate limit that stalls multi-turn workloads in bursts.

## Method and limitations

- 125 tasks: 35 math (25 core, 10 hard), 35 code, 30 tool calling, 10 tool schemas, 15 structured output. All written for this benchmark after the model's June 30, 2026 knowledge cutoff, each verified by its builder (brute-force answers, reference solutions run against tests).
- 3 samples per task and level, except hard math (1 sample, to fit the daily token allowance). Temperature 0.7, top_p 0.99 (the model card's eval settings), 32k max output tokens.
- Accuracy is averaged over samples within each task, then over tasks; 95% confidence intervals bootstrap over tasks. With 10 to 35 tasks per category, the intervals are wide; differences of a point or two between levels are not significant.
- The wrapper sorts requests by simple signals: attached tools, a JSON response format, JSON Schema wording, a fenced Python block or a prompt starting "Write `". These match this benchmark's prompts; anything it doesn't recognize is treated as reasoning and gets `high`, which costs tokens but not accuracy.
- One provider for the main benchmark (Reflection's API). Ollama Cloud was used only for the ablation and the wrapper test, never mixed into the main results.
