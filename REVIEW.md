# Publication review — 10 October 2026

> Historical evidence: see the [new randomized comparisons](controlled/README.md) and [prior-art correction](PRIOR_ART.md). The later comparison found cold-request regressions and two differing Python outputs; output identity here applies only to this document’s original corpus.

The original 98-request study was recomputed unchanged. A distinct 96-request
cost-aware planner study is now exported with its fixed synthetic corpus,
individual rows, native decision receipts, historical source patch, portable
headers, exhaustive CPU oracle and controller tests.

## Corrections

1. Missing, non-finite or reset speculative counters now remain unavailable;
   partial data cannot silently become a measured zero or acceptance rate.
2. The portable client rejects incomplete SSE responses and reset counter
   intervals. Regression tests simulate failures without contacting a model.
3. Planner evidence checks now recompute output hashes, expected arithmetic,
   syntax and complete off/on pairing rather than trusting saved success flags.
4. The exported controller validates geometry before dividing by chunk/bulk
   alignment. A zero-sized configuration returns Invalid rather than crashing.
   This defensive patch follows the measured source patch; historical GPU
   numbers are not attributed to the correction.
5. The model label is distinguished from its `qwen3_5` architecture and unverified
   training lineage. Historic archive/build and fixed-order confounders remain
   explicit. An obsolete “proposed only” description now points to implemented
   planner work, without changing the original study's claims.
6. The old downloadable ZIP is clearly marked as the initial publication.
   Current source, data and docs are covered by a regenerated integrity manifest.
7. Linux/macOS CI verifies evidence and CPU code without loading models. Neither
   this review nor CI changes production or sends real agent tools.

## What is ready and what remains

Ready to share as an experimental engineering contribution: source, tests,
synthetic measurements, honest limitations, prior-art comparison and a technical
article. The four-stage historical patch chain is application-checked. The
standalone planner needs only C++20; analysis needs only Python's standard library.

Not claimed complete: latest-upstream native port/full build, broad GPU
state-restoration/numerical qualification, same-binary randomized inference A/B,
quality evaluations, 32K/64K planner tests, global eviction opportunity pricing,
frontend-provided tool/document spans, and cold-start acceleration. These are
research/integration work, not missing proof that can be supplied by editorial
changes. The running Hermes service was not restarted or modified in this review.

## Conversation-wide follow-up

All 34 available turns and 31 completed answers were reviewed. The resulting
[claim reconciliation](CLAIM_RECONCILIATION.md) records superseded defaults, the
reverted clock shortcut, distinct 35B timing/copying claims, incomplete features,
quality failures, and the unresolved cold-start issue. Two important omissions
were added: the 535-measurement historical baseline with an offline validator,
and the separate ML Drift prototype with deterministic probes and patches.
