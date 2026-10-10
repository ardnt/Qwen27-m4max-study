"""Matched MLX probe for local_probe/projection_probe.mm; synthetic weights."""
import argparse
import json
import statistics
import time
from pathlib import Path

import mlx.core as mx
import numpy as np


def codes(index, seed):
    h = index.astype(np.uint32, copy=True) + np.uint32(seed * 1009)
    h ^= h >> np.uint32(16)
    h *= np.uint32(0x7FEB352D)
    h ^= h >> np.uint32(15)
    h *= np.uint32(0x846CA68B)
    h ^= h >> np.uint32(16)
    return h & np.uint32(15)


def weights(n, k, seed):
    base = np.arange(n * k // 8, dtype=np.uint32) * np.uint32(8)
    packed = np.zeros_like(base)
    for offset in range(8):
        packed |= codes(base + np.uint32(offset), seed) << np.uint32(offset * 4)
    q = mx.array(packed.reshape(n, k // 8))
    scale = mx.full((n, k // 64), 1 / 128, mx.float16)
    bias = mx.full((n, k // 64), -8 / 128, mx.float16)
    mx.eval(q, scale, bias)
    return q, scale, bias


def run(rows, drift_path, compiled):
    parameters = [weights(17408, 5120, s) if s % 2 == 0
                  else weights(5120, 17408, s) for s in range(4)]
    values = ((np.arange(5120)[None, :] * 13
               + np.arange(rows)[:, None] * 11) % 97 - 48) / 64
    x = mx.array(values, dtype=mx.float16)
    mx.eval(x)

    def forward(value):
        outputs = []
        for q, scale, bias in parameters:
            value = mx.quantized_matmul(value, q, scale, bias,
                                       transpose=True, group_size=64, bits=4)
            outputs.append(value)
        return tuple(outputs)

    evaluate = mx.compile(forward) if compiled else forward
    times = []
    mx.reset_peak_memory()
    for sample in range(25):
        start = time.perf_counter()
        output = evaluate(x)
        mx.eval(output)
        mx.synchronize()
        elapsed = (time.perf_counter() - start) * 1000
        if sample >= 4:
            times.append(elapsed)
    first = np.asarray(output[0]).astype(np.float64)
    errors, refs = [], []
    for r in (0, rows - 1):
        for o in (0, 1, 17, 5119, 8191, 17407):
            q = codes(np.arange(5120, dtype=np.uint32) + np.uint32(o * 5120), 0)
            ref = np.dot(values[r], (q.astype(np.float64) - 8) / 128)
            errors.append(first[r, o] - ref)
            refs.append(ref)
    result = dict(runtime='MLX', version=mx.__version__, rows=rows, group_size=64,
                  chain_length=4, compiled=compiled,
                  sync_wall_ms=statistics.median(times), samples=21,
                  active_bytes=mx.get_active_memory(), peak_bytes=mx.get_peak_memory(),
                  sampled_cpu_max_abs_error=max(map(abs, errors)),
                  sampled_cpu_relative_l2_error=float(np.linalg.norm(errors)/np.linalg.norm(refs)))
    actual = np.asarray(output[-1]).astype(np.float32)
    actual.tofile(drift_path.parent / f'mlx-output-{rows}.bin')
    if drift_path.exists():
        drift = np.fromfile(drift_path, dtype=np.float32).reshape(rows, 5120)
        actual = np.asarray(output[-1]).astype(np.float32)
        result.update(drift_vs_mlx_max_abs_error=float(np.max(np.abs(drift-actual))),
                      drift_vs_mlx_relative_l2_error=float(np.linalg.norm(drift-actual)/np.linalg.norm(actual)),
                      drift_vs_mlx_all_finite=bool(np.isfinite(drift).all() and np.isfinite(actual).all()))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--rows', type=int, required=True)
    parser.add_argument('--drift-output', type=Path, required=True)
    parser.add_argument('--eager', action='store_true')
    args = parser.parse_args()
    print(json.dumps(run(args.rows, args.drift_output, not args.eager)), flush=True)
