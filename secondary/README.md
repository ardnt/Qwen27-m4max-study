# Direct indexed quantized draft-head projection

The older local TensorFold/MLX path uses a selected draft vocabulary, including Arabic BPE units and special tokens. Materializing another selected quantized head duplicates packed weights, scales and biases. `indexed_draft_head.py` instead reads selected rows directly from the original head using the existing fragment matmul arithmetic.

The target's full-vocabulary projection and verification are unchanged. This is a draft proposal adaptation; vocabulary restriction can change draft acceptance and cannot establish an intelligence benefit.

Saved evidence from 6 October 2026:

- 139,328 selected vocabulary IDs.
- 401,264,640 bytes / 382.7 MiB of duplicate selected-head storage avoided, relative to materialization.
- 14 real-checkpoint numerical comparisons matched the materialized selected head exactly: seven row geometries, two seeds.
- In two repetitions per mode/domain, effective decode medians changed from 37.93 to 37.94 tok/s for English, 53.20 to 54.03 for code, and 29.67 to 30.15 for Arabic. These are modest observations, not a rigorous current-runtime speed claim.
- The saved 24-run experiment, including excluded fusion variants, reports identical 192-token outputs; the public A/B subset contains only the baseline/head 12 runs.

Receipts are `data/legacy-indexed-head-checks.json` and `data/legacy-indexed-head-ab.json`. Historical compiler/interface dependencies and restricted shapes make this a reference implementation, not an installation script.

Current [TensorFold native draft-head source](https://github.com/ashhart/TensorFold/blob/63bef1260f1172058fbca0aeab13366d9b67373c/zig/src/families/qwen27/dflash/runtime_head.zig) materializes selected weight spans. A native equivalent might reduce that duplicate storage, but the native arithmetic/layout would need independent validation. Indexing quantized matrix rows is not claimed as a new fundamental algorithm.
