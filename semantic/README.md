# Cost-aware semantic checkpoint planner — measured results

“Semantic” refers to exact conversation structure. It adds no embedding model
and never reuses state merely because two prompts have similar meanings.

## Results

Seven different deterministic fixtures per primary cell, temperature zero,
streaming, thinking disabled. TTFT is client-observed first content/reasoning;
these fixtures emit no reasoning. p95 is nearest rank and equals the observed
maximum at n=7; it is not a reliable population-tail estimate.

| Workload | n/arm | Actual input | Output tokens | TTFT off p50 | On p50 | On observed p95 | Reuse off → on (median) |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1K changed question | 7 | 1222 | 4 | 4.125s | 1.218s | 1.225s | 0 → 1024 |
| Multi-turn latest edit | 7 | 1180 | 4 | 4.131s | 2.434s | 2.494s | 0 → 512 |
| Earlier-turn edit | 7 | 710 | 4 | 2.502s | 1.211s | 2.995s | 0 → 512 |
| Exact repeat | 7 | 1222 | 4 | 0.171s | 0.168s | 0.170s | 1216 → 1216 |
| Cold 1K prime | 7 | 1222 | 4 | 4.131s | 4.635s | 4.651s | 0 → 0 |
| Cold multi-turn prime | 7 | 1179 | 4 | 4.035s | 4.199s | 4.538s | 0 → 0 |
| 8K follow-up pilot | 1 | 8390 | 4 | 1.251s | 1.252s | — | 8192 → 8192 |
| Cold 8K pilot | 1 | 8391 | 4 | 28.712s | 28.351s | — | 0 → 0 |
| New Python pilot | 3 | 1099 | 85 | 3.853s | 4.021s | — | 0 → 0 |

For changed 1K questions, both target and draft context rows fall from 1222 to
198. Cold checkpoint creation costs about 0.50s. Entire sequences account for
that cost:

| Sequence | Off median total | On median total | Median paired saving |
|---|---:|---:|---:|
| Prime + changed question + repeat | 8.427s | 6.020s | 2.416s |
| Prime + latest edit + earlier edit | 10.675s | 7.853s | 2.840s |

All seven complete sequences in each family improved. The earlier-turn p95
retains the first miss: there is no claim that every request improved.

Python backend effective speculative decoding was 101.80 → 102.33 tok/s (n=3).
Draft acceptance was **213/273 = 78.02% in each arm**. This short pilot establishes
no sustained decode speedup. All 48 paired outputs match byte-for-byte; Python
syntax is checked, not general program correctness or model intelligence.

Peak sampled process-family footprint: **25.527 GiB**, swap **0**, normal sampled
memory pressure. Sampling can miss short peaks and shared accounting can overlap.
Exact GPU temperature/clocks were not measured. No 32K/64K result is claimed.

## Environment and scope

M4 Max, 14 CPU/32 GPU cores, 36 GiB; macOS 26.5.2 (25F84). Target Q4 affine/group64,
three Safetensor shards totaling 16,054,541,599 bytes. Installed Qwen3.8 label,
`qwen3_5` architecture; exact public target revision unverified.
Splash 1.3.0 historical host base `0d5a035ea26d1cc566e3c7ee4e08e5e06fa68cf7`,
Metal + validated ANE split 0.6176470588 at 512+ rows. Context 65,536,
BF16 KV pages of 32 tokens, 2,048-row prefill commands, register route ≤128 rows,
4,096-token rolling recovery interval, 25 GiB native memory budget.

Draft: `z-lab/Qwen3.8-27B-DFlash2`, revision
`50307d4c4cde6860d4eee73e2547cd786fe8e8a4`, five layers,
3,848,817,896-byte BF16 source weights. Runtime projection handling unchanged;
seven proposals plus anchor, full 2,048-token context, rank256/top-k16 selector,
full target verification. Complete snapshot: 196,083,712 bytes (187 MiB).
Semantic placement budget: two states and 512 MiB per request; native global
admission/eviction still applies.

**Causal limits:** fixed off→on arm order; baseline and final host hashes differ
because an opt-in observer was corrected before the final on run. Off mode did
not use that observer. Two final-binary off smoke requests retained the miss,
but do not replace a same-binary randomized experiment. The unchanged host
archive and stock Metal library were reused; this is not a clean source build.
See [build hashes](data/build-provenance.json). Small differences should not be
attributed to the planner. Direct isolated inference was measured; Hermes,
Telegram, tools and remote-network overhead were not.

Raw data has 100 requests: 96 measured, two warmups, two final-binary off smoke
requests. The original heuristic study has a separate 98 measured requests.

## Reproduction

```sh
# From repository root; no model or service required:
python3 verify.py
python3 semantic/analyze.py --check --output-dir /tmp/semantic-results
```

The verifier recomputes means, standard deviations, observed p95 and paired
sequence sums. It validates actual counts, arithmetic, output hashes, complete
case pairing and syntax directly from [raw rows](data/raw.jsonl) and the fixed
[corpus](data/corpus.json.gz), rather than trusting saved success flags alone.
The original [recorded summary](data/recorded-summary.json) remains unchanged.
Its historical installation gate is scoped to that experiment; passing offline
checks is not authorization or proof of safety for another deployment.

`benchmark.py --suite semantic` sends the 48 corpus cases in their recorded
fixture order; it does not perform service warmup or change a mode. Use a single
final binary for both off/on arms, preserve every other option, start each arm
with the same cache/learner conditions on an isolated test service, and record
warmups separately. At least seven fixture repetitions are supplied. Randomize
arm order across independent runs if estimating small causal effects. Record
actual input counts and reject comparisons with different tokenization.

The client includes no tools and records first-token, first-visible, end-to-end,
usage and optional `--metrics-url` deltas. It does not collect native planner
receipts or per-process memory; reproduce those with independent native
instrumentation before making equivalent claims. It never controls services.
macOS memory pressure and swap growth are monitored; other systems need their
own monitor. Counter intervals shared with other requests are invalid.

The published receipts retain only synthetic case IDs and planner state. Host
paths, process handles and production configuration are excluded from exported
build commands/health state. Synthetic output text and sampled memory records
are retained for scrutiny. No personal-chat replay is included.

## Native integration

On a disposable checkout at the exact historical Splash base above, apply:

```sh
git apply /path/to/study/patches/legacy/01-local-prerequisites.patch
git apply /path/to/study/patches/legacy/02-qualified-host-delta.patch
git apply /path/to/study/semantic/patches/03-measured-semantic-planner.patch
git apply /path/to/study/semantic/patches/04-controller-validation.patch
```

The first three reconstruct the measured planner source; the fourth hardens
invalid geometry before candidate alignment. [Application receipt](data/patch-application.json)
checks all four in sequence and equality of the exported headers. The last fix
is CPU-tested and is not included in the historical GPU benchmark binary.
Do not apply this chain to current Splash main: native interfaces/formats have
changed. No precompiled archive, shader, weights or machine-specific launcher
is redistributed, so the exact measured executable cannot be reproduced from
this repository alone. A clean build should follow the pinned upstream build
instructions and receive new numerical/state-restoration qualification.

`SPLASH_SEMANTIC_PLANNER` supports `off` (default), `shadow` and `on`.
`SPLASH_BRANCH_MARKER_IDS` is tokenizer-specific; the measured value was
`248045,846,198`. Derive it from the deployed chat template. Native prefix/image
identity remains authoritative; image requests fall back to the existing path.
Document/tool spans, persistent learned state, global eviction opportunity cost,
and generated-reply-end checkpoints are not implemented features.

## Scientific classification

- **Verified within this corpus:** saved latencies/counters, avoided rows, output
  equality, memory samples, total-sequence savings, CPU optimizer/oracle agreement.
- **Partially verified:** causal size of small timing changes, estimated cost
  coefficients, forecast generalization, n=1/3 pilots.
- **Not measurable here:** isolated kernel speed, unassisted target decode,
  intelligence, Hermes overhead, GPU temperatures, cross-runtime ranking.
- **Not established:** broad novelty priority, zero regression, latest-upstream
  production readiness, first-ever checkpoint optimization.
