# Proposal: proactively retain a composite state before the final user turn

A first sibling question can miss Splash's final replay state even though almost all its input is shared. In a hybrid Qwen27B + DFlash2 setup, a usable resume boundary needs full-attention KV, recurrent state and the complete draft window together. A progress checkpoint may be too early or already evicted; a lazy junction becomes available only after the first branch has paid for replay.

This proposal schedules one ordinary composite state before the final user turn during the original prefill. The local implementation uses an opt-in tokenizer-verified marker, rounds down to the KV page grid and requires at least one draft window of potential reuse. Existing prefix/image identity checks, admission and eviction remain unchanged. Prefer an explicit frontend message-span boundary for an upstream API.

Public materials: [source and reproducibility package](https://github.com/ardnt/Qwen27-m4max-study), [technical article](https://github.com/ardnt/Qwen27-m4max-study/blob/main/technical-article.md), [patch provenance](https://github.com/ardnt/Qwen27-m4max-study/blob/main/PATCHES.md), and [individual measurements](https://github.com/ardnt/Qwen27-m4max-study/blob/main/data/qualification.jsonl).

## Evidence on an M4 Max / 36 GiB

Target: installed orcarouter uncensored Qwen3.8-27B affine Q4/group64, 64 hybrid layers, context 65536. Draft: `z-lab/Qwen3.8-27B-DFlash2@50307d4c4cde6860d4eee73e2547cd786fe8e8a4`, block eight / seven proposals, full 2048-token window, Q4 runtime affine projections. Splash distributed 1.3.0, BF16 KV, 25 GiB native memory cap, one sequential request, SSD prefix persistence disabled in both arms.

| First changed 8K follow-up, seven paired fixtures | Stock | Enhanced |
|---|---:|---:|
| Client TTFT median | 27.5605 s | 0.4271 s |
| Client TTFT observed p95 | 28.1144 s | 0.4340 s |
| Reused input tokens | 0 | 8192 |
| Target prefill rows | 8238–8239 | 46–47 |
| Draft context materialization rows | 4128 | 32 |

An earlier three-pair rebuilt-control screen retained a stock 4K checkpoint and measured 14.599 s → 0.602 s. The larger headline ratio depends on measured cache pressure and is not a general generation-speed claim. All seven changed-turn outputs match exactly. The complete enhanced preset includes a separate short-prefill scheduling change; the counter reductions identify the state-placement effect, while the final 0.427 s latency cannot be attributed to the anchor alone.

The main qualification has 98 measured requests plus two warmups. Seven distinct fixtures per cell, greedy sampling, fixed seed, streaming, thinking disabled. Stock runs before enhanced, so small timing gains retain ordering/thermal confounding. Sampled family peak 25.50 GiB, swap 0, pressure normal. No new draft-policy sustained speedup or intelligence gain was established.

## Patch and validation status

- [The current-source patch](https://github.com/ardnt/Qwen27-m4max-study/blob/main/patches/01-branch-anchor-latest.patch) targets inspected Splash main `8a2b42069923d483151372b615f6182c72c2b6cd`. It adds the exact locally qualified placement helper and its planner call to the current source.
- The current-source patch passes an offline application check. [Standalone CPU tests](https://github.com/ardnt/Qwen27-m4max-study/blob/main/tests/branch_anchor_test.cpp) compare boundary selection with an independent oracle and check sibling-prefix alignment and invalid inputs.
- It is a **draft**: no new current-source build, `make check`, Metal test or real-model run was performed. This audit preserves the running service and does not repeat the benchmark.
- [The legacy patches](https://github.com/ardnt/Qwen27-m4max-study/tree/main/patches/legacy) preserve the local prerequisite and qualified host-delta chain against the older checkout. Changed host units were linked with a pinned precompiled archive; the nearby source commit does not prove all unchanged units' build provenance.
- [Individual results](https://github.com/ardnt/Qwen27-m4max-study/blob/main/data/qualification.jsonl), [synthetic prompts](https://github.com/ardnt/Qwen27-m4max-study/blob/main/data/prompts.json.gz), [output pairs](https://github.com/ardnt/Qwen27-m4max-study/blob/main/data/output-pairs.json) and [the analysis script](https://github.com/ardnt/Qwen27-m4max-study/blob/main/analyze.py) let reviewers inspect every primary sample and recompute the statistics. [The standalone benchmark client](https://github.com/ardnt/Qwen27-m4max-study/blob/main/benchmark.py) can exercise only these mechanisms against a separately prepared endpoint.

The patch changes checkpoint placement rather than native verification or kernel arithmetic. A follow-up validation should compare new priming cost, first sibling reuse, repeated-turn reuse, arbitrary suffix edits, multimodal identities and low-memory admission on current Splash. Those current-revision checks remain outstanding.

## Related work

This proposal credits [Marconi](https://arxiv.org/abs/2411.19379), [llama.cpp's message-start checkpoints and saved draft state](https://github.com/ggml-org/llama.cpp/blob/781dbc5ac98921dbdb5e5b2ec5b7a50960e937d4/tools/server/server-context.cpp), and [TensorFold's `beginRewind`](https://github.com/ashhart/TensorFold/blob/63bef1260f1172058fbca0aeab13366d9b67373c/zig/src/core/prompt_cache.zig). [oMLX](https://github.com/jundot/omlx/releases) also preserves recurrent draft-prefix state. The idea is established; the proposed contribution is integrating its useful boundary into Splash's existing composite-state planner.

[Splash's contribution guidance](https://github.com/incoai/splash/blob/8a2b42069923d483151372b615f6182c72c2b6cd/CONTRIBUTING.md) asks for an issue first for larger changes. This draft makes the implementation and evidence concrete before an upstream discussion.
