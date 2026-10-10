"""Verify historical counts, TTFT, decode, E2E and output hashes; no inference."""
import collections,gzip,hashlib,json,math,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def main():
    with gzip.open(ROOT/'measurements.jsonl.gz','rt') as f: rows=[json.loads(l) for l in f]
    recorded=json.loads((ROOT/'recorded-summary.json').read_text())
    excluded=set(recorded['fixture_excluded_case_ids'])
    unique={(r['model'],r['phase'],r['case_id']):r for r in rows
            if r['valid'] and not r['warmup'] and r['case_id'] not in excluded}
    assert len(rows)==563 and len(unique)==535
    assert len({r['id'] for r in rows})==len(rows)
    for r in rows:
        assert hashlib.sha256(r['output'].encode()).hexdigest()==r['output_sha256']
        assert 0 < r['client_ttft'] <= r['client_e2e']
        assert r['prompt_tokens']+r['output_tokens']<=65536
    groups=collections.defaultdict(list)
    for r in unique.values():groups[tuple(r[k] for k in ('model','phase','family','level','category'))].append(r)
    for g in recorded['groups']:
        rs=groups[tuple(g[k] for k in ('model','phase','family','level','category'))]
        assert len(rs)==g['n']
        for metric in ('client_ttft','client_e2e','backend_decode_tps'):
            values=sorted(r[metric] for r in rs if r.get(metric) is not None)
            if not values: assert g[metric] is None; continue
            stats={'median':statistics.median(values),'mean':statistics.mean(values),
                   'p95':values[math.ceil(.95*len(values))-1]}
            for name,value in stats.items():assert math.isclose(value,g[metric][name],rel_tol=1e-12,abs_tol=1e-12),(metric,name)
    assert len(recorded['primary_raw_coverage'])==25
    assert all(c['n']==7 for c in recorded['primary_raw_coverage'])
    follows=[r for r in unique.values() if r['model']==recorded['winner'] and r['family']=='follow' and r['level']==8192]
    assert len(follows)==20
    audits=json.loads((ROOT/'input-audit.json').read_text())['requests']
    assert len(audits)==len(rows) and all(a['matches'] for a in audits)
    print('Historical baseline: 563 raw / 535 measured, 68 groups, 25 raw cells, 20 primary follow-ups verified.')
    print('Saved token recount receipts are checked; fresh tokenization requires the original tokenizer.')

if __name__=='__main__':main()
