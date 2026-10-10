"""Recompute the isolated ML Drift candidate medians; no GPU required."""
import json,math,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def main():
    rows=json.loads((ROOT/'candidate-results.json').read_text())
    saved=json.loads((ROOT/'candidate-summary.json').read_text())
    assert len(rows)==18
    for group in saved:
        rs=[r for r in rows if r['runtime_key']==group['runtime'] and r['rows']==group['rows']]
        assert len(rs)==3
        median=statistics.median(r['sync_wall_ms'] for r in rs)
        assert math.isclose(median,group['median_sync_wall_ms'],rel_tol=1e-12)
        assert all(r['final_vs_mlx_relative_l2_error'] <= .02 for r in rs)
    final=next(g for g in saved if g['rows']==512 and g['runtime']=='mixed_fused')
    baseline=next(g for g in saved if g['rows']==512 and g['runtime']=='splash')
    print('ML Drift saved synthetic 512-row projection comparison:',
          round(baseline['median_sync_wall_ms'],3),'->',round(final['median_sync_wall_ms'],3),'ms')
    print('Not full-model TTFT or decoding; FP16/BF16 and GPU-only comparison caveats remain.')

if __name__=='__main__':main()
