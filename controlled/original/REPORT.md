# Initial Randomized Controlled Comparison — Qwen3.8-27B Q4 Checkpoint Policies

10 October 2026 · Apple M4 Max · Collected privately; released after authorization and final validation

**Result:** the planner reduced median paired complete-block latency by **8.66% versus the original heuristic**, winning 7/7 blocks. Its reduction versus the stock checkpoint policy was **23.76%**. The predeclared complexity-justification rule **DID NOT PASS** for this workload mix.

This is a comparison of checkpoint policies inside one tuned Splash binary. It is not a benchmark of the stock distributed Splash executable, nor a ranking against TensorFold, MLX, oMLX, llama.cpp, vLLM or SGLang. The separate [prior-art review](../../PRIOR_ART.md) rejects broad claims of first semantic checkpointing or first cost-aware sparse checkpoint placement.

## Environment and controls

- Hardware: MacBook Pro Mac16,6, Apple M4 Max, 14 CPU cores, 32 GPU cores, 36 GiB unified memory. macOS 26.5.2 (25F84), Metal 4; AC power.
- Served identifier: `Qwen3.8-27B-Uncensored-Splash-1.3`; local target `orcarouter/Qwen3.8-27B-Uncensored-MLX`. Safetensors, affine Q4 group size 64. Target shards total 16,054,541,599 bytes; draft weights 3,848,817,896 bytes. The model configuration identifies the architecture as `qwen3_5`, with 64 text layers (48 linear and 16 full-attention). A marketing/model-family name is not evidence of a different architecture.
- Splash reports version 1.3.0. Same native binary SHA-256 in all arms: `ebb3972229e9de7593c39f9c8fc6cb31a5c093e1afbf135e41f47269e09fa3ef`. Historical source base `0d5a035ea26d1cc566e3c7ee4e08e5e06fa68cf7`; unchanged object archive reused with modified units. This is not a complete pristine-source rebuild.
- DFlash2 remains enabled in every arm: `z-lab/Qwen3.8-27B-DFlash2`, revision `50307d4c4cde6860d4eee73e2547cd786fe8e8a4`, 2,048-token draft window, block 8 / seven proposals, full vocabulary.
- Active context cap 65,536; model metadata limit 262,144. KV BF16, 32-token pages; single sequence. Native hard memory budget 25 GiB, common launcher environment requests 28 GiB. No disk prefix persistence in private workers. The planner can admit at most two additional states / 512 MiB **per decision**, subject to the common global governor.
- Common optimizations: register-prefill threshold 128 and wide prefill enabled. Native ANE route checked on every run: split share 0.6176470588, minimum 512 rows. Existing qualified calibration reused; all native guards remain active.
- Direct OpenAI-compatible streaming endpoint on `127.0.0.1:8486`; same adapter, request settings and tokenizer/template. The counting tokenizer vocabulary and effective template match the served tokenizer; config packaging differs only by embedded versus separate template.
- Temperature 0, seed 20261010, reasoning disabled, no tool schemas, `tool_choice=none`, streaming usage enabled. No agent tools or generated code were executed.

| Arm | Planner switch | User-boundary marker | Meaning |
|---|---|---|---|
| Stock | off | empty | Native lazy junction/replay policy |
| Heuristic | off | `248045,846,198` | Native policy plus original proactive user anchor with 2K minimum |
| Planner | on | same marker | Cost-aware optional placement; native mandatory recovery states retained |

## Experimental design

Seven paired blocks; 15 measured requests per arm per block: **315 measured requests plus 21 excluded warmups**. Each arm starts a fresh worker, clearing its in-memory cache and learner without purging OS caches. Each receives the same eight-token warmup. Cold means cold native prefix state, not cold disk weights or a cold operating-system page cache.

Randomization seed: `202610101234`. All six arm permutations appear, plus one seeded additional permutation. Bundle order is randomized per block and held identical across its arms. Dependent prime/change/repeat sequences stay ordered. Corpus seed values differ from the earlier qualification fixtures; all prompts were written and hashed before inference.

Workload mix per arm/block: a 1K-prefix prime/change/repeat sequence; an 8K-prefix prime/change/repeat sequence; two multi-turn prime/latest-edit/older-edit sequences; two unrelated cold prompts; one original Python function. Arithmetic outputs are intentionally short to isolate first-answer latency. Code is a small decoding control, not a full quality or sustained-throughput suite.

Primary endpoint: sum of client-observed request E2E times within each 15-request block, including cold prime and checkpoint creation costs. The sum excludes model loading, benchmark bookkeeping, between-request gaps and JSON serialization. Each timed request starts before loopback connect/POST and ends after SSE `[DONE]`; `perf_counter_ns` provides the monotonic clock.

Predeclared success rule: median paired E2E reduction at least 10% versus heuristic; at least 6/7 improved blocks; all arithmetic correct; paired outputs identical; no safety abort; peak family footprint at most 30 GiB. Seven blocks—not 315 requests—are the independent comparison units. The rule was fixed in `protocol.json` before measurements.

## Primary result

| Policy | Block E2E median (s) | Mean (s) | SD (s) | p95/max (s) | Peak family footprint (GiB) |
|---|---:|---:|---:|---:|---:|
| Stock checkpoint policy | 84.429 | 84.359 | 0.968 | 85.528 | 22.926 |
| Original heuristic | 70.188 | 70.412 | 0.657 | 71.621 | 22.796 |
| Cost-aware planner | 64.188 | 64.251 | 0.606 | 65.488 | 24.066 |

Planner versus heuristic paired median reduction: **8.66%**, seeded 20,000-resample paired bootstrap interval **8.34% to 9.21%**. Exact two-sided sign-test p=0.01562. With only seven blocks, these quantify this small experiment, not a production population or extreme-tail SLO.

| Block | Order | Stock total (s) | Heuristic total (s) | Planner total (s) | Planner reduction vs heuristic |
|---|---|---:|---:|---:|---:|
| 1 | planner → heuristic → stock | 85.293 | 71.621 | 65.488 | 8.56% |
| 2 | stock → heuristic → planner | 85.528 | 70.844 | 63.961 | 9.72% |
| 3 | heuristic → planner → stock | 85.088 | 70.188 | 64.334 | 8.34% |
| 4 | stock → planner → heuristic | 84.429 | 70.552 | 64.314 | 8.84% |
| 5 | heuristic → planner → stock | 83.242 | 69.696 | 64.188 | 7.90% |
| 6 | planner → stock → heuristic | 83.518 | 69.935 | 63.876 | 8.66% |
| 7 | heuristic → stock → planner | 83.415 | 70.050 | 63.595 | 9.21% |

## Where the time changed

All values below are client TTFT median / nearest-rank p95 in seconds. At n=7, p95 is simply the observed maximum. Multi-turn categories combine two cycles per block (n=14) and are descriptive, not 14 independent experiments.

| Family / stage | Actual input tokens | n per arm | Stock | Heuristic | Planner |
|---|---:|---:|---:|---:|---:|
| latest_1k / prime | 1216,1217 | 7 | 4.064 / 4.245 | 4.055 / 4.194 | 4.495 / 4.605 |
| latest_1k / changed | 1216,1217 | 7 | 4.042 / 4.234 | 4.050 / 4.136 | 1.184 / 1.208 |
| latest_1k / repeat | 1216,1217 | 7 | 0.169 / 0.263 | 0.168 / 0.264 | 0.164 / 0.256 |
| multi_turn / prime | 1174 | 14 | 3.866 / 4.095 | 3.881 / 4.107 | 4.177 / 4.407 |
| multi_turn / changed | 1175 | 14 | 3.889 / 4.108 | 3.897 / 4.099 | 1.784 / 2.382 |
| multi_turn / older | 705 | 14 | 2.470 / 2.554 | 2.465 / 2.547 | 1.793 / 2.947 |
| branch_8k / prime | 8385 | 7 | 28.180 / 28.842 | 27.996 / 28.436 | 27.974 / 28.468 |
| branch_8k / changed | 8385 | 7 | 15.089 / 15.252 | 1.246 / 1.262 | 1.247 / 1.255 |
| branch_8k / repeat | 8385 | 7 | 0.171 / 0.174 | 0.169 / 0.170 | 0.170 / 0.170 |
| unrelated / cold | 1216,1217 | 14 | 4.039 / 4.243 | 4.066 / 4.394 | 4.463 / 4.739 |
| code / python | 1099,1100 | 7 | 3.708 / 3.821 | 3.711 / 3.835 | 3.840 / 3.924 |

Family-level complete-sequence comparisons include the cost of creating the checkpoint. Negative reduction means a regression. Secondary comparisons are descriptive and have no multiple-comparison significance claim.

| Family | Median paired E2E reduction vs heuristic | Improved blocks |
|---|---:|---:|
| branch_8k | -0.27% | 1/7 |
| code | -2.53% | 1/7 |
| latest_1k | 29.24% | 7/7 |
| multi_turn | 22.30% | 7/7 |
| unrelated | -9.98% | 0/7 |

## Work avoided and speculative decoding

| Policy | Target prefill rows | Draft prompt-end rows | Draft materialization rows | Code native decode tok/s median | Code draft acceptance median |
|---|---:|---:|---:|---:|---:|
| Stock checkpoint policy | 173289 | 905 | 128032 | 106.22 | 78.02% |
| Original heuristic | 144617 | 905 | 115040 | 104.98 | 78.02% |
| Cost-aware planner | 123561 | 905 | 93984 | 105.23 | 76.92% |

Work totals exclude startup and warmup, using per-request native counter differences. `results.csv` also records proposed/accepted draft tokens, cached input tokens, native prefill milliseconds and both timing boundaries. This comparison can show avoided draft preparation; it does not isolate a DFlash2 on/off speedup or demonstrate a better drafting algorithm.

Code decode rates use `splash_decode_output_tokens_total / splash_decode_wall_milliseconds_total`. These are backend-reported, speculation-inclusive rates, with runtime-specific committed-token boundaries. They are not ordinary one-token autoregressive rates. Only seven short code outputs per arm were measured; do not extrapolate to general prose, Arabic, long code or other contexts.

The raw harness retains legacy stream-derived decode fields for completeness. **Do not interpret the enormous rates on three-/four-token arithmetic answers:** tokens within the same speculative batch can be emitted microseconds apart after all computation has finished. The analysis suppresses these rates. Likewise, the raw `effective_prefill_tps` based on response `prompt_ms` is not a separately timed pure prefill measurement; use native work/timing counters when evaluating prefill.

## Memory, correctness and planner overhead

All arithmetic correct: **True**. Identical output text, reasoning and committed-token counts across all 105 three-way pairs: **False**. All 21 generated Python definitions parse: **True**; functional correctness was not executed or scored.

**Two of 105 paired cases differed**, both Python controls: `b04-code-python` and `b06-code-python`. Stock and heuristic agree in each case. The planner changes `v // width` to `int(v) // width` in the first and makes the reverse change in the second; output lengths differ by two tokens. These expressions agree for ordinary integer inputs but differ for negative fractional values (for example, −0.5 at width 11). The prompt did not restrict values to integers, so this is not merely a whitespace difference and no functional-equivalence claim is justified. All six affected requests reported zero reused tokens. The observations therefore do not establish a faulty restored cache. Different prefill segmentation/numerical execution is a plausible explanation, but token/logit tracing would be needed to establish the cause. The exact-output criterion fails; all samples remain in the predeclared primary result.

Maximum sampled swap: **0 MiB**. Memory pressure stayed normal in recorded samples. No safety aborts, request errors or excluded measured samples. Family footprint is the sum of sampled process footprints, not system RAM or a continuously observed physical peak. Native allocator peaks are retained separately.

Chooser timing: median **2.792 µs**, maximum reported **5.416 µs**. This timing excludes the separate previous-prompt LCP observation and cost updates; full request E2E includes them. Invalid planner decisions: **0**.

`system-load.jsonl` records AC power, process load and `pmset` thermal status each minute. Absence of a thermal warning does not prove fixed GPU clocks. Background desktop activity and read-only research continued; recorded process samples include transient CPU activity. Randomized paired ordering reduces temporal confounding but cannot remove it completely.

Equal native memory ceilings were enforced. Occupancy was not forced equal: the planner can retain more states and consume more of the same allowance. A single budget and short sessions do not measure long-run displacement, multi-user contention or a memory/performance Pareto frontier.

## What this establishes—and what it does not

**Decision:** the planner has a repeatable latency advantage on this branch-heavy mix, but its added complexity is not yet justified under the predeclared acceptance rule. Both the 10% improvement criterion and exact-output criterion fail. Treat it as an experimental policy, not a universally preferable replacement. No production policy was changed in response to this result.

The strongest next experiment is a simple lower-threshold/earlier-anchor policy against the planner, after investigating output divergence. First measure whether it preserves the 1K and older-turn gains while avoiding speculative captures on unrelated cold requests. The current cold-request regression is roughly 10%, whereas the optimizer itself takes only microseconds; optimizing the decision routine would target the wrong cost. Capture admission, segmentation and forecast calibration are the relevant mechanisms. This is a proposed follow-up, not a result from this experiment.

- The measured difference is attributable to the combined checkpoint policy under these controls, subject to ordinary system noise. This fixes the earlier different-binary/fixed-order comparison weakness.
- A win against the old 2K-threshold heuristic does not establish that the full cost learner and DP are necessary. A smaller threshold plus an earlier-turn anchor could account for part of the gain. That simpler ablation remains unmeasured.
- This synthetic mix was designed to exercise branches, with deterministic arithmetic answers. It is not a random sample of Hermes traffic. Fresh workers test short-session adaptation, not an hours-long steady state.
- No simultaneous users, reasoning stripping, real tool serialization, images, cache persistence, long-context budget sweep or 32K/64K rerun was included. These omissions keep this experiment focused on the requested policies.
- Global novelty is narrowed by the prior art. Global performance superiority remains unmeasured; hardware/model/runtime mismatch prevents using published numbers as a leaderboard.

| Claim | Assessment | Evidence boundary |
|---|---|---|
| Planner reduces latency on the fixed mixed workload | Verified within this experiment | Seven paired wins; 8.66% median reduction versus heuristic |
| Added planner complexity meets the declared bar | Not supported | Below 10%; exact outputs differ in two cases |
| Exact deterministic output preservation | Not reproduced | 103/105 pairs match; two substantive Python differences |
| Full learner/optimizer is necessary | Not measurable from these three arms | Simpler lower-threshold and earlier-anchor baseline absent |
| Better speculative decoding algorithm | Not established | DFlash2 held fixed; code decode rates essentially unchanged |
| Globally first semantic/cost-aware checkpointing | Contradicted as a broad claim | Closely overlapping disclosed prior art |
| Globally superior runtime performance | Not measured | No matched cross-engine benchmark |

## Reproduction and disclosure

The original services were restored after measurement. Production configuration
and source checksums matched their recorded pre-test values. Subsequent checks
confirmed Telegram connected and both local inference health endpoints OK.
No remote-phone connectivity inference follows from local checks.

Run `python3 controlled/verify.py` from the repository root to recompute both
controlled studies. `analyze.py --output-dir /tmp/original-analysis` in this
directory recalculates this study without contacting any service.

`raw.jsonl` preserves every measured request and warmup, synthetic output,
per-request counters and sampled family memory. `corpus.json.gz` and
`protocol.json` preserve prompts, dependency order, randomization and decision
criteria. `decisions.jsonl` contains native policy receipts.
`worker-controls.json` records common command hashes and environment controls;
absolute resource paths are replaced with local-resource placeholders.
`export-provenance.json` records hashes of the original private files and
explains redactions. The original local verifier also checked the complete
serialized request bodies and streams, which are not redistributed.

The native binary is identified by hash; reused archive/Metal dependencies and
model weights are not distributed. A fresh clean build is not automatically
identical to this historical executable. See the repository's native patch
instructions and the separate final candidate study. Do not combine speedups
across the two experiments or across earlier reports.
