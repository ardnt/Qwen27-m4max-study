# Controlled checkpoint-policy comparisons

These studies ask whether checkpoint policy complexity pays for itself on one
M4 Max / Q4 hybrid 27B deployment. They do not establish a global runtime ranking
or an invention-priority claim. [Prior art](../PRIOR_ART.md) substantially overlaps
semantic anchors, recomputation-aware admission and sparse-placement DP.

## Initial randomized experiment

[Full report](original/REPORT.md) · [raw rows](original/raw.jsonl) ·
[protocol](original/protocol.json) · [summary](original/summary.json)

315 measured requests, 21 warmups, seven randomized paired blocks. Stock policy,
original heuristic and cost-aware planner share one tuned binary and a 25 GiB
native memory ceiling. "Stock" means checkpoint policy, not the vendor binary.
Planner versus heuristic: 8.66% median paired latency reduction, seven wins,
but below the predeclared 10% requirement. Unrelated cold requests regress by
roughly 10%; peak family footprint increases by 1.27 GiB. Two Python cases differ.
The declared acceptance rule fails. These results remain unchanged.

## Final conservative candidate

[Final report](final/REPORT.md) · [final patch](final/05-conservative-admission.patch)

The candidate avoids optional captures on short single-turn prompts until a
native prefix junction has been observed. Multi-turn histories and prefixes
of at least 2K remain eligible. This deliberately sacrifices speculative
first-branch gains on unseen short prefixes; it does not make cold prefill free.

A simple comparator uses the same admission gate, selects latest then earlier
user boundaries, requires at least 512 rows from the resume point, and obeys the
same two-state/512 MiB per-decision limits. It has no cost fit, overlap learner
or DP. Native allocation, global memory and exact-prefix identity remain in
control. The planner uses its existing measured-cost selection behind the gate.

The final experiment has seven randomized blocks of original heuristic,
conservative simple policy and conservative planner inside one final binary.
Workload families and geometry are deliberately reused; this is not an independent
production holdout. 103 cases have fresh synthetic text; two exact prior failing Python prompts are
retained as labelled regressions. Do not compare aggregate timings between
experiments as a causal before/after effect: the corpus and binary changed.

## Offline verification

From the repository root:

```sh
python3 verify.py
python3 controlled/verify.py
```

The verifier checks the fixed corpus hash, dependency/arm order, measured counts,
actual usage, every output hash and arithmetic answer, code syntax, native
request counters, memory observations, and recomputed per-request/paired results.
It does not execute generated code. Final controller tests check conservative
admission, memory/pressure handling, malformed geometry, simple selection and
absence of learning in simple mode. The optimizer still faces a brute-force
subset oracle and independent upstream draft-context accounting.

## Replay on an existing isolated service

The operator must supply a fresh worker/cache/learner for each arm/block, the
protocol's native mode and common configuration, and the same model/template.
Follow each protocol's randomized arm order. The client never controls services.
Example for one final arm (read its protocol before choosing block/order):

```sh
python3 controlled/replay.py --study final --block 0 --arm planner \
  --base-url http://127.0.0.1:8001/v1 --model YOUR_MODEL \
  --metrics-url http://127.0.0.1:8001/metrics --output new-block0-planner.jsonl
```

The client sends an eight-token warmup, followed by that block's fixed requests
sequentially. It exposes no agent tools, includes connection setup in client
TTFT/E2E, rejects token-count mismatches, and reads any API key only from
`BENCH_API_KEY`. The existing historical benchmark client retains its older
connection-excluding timing boundary. A dedicated offline test checks both.
Native internal counters, process-family memory and receipts still need native
instrumentation; client replay alone does not recreate all original evidence.

## Native integration and limitations

Apply the [historical patches 01–04](../semantic/README.md#native-integration),
then `controlled/final/05-conservative-admission.patch` on the pinned old source.
Do not apply blindly to current Splash. `SPLASH_SEMANTIC_PLANNER=off` retains the
original heuristic; `on` enables the conservative planner; `simple` enables the
conservative simple selector; `shadow` records conservative plans without applying
them. Marker IDs are tokenizer-specific. All policies rely on native complete
state and exact token identity; none uses approximate semantic similarity.

[Patch verification](final/patch-application.json) checks all 241 runtime files
against the measured final source capsule. Unchanged archive objects and stock
Metal shaders were reused. They and model weights are not redistributed;
independent clean builds require their own qualification. Binary hashes identify
what ran, not full source-build reproducibility.

Equal ceilings are not equal occupied RAM. Short fresh-worker sessions do not
represent hours of interleaved users or a retention-cost frontier. Seven blocks
are the independent units; p95 for seven observations is just their maximum.
Exact saved-state identity does not guarantee bit-identical greedy output when
chunking or floating-point execution changes. Output agreement is corpus-specific.

## Export boundary

Only synthetic prompts/outputs, timing/counter/memory evidence, redacted controls,
source changes and source-receipt metadata are distributed. Private conversations,
credentials, production configuration, process IDs, local paths, captured public
webpage bodies and service-control scripts are excluded. Export source hashes
and redactions are documented separately for each study. Historical data is
retained rather than overwritten with selected favorable results.

### Reading policy receipts

`mode` determines whether the revision's admission policy is active. With
`mode=off`, the legacy heuristic path remains in use even though the status
schema identifies the available `conservative_v2` admission revision.
`admission_deferred=true` means short single-turn eligibility was declined.
In `simple` mode, `cost_scope=none_simple_boundary_policy`; default coefficient
fields and zero predicted-cost fields are not fitted measurements or claims of
zero work. Use actual native work counters for all cross-policy comparisons.

The extra-state cap is per decision, not a global lifetime cap. Native global
allocation and eviction remain authoritative. Role-token markers guide
placement, not authorization or semantic equivalence of different text.
