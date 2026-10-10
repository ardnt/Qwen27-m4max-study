# When a checkpoint planner earns—and does not earn—its complexity

A local optimization can look impressive on its best request and still fail its
own acceptance rule. Our initial randomized comparison found exactly that:
8.66% lower complete-block latency than the original heuristic, but a roughly
10% cold-request regression, more retained memory, and two differing Python
outputs. It won all seven blocks but missed the predeclared 10% threshold.
That is a useful result, not evidence to hide.

## The problem and the existing machinery

A hybrid model needs recurrent state as well as attention KV to resume a prefix.
DFlash2 adds draft context that must agree with that boundary. Splash already
provides complete-state capture, native prefix identity and memory governance.
Our code decides which additional boundaries to retain; it does not invent that
machinery or change model weights.

The original 2K-minimum rule helped long first branches but skipped short useful
boundaries. A learned planner can price target command splits, capture/restore,
draft materialization and expected later reuse. It can also overestimate reuse
and charge an unrelated prompt for a checkpoint it never needs.

The optimizer itself took microseconds. The relevant cost was the extra
prefill/capture work it requested. Optimizing the selection routine would have
targeted the wrong bottleneck.

## A conservative revision and a stronger baseline

The revised admission rule avoids additional captures for short single-turn
requests until a native prefix junction has been observed. Multi-turn histories
and long prefixes remain eligible. This deliberately gives up speculative first
short-branch acceleration. It cannot identify every future useful prefix and
never promises zero cold cost.

We paired this gate with two selectors: the measured-cost planner, and a simple
latest/earlier-boundary selector with no cost fit, overlap learner or DP. Both
use the same state and memory limits. This is the comparison that distinguishes
"more useful boundaries" from "a necessary optimizer."

## Final validation

Seven randomized blocks, 315 measured requests plus 21 excluded warmups. Every
arm shares the same final binary, model, template and 25 GiB native ceiling.
The corpus includes 103 fresh synthetic cases and the two prior divergent Python
prompts. Prime costs count. Every individual sample is retained.

| Comparison | Median paired latency reduction | Wins |
|---|---:|---:|
| Conservative simple vs original heuristic | 6.18% | 7/7 |
| Conservative planner vs original heuristic | 5.69% | 7/7 |
| Conservative planner vs simple | -0.72% | 2/7 |

The final complexity acceptance rule **does not pass**.
See [all criteria, intervals and per-family tradeoffs](final/REPORT.md). Seven
blocks support a focused comparison, not a production population or tail-latency
SLO. The planner wins only two of seven blocks against simple, and its difference
interval includes zero: there is no demonstrated benefit from the extra machinery.
The simple policy is therefore the more useful experimental baseline, not a
proven global winner.

Its multi-turn editing-sequence reduction is 25.04%, but the short 1K sequence slows by
5.74% and unrelated cold sequences by 0.66%. Peak family footprint rises by about
0.92 GiB versus the old heuristic. A short first branch can now pay for capture
after reuse is observed; an immediate repeat does not repay that admission cost.
These regressions are retained in the total and should guide adoption.

Same ceilings do not mean identical occupied memory. No performance ranking
against other engines follows from this experiment.

## Correctness is more than a matching cache key

The first trial changed `v // width` to `int(v) // width` in one Python case and
made the reverse change in another. Those expressions differ for negative
fractional input. Both requests were cold, so the data does not establish a
cache-restore defect. Changed prefill segmentation is a plausible numerical
cause; token/logit tracing would be needed to isolate it.

The final corpus has **105/105 exact three-way output matches**.
Do not turn a regression-fixture pass into a bitwise-equivalence theorem.
Exact native prefix identity is required for restoration; altered floating-point
execution can still change a greedy decision. Arithmetic answers and Python
syntax are checked, but generated code was not executed and intelligence was
not evaluated.

## Attribution and what deserves sharing

[Marconi](https://arxiv.org/abs/2411.19379) covers hybrid-state admission and
compute-aware eviction. [Sparse Prefix Caching](https://arxiv.org/abs/2605.05219)
covers overlap-distribution checkpoint placement with dynamic programming.
[vLLM's semantic proposal](https://github.com/vllm-project/vllm/pull/49574) and
[FreeToken](https://arxiv.org/abs/2608.16157) disclose semantic boundaries.
Our [detailed review](../PRIOR_ART.md) also covers simpler policies, abandoned
cost scores, speculative-state correctness and hardware-cost planning.

The contribution is a concrete Splash/DFlash2 integration, tests and decision
receipts, and evidence about when its costs pay back. Broad first-of-kind claims
are withdrawn. The controlled comparison is valuable precisely because it can
show that additional machinery is unnecessary or harmful for a workload.

Remaining work includes a true per-conversation forecast, global retention
opportunity cost, longer interleaved traces and isolating numerical segmentation
effects. Lower-cost interior state exports are another direction; they are not
implemented or measured here. No new kernel, drafting algorithm or universal
speed gain should be inferred.

[Reproduction and patch instructions](README.md) ·
[Initial controlled report](original/REPORT.md) · [Final report](final/REPORT.md).
