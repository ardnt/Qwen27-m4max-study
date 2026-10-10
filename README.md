# Hybrid 27B on an M4 Max: a measured Splash cache and scheduling fix

This package documents a local Qwen3.8-27B Q4 optimization on an M4 Max with 36 GiB of memory. It contains source changes, synthetic prompts, individual measurements, offline analysis, a contribution proposal, and a technical article.

Repository: [ardnt/Qwen27-m4max-study](https://github.com/ardnt/Qwen27-m4max-study). The [technical article](https://github.com/ardnt/Qwen27-m4max-study/blob/main/technical-article.md), patches and individual results are included here. A complete downloadable source bundle is available in `artifacts/`; its SHA-256 accompanies it. `MANIFEST.json` covers the 35 source-package files, excluding the manifest itself and the external bundle.

The strongest result is **first changed 8K follow-up TTFT: 27.561 s → 0.427 s** in seven paired fixtures under the measured cache pressure. This is a reduction in repeated prompt processing, not a 64.5× improvement in sustained generation. An earlier three-pair rebuilt control with a surviving 4K checkpoint measured 14.599 s → 0.602 s. Both conditions matter.

There is no claim of inventing hybrid prefix caching or conversation-boundary checkpoints. Marconi, current llama.cpp, and current TensorFold have closely related techniques. The contribution is a specific proactive checkpoint policy for Splash, its interaction with DFlash2 state, and measured scheduling changes on this Mac.

- [Architecture and prior-art audit](architecture-review.md)
- [Technical article](technical-article.md)
- [Draft Splash contribution](upstream-issue.md)
- [Patch provenance and application](PATCHES.md)
- [Secondary indexed draft-head work](secondary/README.md)
- [Individual measurements](data/qualification.jsonl), [recorded statistics](data/recorded-summary.json), and [public revision pins](data/public-revisions.json)

Inspect the saved evidence without running inference:

```sh
python3 analyze.py
c++ -std=c++20 -O2 tests/branch_anchor_test.cpp -o /tmp/branch-anchor-test
/tmp/branch-anchor-test
```

The compiler command creates only a standalone CPU boundary test. It does not exercise the GPU, instantiate a model, or prove full state-restoration correctness.

`benchmark.py` can send the fixed corpus to an already running OpenAI-compatible endpoint. It never launches, replaces, restarts, unloads, or reconfigures a service. Select a suite explicitly; see `python3 benchmark.py --help`. Independent users must verify their hardware, checkpoint, tokenizer, precision, draft, cache pressure, ANE policy, and timing boundaries before comparing numbers. The script is not an automatic reproduction of the native binary's build provenance or memory instrumentation.

The package excludes model weights, executable binaries, compiled Metal libraries, precompiled archives, production configuration, credentials, personal conversations, local account identifiers, and private network addresses. The native patch against current Splash is an apply-checked draft; it has not received a new full build, Metal test run, or real-model qualification on that revision.
