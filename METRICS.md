# Timing and counter definitions

The definitions below describe the historical datasets/client. The new
`controlled/original` and `controlled/final` experiments explicitly include
connection setup in client TTFT/E2E: their clock starts before connect/POST and
ends at SSE DONE. Serialization and model startup remain excluded.
`controlled/replay.py` uses that newer boundary; the historical client keeps its
old boundary. Do not silently compare these client timings as identical metrics.

Controlled code throughput uses per-request native output-counter / decode-wall
deltas, then reports the median across seven short code samples. Its acceptance
table reports the median of per-request accepted/proposed ratios, not a ratio of
summed counters. Raw tiny-answer stream rates are preserved but suppressed from
headline tables because speculative-batch delivery can make them meaningless.

- `client_ttft`: time from sending the inference request to the first nonempty generated content or reasoning delta, using `perf_counter_ns`.
- `client_visible`: time to the first nonempty answer-content delta. Thinking was disabled in the saved primary corpus; both timings coincide there.
- `client_e2e`: request send through stream completion. Connection setup precedes this interval in the portable script.
- `json_serialization_ns`: client body serialization; it is not server prompt rendering.
- `backend_decode_tps`: native server-reported subsequent-output throughput. Its numerator excludes the first speculative burst, which can contain multiple tokens. It is effective speculative throughput, not target-only unassisted decoding.
- Saved `client_decode_tps` / summary `client_stream_tps`: a wire chunk-boundary estimate with uncertain first-burst token accounting. It is retained for transparency and is not the headline decode measurement. The portable script leaves this metric unavailable.
- `effective_output_tps`: all actual completion tokens divided by client end-to-end time, including prefill and request latency.
- `prefill_command_wall_tps`: native `splash_prefill_input_tokens_total` delta divided by native summed `splash_prefill_wall_milliseconds_total` delta. This includes command wall time, not isolated GPU shader time.
- `prompt_phase_tps`: server prompt-phase rate, including its first-output boundary; this is not the same timer as native prefill commands.
- `decode_cycle_wall_tps`: all native output-counter tokens divided by summed decoding-cycle wall time; includes the initial cycle.
- Draft acceptance: sum of accepted proposal counters divided by sum of proposed counters. Missing counters make acceptance unavailable; throughput does not estimate it.
- `output_per_iteration`: actual output tokens divided by native decode-batch counter deltas, with the native initial/final iteration convention.
- Peak family memory: maximum of sampled process-family physical-footprint sums; shared accounting can overlap and 0.5-second sampling can miss short peaks. The portable script records system pressure/swap on macOS but does not fabricate process-family peak memory.
- p90/p95: nearest rank. With seven distinct fixtures, both are the observed maximum. The fixtures vary, so standard deviation includes content variation.

The original qualification instrumented a separate local process and native metrics; the portable script cannot establish its exact memory or binary provenance automatically. A branch-only run has different preceding cache pressure from an all-suite run. Always inspect actual cache reuse, input counts, output counts, ANE status, settings and concurrent request contamination before comparing results.
