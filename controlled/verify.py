"""Independently check released controlled evidence; no models or services."""
import ast,csv,gzip,hashlib,json,math,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def equivalent(a,b):
    if isinstance(a,dict): return isinstance(b,dict) and a.keys()==b.keys() and all(equivalent(a[k],b[k]) for k in a)
    if isinstance(a,list): return isinstance(b,list) and len(a)==len(b) and all(equivalent(x,y) for x,y in zip(a,b))
    if isinstance(a,float) and isinstance(b,(int,float)): return math.isclose(a,b,rel_tol=1e-10,abs_tol=1e-10)
    return a==b

def validate(path):
    protocol=json.loads((path/'protocol.json').read_text())
    corpus=gzip.decompress((path/'corpus.json.gz').read_bytes())
    assert hashlib.sha256(corpus).hexdigest()==protocol['corpus_sha256']
    cases={c['id']:c for c in json.loads(corpus)['cases']}
    allrows=[json.loads(x) for x in (path/'raw.jsonl').read_text().splitlines()]
    rows=[r for r in allrows if not r['warmup']]
    assert len(rows)==protocol['count']['total_measured']==315
    assert len(allrows)-len(rows)==protocol['count']['warmups']==21
    warmups=[r for r in allrows if r['warmup']]
    for r in warmups:
        assert r['valid'] and not r['errors'] and not r['safety_abort']
        assert r['prompt_tokens']==15 and 0<r['output_tokens']<=8
    assert len({r['phase'] for r in warmups})==21
    expected=[(a,c) for b in protocol['blocks'] for a in b['arm_order'] for c in b['case_ids']]
    assert [(r['arm'],r['case_id']) for r in rows]==expected
    assert len(set(expected))==len(expected)
    for r in rows:
        c=cases[r['case_id']]
        assert r['http_status']==200 and r['valid'] and not r['errors'] and not r['safety_abort']
        assert r['finish_reason']=='stop'
        assert hashlib.sha256(r['output'].encode()).hexdigest()==r['output_sha256']
        assert r['prompt_tokens']==c['expected_input_tokens']==r['usage']['prompt_tokens']
        assert 0<r['output_tokens']<=c['max_tokens'] and r['output_tokens']==r['usage']['completion_tokens']
        assert r['reasoning']==''
        if 'expected' in c: assert r['output'].strip()==c['expected']
        if c['family']=='code': ast.parse(r['output'])
        for k in ('client_ttft','client_e2e'):
            assert math.isfinite(r[k]) and r[k]>0
        assert r['client_ttft']==r['client_visible']<=r['client_e2e']
        delta=r['runtime_counter_deltas'];assert delta['splash_requests_submitted_total']==delta['splash_requests_completed_total']==1
        assert all(v>=0 and math.isfinite(v) for v in delta.values())
        assert all(x['pressure']==1 and x['swap_bytes']==0 for x in r['memory_samples'])
    controls=json.loads((path/'worker-controls.json').read_text())
    assert len(controls)==21 and len({x['command_sha256'] for x in controls})==1
    common=None
    for x in controls:
        arm=x['variant'].split('-',1)[1];spec=protocol['arms'][arm]
        assert all(x['env'][k]==v for k,v in spec.items())
        env={k:v for k,v in x['env'].items() if k not in spec}
        if common is None:common=env
        assert common==env
    decisions=[json.loads(x) for x in (path/'decisions.jsonl').read_text().splitlines()]
    assert [(x['arm'],x['case_id']) for x in decisions]==expected
    for d in decisions:
        h=d['health'];assert h['memory']['budget']==25*2**30 and h['status']=='ok'
        assert h['ane_ffn']['state']=='split' and abs(h['ane_ffn']['share']-.6176470588)<1e-7
        assert h['ane_ffn']['reruns']==h['transport']['restarts']==0
    with tempfile.TemporaryDirectory() as temp:
        subprocess.run([sys.executable,str(path/'analyze.py'),'--output-dir',temp],check=True)
        computed=json.loads((Path(temp)/'summary.json').read_text())
        saved=json.loads((path/'summary.json').read_text())
        assert equivalent(computed,saved), 'Recomputed summary differs'
        fresh=list(csv.DictReader((Path(temp)/'results.csv').open()))
        stored=list(csv.DictReader((path/'results.csv').open()))
        assert len(fresh)==len(stored)
        for x,y in zip(fresh,stored):
            assert x.keys()==y.keys()
            for k in x:
                if x[k]!=y[k]: assert math.isclose(float(x[k]),float(y[k]),rel_tol=1e-10,abs_tol=1e-10)
    print(path.name+': 315 measured rows, paired order, counts, outputs, counters and statistics verified.')

if __name__=='__main__':
    for name in ('original','final'): validate(ROOT/name)
