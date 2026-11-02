---
title: Beam Effort Curve
emoji: 📈
colorFrom: indigo
colorTo: blue
sdk: gradio
app_file: app.py
pinned: false
license: apache-2.0
short_description: How much reasoning effort does Reflection's Beam need?
hf_oauth: true
hf_oauth_scopes:
  - inference-api
---

# Beam Effort Curve

Accuracy, output tokens and latency for Reflection's Beam-1.0-501B-A23B at all five `reasoning_effort` levels, on 125 tasks written after its knowledge cutoff.

**Headline:** `high` for reasoning and `low` for everything else matches `max` accuracy (95.7%) with 64% of the output tokens. The `beam_autoeffort` wrapper applies this rule to any OpenAI-compatible client.

Tabs: Curves, Router, Try it (sign in; calls use your own Inference Providers credits), Overthinking, Findings.
