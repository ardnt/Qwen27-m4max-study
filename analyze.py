"""Recompute primary statistics from the exported individual measurements."""
import argparse
import collections
import csv
import json
import math
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def stats(values):
    values = sorted(float(v) for v in values if v is not None)
    if not values:
        return None
    return {'n': len(values), 'median': statistics.median(values),
            'mean': statistics.mean(values),
            'stddev': statistics.stdev(values) if len(values) > 1 else 0,
            'p90': values[math.ceil(.9 * len(values)) - 1],
            'p95': values[math.ceil(.95 * len(values)) - 1],
            'min': min(values), 'max': max(values)}

def ratio(row, numerator, denominator):
    c = row['runtime_counter_deltas']
    n, d = c.get(numerator), c.get(denominator)
    return n / (d / 1000) if n is not None and d is not None and d > 0 else None

def complete_counter_sum(rows, name):
    """An absent/reset counter is unavailable, never a measured zero."""
    values = [r['runtime_counter_deltas'].get(name) for r in rows]
    if any(not isinstance(v, (int, float)) or isinstance(v, bool)
           or not math.isfinite(v) or v < 0 for v in values):
        return None
    return sum(values)

def summarize(rows):
    groups = collections.defaultdict(list)
    for row in rows:
        if row['warmup'] or not row['valid']:
            continue
        groups[(row['phase'], row['family'], row['category'])].append(row)
    results = []
    for (phase, family, category), rs in sorted(groups.items()):
        item = {'phase': phase, 'family': family, 'category': category, 'n': len(rs),
                'inputs': sorted({r['prompt_tokens'] for r in rs}, key=lambda x: (x is None, x or 0)),
                'outputs': sorted({r['output_tokens'] for r in rs}, key=lambda x: (x is None, x or 0)),
                'reused': sorted({r['cached_tokens'] for r in rs}, key=lambda x: (x is None, x or 0))}
        metrics = {
            'ttft': [r['client_ttft'] for r in rs],
            'end_to_end': [r['client_e2e'] for r in rs],
            'backend_decode_tps': [r['backend_decode_tps'] for r in rs],
            'client_stream_tps': [r['client_decode_tps'] for r in rs],
            'effective_output_tps': [r['effective_output_tps'] for r in rs],
            'prompt_phase_tps': [r['effective_prefill_tps'] for r in rs],
            'prefill_command_wall_tps': [ratio(r, 'splash_prefill_input_tokens_total',
                                                  'splash_prefill_wall_milliseconds_total') for r in rs],
            'decode_cycle_wall_tps': [ratio(r, 'splash_decode_output_tokens_total',
                                               'splash_decode_cycle_milliseconds_total') for r in rs],
            'draft_context_rebuilt_rows': [r['runtime_counter_deltas'].get(
                'splash_draft_context_materialization_rows_total') for r in rs],
            'target_prefill_rows': [r['runtime_counter_deltas'].get(
                'splash_target_prefill_rows_total') for r in rs],
            'peak_family_gib': [r['peak_family_footprint_bytes'] / 2**30
                               if r.get('peak_family_footprint_bytes') is not None else None for r in rs]}
        item.update({name: stats(values) for name, values in metrics.items()})
        proposed = complete_counter_sum(rs, 'splash_drafted_tokens_total')
        accepted = complete_counter_sum(rs, 'splash_accepted_draft_tokens_total')
        iterations = complete_counter_sum(rs, 'splash_scheduler_decode_batches_total')
        acceptance = (accepted / proposed if proposed and accepted is not None
                      and accepted <= proposed else None)
        outputs = [r['output_tokens'] for r in rs]
        item.update(drafted=proposed, accepted=accepted, iterations=iterations,
                    acceptance=acceptance,
                    output_per_iteration=sum(outputs) / iterations
                    if iterations and all(v is not None for v in outputs) else None)
        results.append(item)
    return results

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=ROOT / 'data/qualification.jsonl')
    parser.add_argument('--output', type=Path, default=ROOT / 'data/recomputed-summary.json')
    parser.add_argument('--check', action='store_true', help='Require equality with the saved native analysis')
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.input.read_text().splitlines() if line.strip()]
    result = summarize(rows)
    if args.check:
        recorded = json.loads((ROOT / 'data/recorded-summary.json').read_text())
        if result != recorded:
            raise SystemExit('Recomputed statistics differ from the recorded summary')
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    csv_path = args.output.with_suffix('.csv')
    fields = ('case_id', 'phase', 'family', 'category', 'warmup', 'prompt_tokens',
              'output_tokens', 'cached_tokens', 'client_ttft', 'client_visible',
              'client_e2e', 'backend_decode_tps', 'peak_family_footprint_bytes', 'valid')
    with csv_path.open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)
    print('Verified', sum(r['n'] for r in result), 'measured samples in', len(result), 'cells')
    for r in result:
        rate = r['backend_decode_tps']['median'] if r['backend_decode_tps'] else None
        rate_text = f'{rate:.2f}' if rate is not None else 'unavailable'
        print(f"{r['phase']:14} {r['family']:14} {r['category']:9} n={r['n']} "
              f"TTFT={r['ttft']['median']:.6f}s decode={rate_text}tok/s")

if __name__ == '__main__':
    main()
