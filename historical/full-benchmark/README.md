# Historical full 27B benchmark — before the checkpoint fixes

This missing context is now exported from the earlier study. It is **not a new
benchmark of the semantic planner**. Dates, installed model labels, arm names,
cache counts, output lengths and settings remain per row. There are 563 saved
requests, 535 unique measured requests, 25 primary raw workload/context cells
with seven repetitions each, and twenty primary 8K follow-ups.

`python3 historical/full-benchmark/analyze.py` independently verifies all 68
group counts and TTFT, E2E and backend-decode means/medians/p95 against the saved
summary, hashes every output and checks coverage. Actual input recount receipts
are included; a fresh recount requires the exact historical tokenizer. The fixed
corpus and corrected/long-copy supplements are included. The seven invalid
original long-edit fixtures are retained and excluded explicitly.

## Why this changes the interpretation

For the selected installed uncensored Splash preset, genuinely new English
output at ~1K input measured 35.89 tok/s, Arabic 26.39, technical explanation
37.57 and Python 78.13. The five-domain installed-preset score favored Splash
by 17.7% over the tested TensorFold preset, but draft precision and runtime
settings differed. This is not a matched kernel or public-runtime ranking.

The generation tests use **warmed reference prefixes**. Their sub-second TTFT
must not be presented as time to process an entirely cold long prompt.

| Approximate context | Cold TTFT median | Exact-repeat TTFT | Changed-suffix TTFT |
|---|---:|---:|---:|
| 1K | 3.447s | 0.314s | 0.317s |
| 8K | 27.284s | 0.322s | 0.335s |
| 16K | 56.784s | 0.330s | 0.356s |
| 32K | 123.498s | 0.347s | 0.406s |
| ~64K (64,528 cold input tokens) | 281.506s | 0.379s | 0.486s |

The twenty primary 8K cached follow-ups measured 334.95ms p50 / 335.40ms p95.
These are historical pre-fix fixtures; they do not contradict a different
first-branch workload missing the usable checkpoint. Cache state and branching
structure matter as much as context length.

At ~32K/~64K, warmed-prefix English decoding was 28.96/25.69 tok/s; Arabic
23.44/19.04; Python 68.97/58.82. New Python with only 104 input tokens measured
91.44 tok/s over seven requests. DFlash2 is included in all these speeds.
Unassisted target-only decoding was not measured.

Copying is separate: short Python copying measured 128.20 tok/s, with 7/7 matching
after outer-whitespace trimming but 0/7 byte-exact. Short document copying was
120.36 tok/s and 7/7 byte-exact. Long document copying was 116.56 tok/s, 7/7 after
trimming, 0/7 byte-exact. Corrected code edits were content-correct in 6/7.
Draft acceptance for copying was about 98–100%, versus approximately 19% for
English, 11% for Arabic and 60% for Python generation near 1K context.

The historical narrow Hermes harness had tools disabled: paired overhead was
3.93ms without reasoning and 6.92ms with low reasoning. First model output
arrived around 0.368s with low reasoning, but visible answer content around
3.455s. These saved harness summaries exclude Telegram, remote transport and
private production tools/history. They are not full deployed-agent latency.
The exported validator does not re-execute that Hermes harness.

## Quality and limitations

35/35 selected raw JSON responses parsed, but 0/35 met every instruction,
including exact 20-word notes. Python syntax passed 31/35 raw cases, with output
truncation contributing failures. Model quality cannot be inferred from speed.
Peak sampled family memory was 25.55 GiB and swap stayed zero. Exact GPU
clocks/temperatures were not recorded. The original token-label and reused-binary
provenance caveats in the main study apply.

The summary is a historical record; client chunk-derived decode estimates and
its partial-counter aggregates are not promoted as headline metrics. Use the
backend rate with actual lengths, and require complete draft counters for new
analysis. The current verifier recomputes latencies/rates, not every original
quality or backend-tokenization audit.

A setup error truncated an old 176.8 MB **isolated benchmark** KV-cache file,
which could not be recovered. Production caches, weights and configuration
were reported preserved. This incident qualifies the original broad restoration
statement; no such destructive step is part of the exported analysis or client.
