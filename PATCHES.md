# Patch provenance and validation

## Current Splash contribution draft

`patches/01-branch-anchor-latest.patch` targets the inspected `incoai/splash` main revision `8a2b42069923d483151372b615f6182c72c2b6cd`.

It adds the qualified `branchAnchor` helper, the opt-in marker parser, and a call into the current composite-state planner. The marker control is `SPLASH_BRANCH_MARKER_IDS`. The measured tokenizer encoded the final user header as `248045,846,198`; these values are configuration, not built into the helper. Other tokenizers must derive their own verified marker. The marker only selects a snapshot boundary; native prefix and image identity checks remain authoritative.

An upstream checkout can inspect application without changing its files:

```sh
git apply --check /path/to/patches/01-branch-anchor-latest.patch
```

The current-source draft was checked on a minimal copy of the pinned source and applied successfully. CPU helper tests passed. This is not current-source full-build, Metal, memory-admission, multimodal or real-model qualification. No production service was restarted for this audit.

A maintainer-facing version should take a frontend-provided user-message span, add native engine regression tests and use the project's current formatting/test workflow. This package deliberately keeps that review status visible.

## Exact historical qualified host changes

The measured host build started from an already modified source tree near `0d5a035ea26d1cc566e3c7ee4e08e5e06fa68cf7`. The patch chain is:

1. `patches/legacy/01-local-prerequisites.patch`: eight earlier local file changes, including short-prefill scratch plumbing and compiler compatibility.
2. `patches/legacy/02-qualified-host-delta.patch`: proactive branch placement, independent register prefill, opt-in bulk policy, and calibration handling.

Both patches apply sequentially to that older source. The second is a delta against the local parent, not a stand-alone clean-upstream patch. These historical diffs include disabled experimental fusion hooks for exact source disclosure; the qualified preset did **not** enable those hooks. The source phase, matrix geometry and numeric guards are part of the measured implementation.

The measured build reused an existing host archive for unchanged translation units and a stock precompiled Metal library. Hashes are in `data/build-provenance.json`. Those artifacts and weights are not redistributed. The source commit alone does not establish the build provenance of every reused unit. A new clean build can evaluate the policy but is not automatically the exact measured executable.

Current Splash uses a changed quantized layout and a `LinearGguf` policy. The legacy register-prefill and wide-prefill patch is not offered as a drop-in change against current main. No latency or throughput measurement is transferred to an untested port.

## Secondary TensorFold adaptation

`secondary/indexed_draft_head.py` targets the older TensorFold Python/MLX fragment-kernel interface. It replaces only weight-row addressing, checks quantization and input type, and retains a source-pattern guard. It imports upstream kernel generation rather than copying an entire shader.

It does not load into the measured Splash decoder or the current native Zig TensorFold engine. The public evidence covers 14 numerical comparisons and a small historical two-repetition/domain decode comparison. A native port would require new tests and benchmarking.
