# Cost-aware checkpoints for a hybrid 27B on Apple Silicon

A reproducible engineering study of exact prefix reuse in Splash with DFlash2,
on an M4 Max with 36 GiB. The contribution is a **bounded checkpoint planner
that prices target dispatch geometry, draft-state materialization and future
branch reuse together**. It learns from misses as well as hits. This repository
contains code, synthetic inputs, individual measurements, patches and tests.

**Start here:** [technical article](semantic/ARTICLE.md),
[planner results and reproduction](semantic/README.md),
[review findings](REVIEW.md), and [conversation claim reconciliation](CLAIM_RECONCILIATION.md).

Also included: the previously omitted [full 1K–64K baseline](historical/full-benchmark/README.md)
and the separate [ML Drift kernel prototype](secondary/drift/README.md).

## What was measured

These are two separate experiments. Their speedups must not be multiplied.

| Experiment | Matched workload | Median TTFT before → after | Evidence |
|---|---|---:|---|
| Original heuristic, 98 measured requests | First changed 8K question under measured cache pressure, n=7/arm | 27.561s → 0.427s | [Original article](technical-article.md) |
| Cost-aware planner, 96 measured requests | Changed 1K question, n=7/arm | 4.125s → 1.218s | [Planner report](semantic/README.md) |
| Cost-aware planner | Cold 1K request that creates the checkpoint, n=7/arm | 4.131s → 4.635s | Upfront cost, included in sequence totals |

For the planner, the complete prime + changed question + repeat sequence saved
**2.416 seconds median per paired fixture**, including checkpoint creation.
The gain is avoided prefill work. Neither experiment establishes a new decoding
kernel, increased intelligence or a ranking against other runtimes.

The installed model's label is `Qwen3.8-27B-Uncensored-Splash-1.3`, Q4/group64.
Its configuration declares `Qwen3_5ForConditionalGeneration` / `qwen3_5`.
The exact public target checkpoint revision and training provenance remain
unverified. Compare architecture, weight hashes/revisions, quantization and
settings, not this product label alone.

## Verify without a GPU or model

Python 3.10+ and a C++20 compiler are sufficient:

```sh
python3 verify.py
```

This checks distributed-file hashes, recomputes both studies, validates the
synthetic outputs, tests incomplete streams/counters, and runs the independent
checkpoint subset oracle and controller tests. It sends no inference requests
and controls no service. CI runs these checks on Linux and macOS.

To send the **48 fixed planner cases sequentially** to an already-running,
explicitly configured endpoint, use the portable client:

```sh
python3 benchmark.py --base-url http://localhost:8001/v1   --model YOUR_MODEL --label planner-on --suite semantic --output on.jsonl
```

Read the [reproduction limitations](semantic/README.md#reproduction) first.
The script does not change planner mode, launch a server, clear caches, or
execute agent tools. A portable API run alone cannot reproduce native build
provenance, planner receipts or sampled process-family memory.

## Attribution and status

Conversation-boundary caching and distribution-aware checkpoint optimization
have close [prior art](semantic/ARTICLE.md#prior-art-and-scope). Our claim is a
specific, inspectable integration of those ideas with Splash dispatch costs
and complete DFlash2 state, not invention of prefix caching or dynamic programming.

The [historical native patch chain](semantic/README.md#native-integration)
is apply-checked against its pinned base. The exported controller includes a
separate input-validation fix, CPU-tested after the measured study; no new GPU
performance is attributed to that fix. A full clean build and qualification
against current upstream Splash remain uncompleted integration work.

Original [architecture audit](architecture-review.md),
[metric definitions](METRICS.md), [patch provenance](PATCHES.md), and
[upstream heuristic discussion #361](https://github.com/incoai/splash/issues/361)
are retained. The ZIP in `artifacts/` is the **initial heuristic publication**,
not this updated tree; use GitHub's source archive for the current version.
`MANIFEST.json` covers distributed files except itself, including that historical ZIP.
No weights, native executables, private conversations or production configuration
are distributed.
