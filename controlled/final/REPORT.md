# Final conservative checkpoint-policy validation

10 October 2026. Seven randomized paired blocks; 315 measured requests and 21 excluded warmups. No agent tools were available or executed.

**Result:** the conservative planner changes median paired complete-block latency by **-0.72% reduction versus the conservative simple policy** (2/7 wins). Its predeclared complexity rule **does not pass**. Positive reductions mean faster; negative reductions mean slower.

## What changed and why

The initial randomized trial found an approximately 10% unrelated-cold regression and two Python output differences. The final candidate declines extra checkpoints on short single-turn prompts until a native prefix junction is observed. Multi-turn histories and user boundaries at least 2K into the prompt remain eligible. This is an admission tradeoff: it gives up speculative first-branch gains on unseen short prefixes. It does not eliminate all numerical differences from chunking, guarantee no regression, or make new long prompts cheap.

The simple comparator shares the admission gate but takes the latest then earlier user boundaries, with at least 512 rows of distance from the resume point. It obeys the same two-state/512 MiB per-decision limit and native global governor. It has no fitted cost coefficients, overlap learner or dynamic program. The cost-aware candidate retains those mechanisms. Invalid geometry is checked before candidate-alignment divisions.

## Controls and provenance

- M4 Max, 14 CPU / 32 GPU cores, 36 GiB unified memory; macOS 26.5.2, AC. One sequential inference request. Native memory ceiling 25 GiB in all arms, launcher limit 28 GiB; no disk prefix persistence in isolated workers.
- Local target label Qwen3.8-27B-Uncensored-Splash-1.3, affine Q4/group64, Safetensors. Target config declares qwen3_5; exact remote target revision remains unverified. Same local weights/tokenizer/template for every arm.
- Splash 1.3.0 historical host base 0d5a035ea26d1cc566e3c7ee4e08e5e06fa68cf7. Shared final binary SHA-256: `b2dfcfc0ed4683991c2b226c4782dcaaaa4f1322cceef5982f27805c3c78646e`. Modified host units rebuilt; pinned unchanged archive and stock Metal library reused. This is not a complete clean-source build.
- DFlash2 unchanged: z-lab/Qwen3.8-27B-DFlash2, revision 50307d4c4cde6860d4eee73e2547cd786fe8e8a4, seven proposals / block eight, 2048-token draft window, full vocabulary. Context cap 65536; BF16 KV, page 32.
- Register-prefill threshold 128, wide prefill enabled, qualified native ANE split share 0.6176470588 at 512+ rows. Route/share and native guards checked on every run; no guard disabled.
- Streaming, temperature zero, seed 20261010, thinking disabled, no tools. Identical 15-request blocks and reset cache/learner per arm. All six arm permutations plus a seeded seventh; bundle order randomized, dependent sequences stay ordered.
- Corpus seed 202610102006. 103 cases use new synthetic text; two exact prior Python regression prompts are retained and identified in the protocol. Workload families and geometry are deliberately reused, so this is not an independent production holdout. All prompts, arm orders, binary hash and criteria fixed before measuring.
- Client monotonic clock includes connect and POST through SSE DONE; serialization, between-request gaps and model startup excluded. Primary endpoint sums all 15 request latencies, including cold priming and capture costs.

## Primary results

| Policy | Block E2E median (s) | Mean (s) | SD (s) | Peak sampled family (GiB) |
|---|---:|---:|---:|---:|
| Original heuristic | 71.107 | 71.207 | 0.399 | 22.790 |
| Conservative simple | 66.711 | 66.731 | 0.466 | 23.707 |
| Conservative planner | 67.030 | 67.261 | 0.844 | 23.507 |

| Paired comparison | Median latency reduction | Bootstrap 95% interval | Wins |
|---|---:|---:|---:|
| Planner vs simple | -0.72% | -1.43% to 0.02% | 2/7 |
| Planner vs heuristic | 5.69% | 5.07% to 6.20% | 7/7 |
| Simple vs heuristic | 6.18% | 5.95% to 7.26% | 7/7 |

Primary exact two-sided sign-test p=0.45312. Seven blocks are the independent units. Seeded paired bootstrap uses 20,000 resamples. Intervals describe this small synthetic experiment, not general production traffic. Secondary family comparisons are descriptive with no multiple-comparison significance claim.

| Predeclared criterion | Passed |
|---|---|
| cold regression at most 3pct | True |
| median reduction at least 10pct | False |
| at least six wins | False |
| all arithmetic correct | True |
| all paired outputs identical | True |
| no safety abort | True |
| peak no more than 30gib | True |

The 10% criterion applies to planner versus simple. Cold regression must be at most 3% against the original heuristic. Exact paired outputs, correct arithmetic, no safety abort and sampled peak at most 30 GiB are also required. No threshold was revised after results.

## TTFT by stage

Client median / nearest-rank p95, in seconds. n=7 except multi-turn and unrelated n=14. At n=7 p95 is the sample maximum; related within-block requests are not independent trials.

| Family / stage | Actual input tokens | Heuristic | Simple | Planner |
|---|---:|---:|---:|---:|
| latest_1k / prime | 1217 | 4.053 / 4.294 | 4.256 / 4.513 | 4.084 / 4.215 |
| latest_1k / changed | 1217 | 4.030 / 4.218 | 4.495 / 4.649 | 4.579 / 4.709 |
| latest_1k / repeat | 1217 | 0.168 / 0.175 | 0.164 / 0.165 | 0.165 / 0.171 |
| multi_turn / prime | 1173,1174 | 3.886 / 4.211 | 5.421 / 5.733 | 4.198 / 4.571 |
| multi_turn / changed | 1174,1175 | 3.917 / 4.178 | 1.254 / 1.327 | 1.790 / 2.511 |
| multi_turn / older | 704,705 | 2.460 / 2.619 | 1.192 / 1.243 | 1.852 / 3.096 |
| branch_8k / prime | 8385 | 28.234 / 28.584 | 28.200 / 28.745 | 28.203 / 28.545 |
| branch_8k / changed | 8385 | 1.276 / 1.296 | 1.248 / 1.314 | 1.267 / 1.290 |
| branch_8k / repeat | 8385 | 0.173 / 0.173 | 0.170 / 0.177 | 0.173 / 0.176 |
| unrelated / cold | 1217 | 4.094 / 4.276 | 4.127 / 4.330 | 4.157 / 4.305 |
| code / python | 1098,1099,1100 | 3.710 / 3.894 | 3.813 / 3.900 | 3.702 / 3.894 |

## Complete-sequence tradeoffs

Includes first-request cost. Positive means reduction versus the original heuristic.

| Family | Simple median reduction | Planner median reduction |
|---|---:|---:|
| branch_8k | 0.34% | -0.18% |
| code | -0.00% | 0.06% |
| latest_1k | -5.74% | -6.55% |
| multi_turn | 25.04% | 22.08% |
| unrelated | -0.66% | -0.42% |

## Work counters and decoding control

| Policy | Target prefill rows | Draft materialization rows | Code native decode tok/s median | Code acceptance median |
|---|---:|---:|---:|---:|
| Original heuristic | 144579 | 115104 | 105.18 | 76.92% |
| Conservative simple | 123971 | 94496 | 103.55 | 76.92% |
| Conservative planner | 130691 | 101216 | 103.93 | 76.92% |

Native code decode throughput is committed output counter delta divided by native decode-wall delta, including speculation. Seven short Python outputs per arm cannot establish sustained general decoding speed. DFlash2 was never disabled or changed. Avoided draft preparation is not a better drafting algorithm. Three-/four-token arithmetic stream rates are excluded because delivery within one speculative batch produces meaningless extreme tok/s values. Raw effective-prefill fields are not pure kernel timings; native prefill counters are retained separately.

## Output, memory and limitations

All arithmetic answers correct: **True**. Three-way exact text/reasoning/token-count matches: **105/105**. All 21 Python definitions parse: **True**. No generated code was executed; this is not a functional-quality benchmark.

Mismatch case IDs: **none**. Full outputs and differences remain in raw rows and summary.json. Regressions b04-code-python and b06-code-python are retained verbatim from the previous corpus. Passing those fixtures would show the observed divergence no longer appears in this test, not prove universal numerical equivalence.

Maximum sampled swap: **0 MiB**. No request errors/safety aborts: **True**. Family footprint is sampled process accounting, not total physical memory, and can miss short peaks. Equal hard ceilings do not enforce equal occupied RAM.

Planner chooser median 2.834 microseconds; maximum reported 5.583 microseconds. This excludes separate observation/update work; request E2E includes it. Invalid decisions: 0.

Background desktop and CPU-only publication work continued. Native ANE route was fixed, and recorded system monitoring reported thermal state; absence of warnings does not prove constant GPU clocks. No aggressive cache purge, concurrent inference or service-source/config edits occurred. Model startup is excluded; each arm receives the same warmup.

These are short, fresh-worker synthetic sessions. They do not measure multi-user interleaving, long-run eviction opportunity cost, real tools, images, Arabic, 32K/64K scaling or intelligence. Different prompt seeds and binaries prevent causal aggregate before/after comparisons with the initial experiment. No current-upstream integration or cross-runtime performance ranking is established.

## Decision and remaining tradeoffs

The final evidence does not justify the fitted-cost planner over the conservative simple selector. The planner wins only 2/7 paired blocks against simple; the difference interval includes zero. The simpler policy is a useful experimental baseline, not a proven universal winner or automatic production replacement.

The simple policy reduces complete-block latency by 6.18% versus the old heuristic and multi-turn editing-sequence latency by 25.04%, but regresses the short 1K sequence by 5.74% and unrelated cold sequences by 0.66%. Its sampled peak family footprint is about 0.92 GiB higher. The conservative planner regresses the short 1K sequence by 6.55% and unrelated cold sequences by 0.42%. This tradeoff is intentional: a short first branch can pay for admission only after reuse is seen, and an immediate exact repeat does not repay that extra capture. No zero-regression claim is made.

## Reproduce and interpret

Run the repository root verifier or `python3 controlled/verify.py`. Every saved request is retained; analysis suppresses misleading tiny-output decode rates without removing samples. Export provenance records privacy redactions and original source hashes. See controlled/README.md for manual isolated replay and pinned-source patch instructions.

An advantage over the old threshold heuristic is evidence about these policies on these workloads. It is not evidence that full cost fitting and DP are necessary. The primary simple comparator directly tests that stronger claim. Performance and output agreement must both be reported; a failure of the declared rule remains a failure.

Production services are restored to their previous configuration. The tested patch is distributed as an experimental candidate; this publication does not silently install it.
