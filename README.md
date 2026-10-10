# Checkpoint admission tradeoffs on a hybrid 27B

A measured engineering study on an M4 Max with 36 GiB, using a Q4 hybrid model
labelled Qwen3.8-27B and Splash/DFlash2. This repository preserves source patches,
synthetic prompts, individual observations and offline validators—including
negative results. It does not claim a new general checkpoint algorithm, universal
output identity, increased intelligence or a globally fastest runtime.

**Read the [updated technical article](controlled/ARTICLE.md),
[controlled evidence](controlled/README.md), and [prior-art review](PRIOR_ART.md).**

## Latest controlled evidence

Each experiment has 315 measured requests, 21 warmups and seven randomized blocks.
Every arm within an experiment uses the same binary, model, workloads and native
25 GiB memory ceiling. Captures and cold priming count in complete-block latency.

| Experiment | Comparison | Median paired latency reduction | Interpretation |
|---|---|---:|---|
| Initial | Original planner vs original heuristic | 8.66% | Below declared 10%; two differing Python outputs; cold regression |
| Initial | Original planner vs stock checkpoint policy | 23.76% | Same tuned binary; not the released stock executable |
| Final | Conservative simple vs original heuristic | 6.18% | See per-family costs and memory, not a universal gain |
| Final | Conservative planner vs conservative simple | -0.72% | Declared complexity rule did not pass |

The final admission rule avoids speculative captures on unseen short single-turn
prompts. A simple selector without fitted costs, overlap learning or DP provides
the stronger baseline. Exact output matches in the final three-way comparison:
**105/105**. This is corpus-specific, not a numerical
identity guarantee. The [initial output differences](controlled/original/REPORT.md)
remain documented rather than erased.

The simpler policy is the useful experimental baseline here, not a proven
universal winner: the planner's difference interval includes zero. The simple
policy improves multi-turn editing sequences by 25.04% but slows the short 1K sequence
by 5.74% and unrelated cold sequences by 0.66%. Peak sampled family footprint
is about 0.92 GiB higher than the original heuristic. See the full tradeoffs
before adopting either option. The tested patch was not installed in production.

The target's configuration declares `qwen3_5`; its product label alone does not
establish a different architecture or verified training provenance. Exact remote
target revision remains unverified. Model digests and tokenizer checks are in
[model metadata](controlled/model-metadata.json). The build reuses pinned archive
objects and stock Metal shaders; clean-source equivalence is not established.

## Reproduce and inspect

```sh
python3 verify.py
```

Python 3.10+ and a C++20 compiler are sufficient for offline checks. They verify
artifact hashes, raw outputs/counts/order, counter consistency, recomputed paired
statistics, malformed streams, timing boundaries and native policy CPU tests.
They contact no inference service and execute no generated model code.

[Controlled replay instructions](controlled/README.md#replay-on-an-existing-isolated-service)
explain fresh-worker boundaries, mode selection, timing and instrumentation.
The [final patch](controlled/final/05-conservative-admission.patch) follows the
historical pinned patch chain; it is not a current-upstream or universally safe
drop-in release. No production configuration is distributed or silently changed.

## Historical evidence

- [Initial heuristic study](technical-article.md): 98 measured requests.
- [Earlier planner study](semantic/README.md): 96 measured requests; fixed order
  and differing binaries limit small-effect attribution.
- [Full 1K–64K benchmark](historical/full-benchmark/README.md): separate setup and
  timing boundaries; do not multiply its speedups with these policy results.
- [ML Drift prototype](secondary/drift/README.md), [architecture review](architecture-review.md),
  [claim reconciliation](CLAIM_RECONCILIATION.md), [patch provenance](PATCHES.md).

Broad novelty implications are withdrawn: semantic anchors, cost-aware hybrid
caching and sparse-placement dynamic programming have substantial
[prior art](PRIOR_ART.md). The contribution is inspectable integration and a
controlled comparison of its benefits, costs and simpler alternatives.

No weights, native binaries, private conversations, credentials or production
configuration are distributed. The ZIP in artifacts/ is the historical first
publication; GitHub's current source archive represents this revision.
