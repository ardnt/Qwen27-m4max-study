# Reconciliation of the conversation's earlier answers

This review read all 34 available turns and all 31 completed answers, from the
initial runtime installation through the 47-second diagnosis. This document
supersedes overbroad interpretations; past chat messages themselves cannot be
edited. It is not a fresh live qualification of every earlier integration.
Private API settings, credentials, chat text, photos and account details are not
republished. These rows cover the earlier answers by topic, including updates
that superseded earlier answers.

| Earlier answer or claim | Correct scope / current interpretation | Included evidence or disposition |
|---|---|---|
| Initial TensorFold 0.6.5 + DFlash2 was “fastest” | Fastest of the locally tested presets at that time; not a universal ranking. The later active 27B profile uses Splash. | Historical installation context; newer controlled studies govern headline claims. |
| 48 → 14 tok/s regression / Arabic drafter fix | Workload-dependent Arabic acceptance failure; full vocabulary/adaptive fallback belonged to the earlier TensorFold path. 48 tok/s was not guaranteed Arabic speed. | Retained as integration history; not attributed to the current Splash planner. |
| ArabicFast translation | Optional English generation + TranslateGemma; story completion improved, technical text did not, first words could be later and semantics/tool choices could differ. | Not evidence of better native Arabic decoding or unchanged quality; auxiliary model is not part of planner tests. |
| Cloud Qwen image integration | Local unit checks only; cloud generation was untested and required credentials. User later requested local operation. | Superseded for this user's requested workflow; no cloud performance gain claimed. |
| Local image generation/edit/enhance | Historical MLX image integration; image work can still contend for GPU despite yielding to chat. | Feature integration, not zero-cost coexistence or a new inference algorithm. Personal generated images excluded. |
| Pillow image failure | Cross-version Python path contamination, corrected by isolating the image worker; historical real generation succeeded. | Useful environment-isolation lesson, not a model/kernel improvement. |
| 35B won initial model comparison / CLEF | Short local samples and eight reasoning checks; no general intelligence ranking. Optional structured scoring did not deploy CLEF as another resident chat model. | Superseded as default by the user's later 27B choice; not added to 27B results. |
| Tool call failed after internal reasoning | Unknown tool name was suppressed at streaming handoff; historical parser/handoff repair let the agent reject/correct it. | Integration fix, not increased model intelligence; no private query replay published. |
| MTP draft-head projection gains | Short 35B tests with identical hashes; distinct from 27B DFlash2. | Do not transfer 131→137 or 160→175 tok/s to this 27B path. |
| Prompt preparation 29.8→1.8ms | Message-segment tokenization cache, a CPU preparation timer on earlier TensorFold. 228 token comparisons and 18 outputs were reported equal. | Distinct from GPU prefill/TTFT; architecture audit already records this contribution. |
| First output 208→34ms, follow-up 251→110ms | Earlier **35B**, reasoning disabled, specific cache/timing boundaries. | Not a current 27B TTFT claim. |
| Copying code 281→426 and documents 490→557 tok/s | Earlier **35B copying/reconstruction** workloads. | Not ordinary new generation, not 27B DFlash2 throughput; later full benchmark reports separately verified copying. |
| Dense cached replies 1.15→0.268s / 1.19→0.271s | Earlier 27B one-token follow-up fixtures; history rendering/eviction improvements. | Not sustained output or all-context guarantee. |
| 35B long history 33.64→1.25s | Earlier 35B cache-reuse condition; later source changes/model states differ. | Historical only; not additive with Splash gains. |
| Nine-minute clock reply fixed to 0.29s | A clock shortcut and earlier compaction produced that result. User rejected shortcuts. | Both shortcut and tighter compaction change were subsequently removed. **Do not present this as an inference-engine speedup or retained fix.** |
| Earlier compaction rollback | 28K cap removed, previous protected-message settings restored; 65,536 serving limit retained. | Overrides the preceding clock/compaction answer. Long-history latency was explicitly still unresolved. |
| Remote API setup/key answers and authentication fix | Local authentication, model listing and streaming were tested; phone confirmation was not always available. | Credentials and private addresses excluded. No claim of present remote reachability without a new remote test. |
| WonderChat “file is directory” | Failure appeared before a request reached the server; not resolved in the saved answer. | **Unresolved client issue**, not silently marked fixed. |
| API max_tokens compatibility/cancellation | Larger limits, protocol adapters and cancellation handling were implemented; a 35B cancellation fixture improved 4.10→1.15s. | API/runtime integration, not planner throughput. |
| API rejected image parts | Local vision feature caching/lazy encoder and draft-state reload fix; historical client/server tests. | Separate multimodal integration. Semantic planner's measured corpus is text-only and images use fallback. |
| Splash 1.3 installation | Earlier 8.6K cold prompt and repeated-photo comparisons; complete runtime presets. | Precedes the later controlled 27B experiments; don't multiply the speedups. |
| Hermes /stats after update | Merge/stash recovery restored command/footer, historical 28 tests. | Operational compatibility, not inference optimization. |
| ML Drift 9.2% improvement | Synthetic four-projection 512-row GPU chain, FP16 Drift/MLX vs BF16 Splash, without Splash ANE. Decode remained faster in Splash. | **Now included:** [prototype, patches and raw results](secondary/drift/README.md). Not deployed full-Qwen acceleration. |
| Saudi Arabic voice | Local ASR/TTS configured; warmed natural TTS ≈1.2s for 8s audio, with much slower cold startup. First real mic/Telegram exchange remained untested. | Not “best” independently established; voice workers aren't part of decoder benchmarks. |
| Initial safe benchmark | Actually found resident 35B and stopped under disk guard. | That partial report is not a 27B benchmark. |
| Full 27B benchmark | 535 measured / 563 saved, 1K–64K, twenty 8K follow-ups; warmed raw-generation prefixes explicitly separate from cold prefill. | **Now included:** [historical data and validator](historical/full-benchmark/README.md). |
| Full benchmark restoration | Production restored, but one old isolated cache file was lost in setup. | Preserve the exception; do not claim every file was restored. |
| Three-path fix | 8K first-branch TTFT 27.56→0.427s under measured cache pressure, new retained composite checkpoint plus scheduling. | [Original article](technical-article.md); strong avoided-work result, not 64.5× generation speed. |
| Architecture superiority / sharing answers | Prior-art overlap acknowledged, current-main patch only application/CPU checked. Publication occurred; upstream issue is a proposal, not a merge. | [Architecture audit](architecture-review.md), [patch status](PATCHES.md). No global priority/ranking claim. |
| Cost-aware planner | 96 measured requests, short-branch gains, cold creation regression, identical paired outputs; fixed arm order and differing host hashes. | [Full planner study](semantic/README.md). The earlier answer said **17 decisions; ledger actually contains 18**. |
| Make 27B default | Later local selection/config change superseded the earlier 35B default. | Operational setting, not evidence of comparative intelligence; no selection changed in this publication review. |
| 47-second latest reply | 14,022 cold input tokens, 46.3s before model output, about 1.4s generation; deployment cleared RAM cache and tiny startup smoke did not warm agent context. | Diagnosed, **not permanently fixed**. Reused-prefix visible answer was ≈1.07s in a different controlled request, not an exact replay. |

## What remains worth pursuing

The measured 129–511-row prefill route, exact stable-prefix warming after restart,
and global retained-state opportunity cost are distinct open problems. The
planner does not solve genuinely cold prefill, lost RAM state, translation
quality, remote app filesystem errors or voice latency. New improvements need
focused tests with unchanged timing boundaries and numerical/state checks.

The cost-aware placement implementation is a useful engineering experiment, but
its added complexity is not established as necessary. The later randomized study
missed its predeclared threshold and found output differences; see
[controlled comparisons](controlled/README.md) and [prior art](PRIOR_ART.md). The Drift mixed-precision route and INT4 allocation correction are
separate useful prototypes. The historical indexed draft head already published
in `secondary/` avoids 382.7 MiB in the older MLX path; it is not active inside
Splash and its modest n=2 speed differences remain exploratory.


## Later randomized comparison correction

The cost-aware planner's initial randomized comparison reduced median paired
whole-block latency by 8.66% versus the original heuristic and 23.76% versus the
stock checkpoint policy within one tuned binary. It did not meet the declared
10% improvement requirement against the heuristic. Unrelated cold requests
regressed by about 10%, and two of 105 three-way output pairs differed. Therefore
neither universal output identity nor a universally better policy is established.

Broad first-semantic-checkpoint and first-cost-aware-placement implications are
withdrawn in light of the [closer prior art](PRIOR_ART.md). Global performance
superiority was not tested. The final conservative candidate is a separate
experiment with its own same-binary simple-policy comparator and fresh prompts;
it does not erase the earlier negative results.
