# Prior-art review: cost-aware semantic checkpoint planning

Research date: 10 October 2026. Published after the author requested corrections and final validation. This is a review of disclosed engineering work, not a patentability opinion.

**Finding: the broad invention claim does not survive a deeper search.** Semantic checkpointing, hybrid-state prefix reuse, recomputation-aware cache policy, learned overlap statistics, and dynamic programming for sparse checkpoint placement all have prior art. A narrower, potentially useful contribution remains: this implementation combines those ideas with Splash's measured command costs, prefill dispatch thresholds, and DFlash2 context-materialization work. We have not established that this exact combination is globally first, or that it beats other engines.

The controlled experiment in [controlled comparison](controlled/original/REPORT.md) tests the usefulness of the implemented combination against two policies within one binary. It does not establish priority or global superiority.

## Method and evidence standard

Searched public papers, primary project repositories, documentation and pull requests for semantic checkpoints, recurrent prefix-cache admission, overlap-distribution placement, speculative-state reuse, cost-aware eviction and hardware-dependent replay. Followed references from the closest matches and inspected implementation files. Search results pointing to mirrors were used only to locate original sources. Our own public repository was not counted as independent evidence.

The mere.run user-boundary implementation was also checked at its 9 September file revision (`33b6b224e502db89a16d5716f96da821f18fdddf`), so that finding does not rely solely on today's repository head. The FreeToken tool-anchor file was checked at a 7 October revision as well.

The author retained primary-source captures locally. [Source receipts](controlled/source-receipts.json) record URLs, retrieved dates, fixed revisions where available, and content hashes; third-party page contents are not redistributed. Some engine source snapshots come from the earlier same-day audit and are explicitly pinned, rather than claimed to be the latest release. Closed experimental PRs are not treated as shipped features. Search cannot establish the absence of undisclosed, unindexed or differently named work; this is an engineering literature review, not a patentability opinion.

## Closest prior art

| Work | Overlap with our approach | Distinction and implication |
|---|---|---|
| [Marconi](https://arxiv.org/abs/2411.19379), 2024 | Sparse hybrid-state admission at discovered branches; saved compute per byte informs eviction. | Broad cost-aware caching and learning branch demand are prior art. Our local placement objective differs from global eviction. |
| [Sparse Prefix Caching](https://arxiv.org/abs/2605.05219), 2026 | Expected overlap distribution, exact checkpoint-placement DP, empirical adaptation. | Strongest algorithmic overlap. Our nonlinear execution-cost objective and live capture integration are narrower engineering distinctions. |
| [vLLM PR 49574](https://github.com/vllm-project/vllm/pull/49574), July 2026 | Proactive semantic boundaries with exact token-prefix validation and bounded states. | Experimental, closed without merge. Defeats a broad first-semantic-checkpoint claim regardless of merge status. |
| [FreeToken](https://arxiv.org/abs/2608.16157), August 2026 | Semantic recurrent-state anchors for edited agent histories. | Public implementation; not merely a proposal. No matched performance comparison with our dense Apple model. |
| [SegLen](https://abdelfattah-lab.github.io/blogs/seglen/), 2026 | Replay-distance-aware eviction with recency. | A simpler policy can capture much of the benefit. Does not solve our within-request capture-placement objective. |
| [llama-server slot patches](https://github.com/wguerlich/llama-server-slot-patches) | Learned conversation boundaries, complete speculative-state persistence, reuse-aware slot management. | Source reveals a continuous cost score was replaced by class ordering. Sophistication can lose to a better-classified simple policy. |
| [mere.run](https://github.com/sawfwair/mere-run/blob/01feae347b640f1c9fa8bf8e7dfbf782497d2706/Sources/MereRunCore/Q35/Q35Generator%2BPrefill.swift) | Proactive stable conversation-prefix checkpoint, exact token-prefix check and preferential retention. | Local-Mac semantic-prefix policies already exist; the platform alone is not novelty. |
| [SuffixReplay](https://arxiv.org/abs/2609.33477), September 2026 | Addresses missing recurrent state at a partial-prefix hit. | Approximate reconstruction with a quality tradeoff; a different correctness contract from exact saved states. |

### Marconi: admission and eviction are established

Marconi identifies the full-attention/recurrent-state mismatch, uses radix-tree overlap to decide admissions, and combines recency with saved FLOPs per byte for eviction. It also tunes a policy parameter using recorded demand. It explicitly accepts losing the second occurrence of some input prefixes to avoid retaining low-value states. Our first-branch optimization revisits that tradeoff for this runtime; it does not discover the underlying problem. [Paper](https://arxiv.org/html/2411.19379v1)

The corresponding [vLLM PR 37898](https://github.com/vllm-project/vllm/pull/37898) merged on 10 June 2026, unlike the later experimental semantic PRs. Saved API metadata records the distinction. A miss-inclusive learning claim must therefore be qualified: observing an overlap that did not hit a retained recurrent state is already central to reactive branch admission.

### Sparse Prefix Caching: the DP claim must be narrowed

The paper minimizes expected replay distance under a checkpoint budget using an exact dynamic program and estimated overlap distributions. This is direct prior art for our broad optimizer concept. Its timing evaluation uses an RTX 2080 Super layer-group prototype, not our end-to-end deployment; checkpoint capture happens in separate untimed runs. Our experiment charges capture on the live request path. [Methods and algorithm](https://arxiv.org/html/2605.05219v1)

Source caveats matter: its HTML displays conflicting April/August dates around an identifier beginning `2605`, and sections specify both 128- and 64-token block granularity. We retain the retrieved version, do not infer a precise priority date from these inconsistencies, and do not compare its reported speed directly with ours. None of those caveats makes its disclosed placement algorithm ours.

### vLLM: semantic boundaries and a published negative result

PR 49574 proposes input, reasoning and response boundaries, aligned to materializable recurrent-state checkpoints, while preserving exact prefix hashing. It reports an input-end-only negative control: extra storage produced no extra hits on canonical replay traces. This is particularly relevant to our exact-repeat and 8K controls. The PR opened 23 July and closed 11 September without merging; its head is `feee95e2a344ea8a2de31715dcf42aa8fe9cf4ec`. [PR](https://github.com/vllm-project/vllm/pull/49574)

Related PRs [50503](https://github.com/vllm-project/vllm/pull/50503) and [50506](https://github.com/vllm-project/vllm/pull/50506) are also closed without merge. [50551](https://github.com/vllm-project/vllm/pull/50551) remains open. These are evidence of disclosed designs and implementation work, not proof of production behavior or successful results.

A separate [lookahead-aware hashing RFC](https://github.com/vllm-project/vllm/issues/50438) explains why target-prefix equality can be insufficient for a shifted draft cache. It proposes including a finalized following token in the cache contract. We must not simplify draft-state validity to “the prefix matches” when discussing other engines. Our patch relies on Splash's existing complete-state and identity machinery; it does not invent speculative-cache correctness.

### FreeToken: semantic anchors are already an implemented systems idea

The paper places recurrent checkpoints around thinking, tools and conversation boundaries so that edited histories can reuse surviving prefixes. Its source has separate recurrent-state LRU management and a tool-call-anchor snapshot path. Pinned files include `hybrid_radix_cache.py`, `linear_state_pool.py` and `scheduler/cache.py`. Our candidate extractor currently recognizes user-role markers; FreeToken's disclosed semantic coverage is broader. Its MoE/offload hardware and workloads cannot establish a speed ranking for our dense 27B Mac deployment. [Paper](https://arxiv.org/html/2608.16157v1), [implementation](https://github.com/FlashML-org/FreeToken)

### SegLen and the cost-model counterexample

SegLen ranks eviction candidates using replay distance and recency instead of detailed model-specific FLOP accounting. Its research blog and [PR 22172](https://github.com/sgl-project/sglang/pull/22172) report different experiment sets; neither should be copied into our results table. The PR is closed without merge in the retrieved metadata. The lesson is about the strength of a simple baseline, not a numerical comparison with our system.

The llama-server patch set is an especially useful counterexample. Its README calls slot management cost-aware. The pinned code says the earlier `n_rebuild × session × decay` score was replaced because its session signal confused unrelated questions about the same document with genuine conversation continuation. The implemented replacement uses classes and recency, with old tuning parameters unused. That is evidence against assuming that a more elaborate score is automatically better. [Pinned patch](https://github.com/wguerlich/llama-server-slot-patches/blob/3779565e96d5c39b02c89c67ff7f610e70538412/patches/upstream-3cf03257f/03-slot-management.patch)

### SuffixReplay is an alternative tradeoff, not an exactness-equivalent baseline

SuffixReplay reconstructs linear states from recent hidden-state inputs, relying on attenuation of distant history. Its design explicitly permits approximation and evaluates downstream quality. It could be relevant to a future quality/performance tradeoff study, but adopting its headline latency as an exact-cache comparator would be misleading. It was not installed or run. [Paper](https://arxiv.org/html/2609.33477v1)

## Existing engine machinery we should credit

These inspected files show that the main capability already exists upstream. File-level inspection cannot prove an engine lacks a comparable feature elsewhere.

| Engine and pinned revision | Relevant existing capability |
|---|---|
| [Splash `8a2b420`](https://github.com/incoai/splash/blob/8a2b42069923d483151372b615f6182c72c2b6cd/runtime/engine/Engine.cpp) | Lazy branch junctions, native replay/progress states, and target/draft state reuse. Our planner changes admission decisions around this machinery. |
| [TensorFold `63bef12`](https://github.com/ashhart/TensorFold/blob/63bef1260f1172058fbca0aeab13366d9b67373c/zig/src/core/prompt_cache.zig) | Budgeted history/shared/rewind marks, exact token and canonical-computation identity, draft lookahead dependencies. |
| [oMLX `013bc3f`](https://github.com/jundot/omlx/blob/013bc3f3a48fa9a4b7dffbfeb6cdc7c1face1c5d/omlx/cache/prefix_cache.py) | Prefix and recurrent-boundary cache management. A generic “hybrid prefix reuse” claim would duplicate existing functionality. |
| [llama.cpp `781dbc5`](https://github.com/ggml-org/llama.cpp/blob/781dbc5ac98921dbdb5e5b2ec5b7a50960e937d4/tools/server/server-context.cpp) | Server checkpoint and prompt-reuse machinery; our change is not a new state serialization primitive. |
| [MLX-LM `ba8a08f`](https://github.com/ml-explore/mlx-lm/blob/ba8a08fd2ed72bbc53de84f89933f91fe4743e4a/mlx_lm/models/cache.py) | Cache representations and model-dependent trim/restore constraints. MLX is a backend/library, not one universally specified serving policy. |

## Hardware-aware planning is also prior art; the placement objective is the distinction

SGLang's Kimi K3 engineering account describes a per-step speculative-verification planner combining draft confidence with a profiled, stair-stepped hardware cost curve. It also documents sparse branch checkpoints and exact raw-input replay for speculative recurrent state. Thus neither “measured nonlinear hardware costs” nor “a planner deciding which speculative work is worthwhile” is globally new. Those mechanisms optimize different decisions from our checkpoint-admission objective. [Primary engineering account](https://www.lmsys.org/blog/2026-07-27-kimi-k3-day0-support)

A GLM-5.3 serving implementation documents packed interior recurrent-state exports without a separate target forward for every checkpoint. That suggests a different optimization route: reduce the cost of capturing a useful state, rather than only choose fewer captures. Its model, hardware and implementation differ, so this is a research direction—not an available drop-in improvement for this Mac. [Pinned implementation report](https://github.com/local-inference-lab/rtx6kpro/blob/d24d7ce6b4eee06552d2d4b096a6418a4666c51e/models/glm-5.3-flash-community-r35.md)

For our engine, such a route would need complete target state, valid draft context, exact position/identity and compatible numerical behavior. No kernel export change was implemented or benchmarked here. A cost-aware planner must learn a new capture cost if the kernel changes; it should not preserve an expensive old scheduling assumption merely because its optimizer models that assumption precisely.

## What is actually implemented here

`CostAwareCheckpoint.hpp` solves a bounded shortest-path problem over candidate positions. Its objective charges today's split prefill and snapshot costs, plus expected future replay from the deepest retained predecessor. Each forecast outcome is charged once. Budgets constrain state count and bytes; mandatory native captures remain in every plan.

The execution model distinguishes short rows (up to 128), middle rows (129–511), bulk rows (512 and above), and 2,048-row chunks. This represents dispatch discontinuities: another checkpoint can move a tail out of the ANE route. Draft-context work is charged by the actual bounded window per segment, rather than assuming that every extra checkpoint materializes a fresh full window. Capture/restore observations and regularized command-wall estimates replace initialized priors as observations arrive.

In compact notation, the implemented objective is

`min_S C_current(S) + sum_b p_b [C_target(r_b, b + suffix_b) + C_draft(r_b, b + suffix_b) + C_restore(r_b)] + C_retention(S)`,

where `r_b` is the deepest selected/reusable predecessor for overlap `b`, and `S` obeys the state-count and byte limits. Mandatory progress captures are included in `C_current` even when they are not assumed to survive for a future hit. The live retention term is zero; a memory ceiling is not an opportunity-cost model. This formulation exposes the practical question: do the avoided future rows repay today's split, snapshot and extra draft work? It also exposes why an optimizer can be mathematically correct while choosing poorly under wrong probabilities or costs.

The live learner is modest. It retains only the previous prompt, compares exact token overlap, and updates four outcome counts in three request-shape buckets with a rolling 64-transition history. It is not a general per-conversation demand model or a full overlap-depth histogram. User-role markers guide candidates; exact native prefix identity authorizes reuse. No embedding similarity, translation, model-weight change, or new Metal arithmetic is involved.

The DP is optimal **only for its supplied candidates, forecast and cost model**. Its bounded quadratic search is not a new general-purpose DP technique. If costs are reduced to linear replay and fixed slots, the conceptual objective overlaps directly with sparse-prefix placement. The engineering extension is pricing discontinuous current execution and draft preparation in the same decision.

## Remaining weaknesses and where another approach can be better

1. **Complexity attribution:** the original heuristic has a 2K minimum. A planner can win below 2K simply by admitting a useful boundary. Three-arm superiority does not prove that fitting five cost coefficients or running the full optimizer is necessary. A later simple threshold/earlier-anchor ablation would isolate that question; it is not silently substituted into today's fixed experiment.
2. **Retention is not globally priced:** `retentionMsPerByte` is zero in the live configuration. Two states/512 MiB is a per-decision admission limit, not a lifetime cap on all additional cache states. The native global memory governor and eviction policy still decide what survives. Equal hard budgets can therefore produce different occupied memory and different displacement costs.
3. **Forecast bias:** adjacent engine requests are not always adjacent turns of the same conversation. Three shape buckets can mix unrelated users and harnesses. The fixed prior is useful for first branches but can spend memory on never-reused cold prompts. The llama-server counterexample shows why classification deserves attention.
4. **Cost identifiability:** target and draft work often co-vary. Regularization stabilizes a fit; it does not convert its coefficients into separately measured kernel timings. Threshold movement, long-context attention cost and changing load can invalidate a locally good estimate.
5. **Limited semantics:** `StablePrefix` and `ToolResult` enum names are not evidence that those boundaries are extracted by the live integration. The current path is user-marker based. Reasoning stripping, tool serialization and interleaved sessions remain under-tested.
6. **Exactness has an observed limitation:** saved-state identity is necessary, but altered execution chunking can also affect floating-point arithmetic. The initial randomized comparison matched 103/105 three-way output cases; two Python cases changed between `v // width` and `int(v) // width`, which are not equivalent for negative fractional values. Both were cold requests with zero reused tokens. The cause remains unisolated; numerical segmentation effects are a hypothesis, not a proven explanation. Exact output preservation must not be claimed from this experiment.
7. **No universal speed gain:** the planner does not eliminate a genuinely new long prefill or make weight reads in dense decoding cheaper. Any improvement to those must come from another mechanism.

## Defensible claim and publication decision

A defensible description is: **“A measured-cost checkpoint-admission extension for a specific Splash/DFlash2 deployment, evaluated with a randomized same-binary ablation.”** The strongest distinguishing element is the integration of current capture/split cost and draft-window cost with bounded branch forecasting, backed by decision receipts and complete request timings.

Do not claim the first semantic checkpoint planner, a novel general checkpoint-placement algorithm, globally optimal caching, or the fastest Qwen runtime. A useful systems contribution need not be globally unprecedented, but it must clearly identify its incremental mechanism and tradeoffs. The initial randomized comparison did not pass its predeclared complexity rule. Final conservative-policy results are reported separately; they cannot retroactively change that outcome. Broader superiority would still require matched model bytes, quantization, templates, backend settings, cache budgets, arrival patterns and correctness checks across engines.

This review supersedes broad novelty implications in the earlier article. The historical datasets remain available; their measurements are not rewritten to fit the newer conclusion.
