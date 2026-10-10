# ML Drift on the M4 Max: measured result

A useful prefill optimization was found and implemented in an isolated ML Drift build. It reduces the elapsed time of a 512-row Qwen-size projection workload by **9.2% compared with Splash’s released GPU kernels**, while matching the FP16 MLX reference output. Hermes continues to use Splash 1.3.0. No full-model Qwen speed gain has been established or deployed.

This Mac has an M4 Max with 32 GPU cores and 36 GiB unified memory. The tested ML Drift source is pinned to `29e3d2b41a7128d7d5dd9cd1ba09f226cca14d22`. Comparison versions are MLX 0.32.2 and Splash 1.3.0 with its released `splash.metallib` and released Linear policy. Earlier local Splash experiments were excluded from the comparison.

The workload contains four dependent matrix projections alternating 5120→17408 and 17408→5120, matching the dense 27B model’s feed-forward matrix dimensions. All implementations use identical deterministic synthetic 4-bit weights, group size 64, and exactly representable scales. Drift and MLX use FP16 activations; Splash uses its native BF16 activations. This measures projection operations, not an entire language model, prompt-to-first-token latency, reasoning quality, attention, speculative acceptance, or Telegram delivery. The Splash comparison uses GPU kernels, without its live ANE split.

Times are medians of three separate process runs, each with four warmups and 21 timed iterations. Runs are sequential and their order is rotated. Each iteration executes all four projections and waits for GPU completion. Model construction, packing, compilation and input uploads are excluded. MLX wall time includes its Python evaluation interface; Drift and Splash use C++ interfaces.

| Projection batch | MLX | Drift with FP32 accumulation, before optimization | Optimized Drift | Released Splash GPU |
|---|---:|---:|---:|---:|
| 1 row | 0.829 ms | 0.760 ms | No changed path | Not compared: Splash decode uses eight-row verification geometry |
| 8 rows, decode-sized | 1.681 ms | 1.145 ms | 1.145 ms | **0.938 ms** |
| 64 rows, prefill-sized | **4.769 ms** | 10.345 ms | 5.871 ms | 6.357 ms |
| 512 rows, prefill-sized | 34.217 ms | 46.481 ms | **31.657 ms** | 34.847 ms |

The initial pilot timings were discarded once repeated tests established stable results. Input buffers are retained explicitly: Drift’s memory planner can otherwise reuse an input after its final read, which makes repeated evaluation of an unchanged input invalid. The final harness checks finite outputs and sampled independent CPU reference results.

The transferable improvement is in the kernel decision tree. Drift’s Metal capability list omitted the FP16-input/FP32-accumulator SIMD matrix combination. Selecting FP32 accumulation therefore sent this workload to a slower generic convolution path. Registering and selecting that combination worked on this M4 Max and retained the reference output. At 512 rows, the default heuristic also inserted separate weight-conversion passes. For the two measured feed-forward shapes, using the fused quantized matrix path instead reduced time further and avoided expanded weight intermediates.

For the 512-row workload, enabling the mixed matrix path reduced time to 33.762 ms. Selecting its fused quantized variant reduced it to 31.657 ms. Drift’s intermediate allocation fell from **224.4 MB to 46.1 MB**, and total Metal allocation fell from 419.5 MB to 241.3 MB. These are operation-graph allocations, not projected savings for the entire 27B model. The final policy override is limited to the M4 Max, FP32 accumulation, 512 rows and the two tested matrix shapes. Other shapes retain the original heuristic.

All outputs of the optimized 64-row and 512-row chains matched the MLX FP16 reference byte for byte. Sampled first-projection relative L2 error against an independent CPU reference was about 0.027%. Metal API/GPU validation also passed for 8, 64 and 512 rows. The default FP16-accumulation path was tested separately: it took 6.234 ms and 33.299 ms at 64 and 512 rows, but final-chain relative error against MLX was approximately 3.84% and 3.74%. That lower-accuracy path was rejected for this experiment. These synthetic checks cannot establish full-model intelligence or quality equivalence.

An additional upstream INT4 loader defect was found. Its unpacked-INT8-to-packed-INT4 overload allocated one quarter of the logical element count rather than one half. It crashed while transposing the weights. The isolated copy now allocates the required space; the INT2 overload retains its original quarter-size allocation. A batched reduction also exceeded this Mac’s shared-memory limit with FP32 accumulation. A scoped reduction-array reuse fix passes Metal validation.

The practical integration route is to reuse the mixed-precision fused prefill kernel inside the existing Qwen runtime, preserving Splash’s faster decode and the current API/Telegram stack. A full runtime switch is not justified by these results. Drift’s supplied Qwen sample implements older Qwen3 standard attention. The installed 27B model has **48 linear-attention layers and 16 full-attention layers**, plus speculative decoding, affine group-64 weights and vision support. Porting only the projection path would still require adapting the weight layout and affine biases, BF16 inputs/outputs, and command scheduling; then verifying real-model Arabic, tool calls, speculative acceptance, long context and end-to-end latency. Conversion and scheduling overhead could consume the measured kernel gain. The 64-row test also shows that MLX remains faster at that batch size, so any new selector should use measurements per phase and shape.

The official native Metal profiler was built and ran successfully using one synthetic layer of Qwen3 0.6B. Its throughput is deliberately excluded from the comparison above because it is not real 27B generation. Google’s desktop table itself shows near-parity with MLX on its M3 Ultra examples rather than a universal Mac speed improvement. The Intel-specific INT4 activation path and Apple-family-10 MPP path do not apply to this M4 Max.


## Public package scope

This export includes the five reviewable patches, deterministic C++/MLX probes,
individual synthetic timings, and Metal-validation receipts. It excludes compiled
binaries, personal configuration and machine-specific orchestration scripts.
The proposal is a prototype; it is not a deployed Qwen runtime optimization.

Pinned source: https://github.com/google-ai-edge/ml-drift/tree/29e3d2b41a7128d7d5dd9cd1ba09f226cca14d22

Run `python3 secondary/drift/analyze.py` from the study root to recompute medians
without using the GPU. For a new isolated build, apply build compatibility, INT4
allocation, mixed precision, shared-memory, then the scoped fused-prefill patch
to the pinned ML Drift checkout. Copy `local_probe/` to that checkout and build
its `//local_probe:projection_probe` Bazel target using upstream's macOS build
requirements. Run the resulting probe with rows and output-path arguments; the
probe itself performs four warmups and 21 timed iterations. Compare separate
process runs, rotating order, against the included MLX probe and the unchanged
Splash probe. Splash also requires its source headers, host implementation and
matching compiled Metal library, which are not redistributed. This review checks
saved results and source application, not a fresh GPU build.
