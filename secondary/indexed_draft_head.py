"""Read selected vocabulary rows directly from the original 4-bit head.

The SIMD arithmetic is TensorFold's existing fragment matmul; only the source
weight-row address is indexed. This avoids allocating a second vocabulary head.
No target projection or target sampling function uses this kernel.
"""
import hashlib
import mlx.core as mx
from tensorfold.kernels.qwen.dense.v1 import simd_qmm as q

_kernels = {}
_source = q._fragment_source(q._MMA)
_old = 'wrow[t] = min(nb + 8 * t + fm, N - 1);'
assert _source.count(_old) == 1, 'Indexed drafter must be reviewed after SIMD source changes'
_source = _source.replace(_old, 'wrow[t] = IDS[min(nb + 8 * t + fm, N - 1)];')


def project(x, head, ids):
    if int(head.bits) != 4 or int(head.group_size) != 64 or x.dtype != mx.bfloat16:
        raise ValueError('Indexed draft head requires BF16 inputs and affine 4-bit/64 weights')
    xf, xs = q.fragments(x)
    rows, dims, count = int(xs.shape[0]), int(xs.shape[1]) * 64, int(ids.size)
    plan = q._launch('mma', rows, count, dims, 64)
    consts, grid, group, shapes = plan
    key = consts
    if key not in _kernels:
        source = ''.join(f'  constexpr int {k} = {v};\n' for k,v in consts) + _source
        name = 'hermes_indexed_draft_' + hashlib.sha256((q._HEADER + source).encode()).hexdigest()[:16]
        _kernels[key] = mx.fast.metal_kernel(name=name,
            input_names=['XF','XS','W','SC','BI','ONE','IDS'], output_names=['OUT'],
            header=q._HEADER, source=source)
    result = _kernels[key](inputs=[xf,xs,head['weight'],head['scales'],head['biases'],q._one,ids],
                  grid=grid, threadgroup=group, output_shapes=shapes, output_dtypes=[mx.bfloat16])[0]
    return result.reshape(*x.shape[:-1], count)
