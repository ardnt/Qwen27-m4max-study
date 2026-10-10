# Why a cached 27B conversation still took 27 seconds to start

On a 36 GiB M4 Max, a local Qwen3.8-27B Q4 installation could answer an exact repeated prompt quickly yet stall when only the final question changed. The model weights were already loaded. Much of the attention cache was reusable. Nevertheless, the first changed 8K request took a median 27.561 seconds to emit text in the measured workload.

An additional checkpoint before the final user turn reduced that median to 0.427 seconds. The useful finding is where the runtime saves resumable state, not a claim that a 27B model suddenly generates text 64 times faster.

## A cache hit needs more than matching text

The measured target combines 16 full-attention layers with 48 GatedDeltaNet layers. Attention retains token-indexed KV. Recurrent layers update state in place; the final state after an old question cannot simply be rewound to before that question. DFlash2 also needs a complete context window aligned with the target's restored state.

The runtime therefore needs a compatible bundle at the chosen prefix boundary:

```text
shared token/image identity
           ↓
attention KV + recurrent state + complete draft context
           ↓
resume from that boundary, prefill only the new tail
```

Splash already implements composite-state capture and restoration. Its tested stock policy generally retained a final replay state and disposable progress checkpoints. The final replay state could include the previous question. A sibling question diverged earlier, and the progress checkpoint needed to resume that branch might have been reclaimed.

## Place state before the likely divergence

The local change finds the last tokenizer-verified user header and rounds its position down to Splash's 32-token page boundary. It schedules an ordinary composite snapshot there when the boundary is at least 2048 tokens beyond the current resume point. That threshold avoids paying for another snapshot when little work can be saved.

The header is only a scheduling hint. Existing prefix and image identities still decide whether the saved state matches. Existing memory admission and eviction remain in charge. The new checkpoint is not pinned outside the runtime's memory budget.

Preserving the draft window matters as much as preserving the target's recurrent tensors. A nominal target cache hit that must reconstruct DFlash context can still pay substantial setup work. In the changed-turn measurements, target prefill fell from 8238–8239 rows to 46–47, and draft context materialization fell from 4128 rows to 32.

## Use the right kernel route for what remains

After successful prefix reuse, prefill is a small matrix problem. The historical Splash implementation had eight-row Q4 register kernels, but the local short-prefill route inherited the four physical decode lanes and stopped at 32 rows.

A separate `RegisterPrefill` phase schedules up to 128 independent prefill rows in eight-row tiles. Matrix row tiles are not model request lanes. Counting those independent tiles when choosing K splits avoids partial-sum reductions when the GPU already has enough independent work. Scratch sizes cover every supported plan, while the physical decode-lane guard remains unchanged.

This reuses existing shader arithmetic. The qualified preset keeps the original FP32 up-projection/SiLU prefill epilogue; a faster fusion that rounded earlier was excluded. An opt-in wider bulk tile and revalidated ANE split produced a much smaller cold-prefill difference.

Current Splash has since changed its quantized weight layout and dispatch. The public package supplies the measured historical patch chain and a separate current-source branch-anchor draft. The short-prefill policy needs a new format-aware port and qualification before its measurements can be attributed to current upstream code.

## The measurements, with their boundaries

Seven distinct fixtures were paired between stock and enhanced. Generation used temperature zero, a fixed seed, streaming and disabled thinking. Branch prime → changed suffix → exact repeat stayed contiguous. The measured stock arm ran before the enhanced arm, so small differences can still reflect time or thermal effects.

| Workload | Stock TTFT median | Enhanced TTFT median |
|---|---:|---:|
| First changed 8K suffix, measured cache pressure | 27.561 s | 0.427 s |
| Exact repeated 8K prompt | 0.323 s | 0.207 s |
| Completely new 8K prompt | 27.081 s | 26.574 s |

In the main first-branch comparison stock reused zero tokens and enhanced reused 8192. An earlier three-pair rebuilt-control screen retained a stock 4096-token checkpoint and measured 14.599 s → 0.602 s. The headline ratio consequently depends on cache retention. It must not be described as the speedup of an already fully cached request.

All seven changed-turn outputs and seven repeated outputs matched between arms. The complete 49-pair corpus matched in 28 pairs; tiling changes can alter floating-point reductions and greedy sequences. Peak sampled process-family footprint was 25.50 GiB, with zero swap and normal observed pressure. No GPU frequency or temperature measurements establish the absence of all thermal effects.

New English, Arabic and Python generation measured about 33.8, 26.7 and 79.4 tok/s in the enhanced preset. Native draft acceptance was about 19%, 11% and 61%. Alternate draft selection and shorter draft attention windows did not give a consistent improvement. Preserving draft state accelerated setup; it did not solve low acceptance on free-form Arabic or English.

## Related work changes the claim

[Marconi](https://arxiv.org/abs/2411.19379) established hybrid prefix caching and reuse-aware cache policy before this work. Current [llama.cpp](https://github.com/ggml-org/llama.cpp/blob/781dbc5ac98921dbdb5e5b2ec5b7a50960e937d4/tools/server/server-context.cpp) explicitly treats the latest user-message boundary as a checkpoint opportunity and saves draft state. Current [TensorFold](https://github.com/ashhart/TensorFold/blob/63bef1260f1172058fbca0aeab13366d9b67373c/zig/src/core/prompt_cache.zig) has a rewind state before the latest user message. [oMLX](https://github.com/jundot/omlx/releases) has recurrent boundary snapshots and reusable speculative draft state.

The contribution is a localized Splash implementation and an instrumented M4 case study, with these projects credited. It is not a claim to have invented conversation checkpoints, DFlash2, ANE execution or a new model architecture.

A second local adaptation reads selected vocabulary rows directly from existing quantized draft-head weights. In the older TensorFold/MLX path it avoided a 382.7 MiB duplicate allocation and matched the materialized selected-head result in 14 checks. That is a separate memory result, not an additional benefit inside the measured Splash decoder.

## What a useful upstream contribution looks like

A maintainer can review a small branch-placement patch, a fixed synthetic corpus, individual results and the target/draft work counters. A frontend-provided message boundary would be a cleaner long-term interface than an environment marker. The scheduler can continue to choose checkpoints under its existing memory policy.

The remaining bottlenecks are visible: completely new 8K prompts still take around 26.6 seconds, and draft acceptance remains content-dependent. This work improves a specific, common conversation failure. It provides no current cross-runtime speed ranking or measured intelligence gain. The full evidence and source provenance accompany the article so those limits remain inspectable.
