# A checkpoint can save seconds—or create an expensive tail

On a 36 GiB M4 Max, a changed question after a shared 1K prefix took 4.125 seconds
to produce its first token. Preserving a useful composite checkpoint reduced
that to 1.218 seconds in seven paired fixtures. The first request became slower:
4.131 → 4.635 seconds. Across prime, changed question and repeat, the median
paired saving was 2.416 seconds. That tradeoff is the subject of this work.

## Why a hit counter is not enough

Hybrid models combine attention KV with recurrent state. The attention prefix
alone cannot restore the recurrent state at an arbitrary earlier position.
Speculative decoding adds draft context that must agree with the same boundary.
Splash already supplies complete-state capture and exact prefix checks. The
engineering problem is choosing which additional boundaries deserve retention.

An earlier local rule captured the latest user boundary only after at least
2,048 reusable tokens. It fixed an 8K branch miss, but rejected useful smaller
branches. A hit-only learner would reinforce that rejection: without a retained
checkpoint, it never observes the hit that would justify creating one.

The controller instead observes exact longest-common token prefixes between
successive requests, including cache misses. It credits each outcome to the
previous request shape. Three bounded histories distinguish single-turn and
multi-turn patterns. The previous prompt buffer is capped at 65,536 uint32 tokens;
it and the learned histories stay in the engine, without an auxiliary model.

## Price the work actually executed

A checkpoint is not just a memory allocation. It splits prefill commands and
changes their dispatch sizes. On this profile, ≤128 rows use a register route,
129–511 use the middle GPU route, and 512+ qualify for the calibrated ANE split.
A deeper checkpoint can therefore be worse if it leaves an expensive short tail.

Draft cost is also nonlinear. Adjacent captures can continue the draft ring.
The planner charges `min(2048, distance)` between complete-state boundaries,
including mandatory recovery points. It does not charge a fresh full draft
window at every extra snapshot. A brute-force subset oracle uses an extracted
upstream draft-context planner to check this accounting independently.

The objective is:

```text
current target dispatch + current draft materialization
+ extra capture and queue interference
+ expected future replay/restore
+ optional retained-memory penalty
```

A bounded shortest path chooses the set jointly under state-count and byte
limits. Every future overlap is charged once, to its deepest selected reusable
predecessor. Mandatory native recovery/replay captures stay on every path.
Native identity, allocation and eviction checks still authorize actual reuse.

The current implementation uses measured capture/restore wall times and a
regularized nonnegative fit of whole-command time to target/draft rows. These
coefficients are estimates, sometimes underidentified, not isolated kernel
measurements. The native global eviction opportunity cost is not modeled, and
the deployed retention penalty is zero. “Optimal” means optimal under the supplied
forecast and cost model, not globally optimal serving.

## What makes this implementation worth sharing

Its useful combination is dispatch-size-aware placement, complete draft-state
accounting, learning uncensored by cache admission, joint rather than greedy
selection, and inspectable decision receipts. The source is small enough to
review; tests compare 3,000 generated problems against 75,821 exhaustive feasible
subsets. A bounded-history controller test covers unrelated traffic, reuse,
shape transitions and cost drift. Publication review additionally fixes malformed
geometry before alignment arithmetic.

The [decision ledger](DECISION_LEDGER.md) records 18 alternatives from available
local engineering history, including unsuccessful smaller draft windows and
unsafe numerical shortcuts. It is not a claim to have recovered every abandoned
idea in inference engineering. No new Metal arithmetic kernel is introduced.

## What the measurements do and do not say

The [full report](README.md) includes cold regressions, earlier-turn tail misses,
all individual requests and complete-sequence costs. The 8K follow-up pilot was
effectively unchanged. Three new 85-token Python outputs per arm showed
101.80 → 102.33 effective speculative tok/s, with identical 78.02% acceptance.
That is no evidence of a sustained decoding breakthrough.

The baseline and final host binaries differ, although the changed observer was
disabled in the off arm and arithmetic stayed unchanged. Arm order was fixed.
Those confounders limit causal claims. Exact output matches support these
fixtures, not general quality equivalence. Public runtimes have not been tested
under matched hardware, weights, state and timing boundaries, so there is no
performance ranking.

A genuinely cold long agent prompt still needs prefill. Structural checkpoint
placement cannot supply state lost at a restart or never created. Nor does this
work eliminate the roughly 1.2-second residual replay of the 198-row changed
suffix. That middle-size dispatch region is a measured next target, not a solved
problem. A useful next experiment would compare routing choices for that region
with identical numerics and state, rather than repeat broad throughput tests.

## Prior art and scope

[Marconi](https://arxiv.org/abs/2411.19379) already studies hybrid prefix caching
and compute/reuse-aware cache management.
[Sparse Prefix Caching for Hybrid and Recurrent LLM Serving](https://arxiv.org/abs/2605.05219)
formulates overlap-distribution checkpoint placement and an exact dynamic
program. We do not claim priority for that formulation or for dynamic programming.
[SegLen](https://abdelfattah-lab.github.io/blogs/seglen/) explores practical
hybrid-cache retention heuristics in SGLang.
[SuffixReplay](https://arxiv.org/abs/2609.33477) instead approximates recurrent
state through bounded suffix replay; this study retains exact native state
identity and does not implement that approach.

The [pinned source audit](../architecture-review.md) also identifies close
conversation-boundary and draft-state mechanisms in TensorFold, llama.cpp,
oMLX, Splash and vLLM. Our contribution is the concrete Splash/DFlash2 scheduling
extension and reproducible evidence, not ownership of their mechanisms.
