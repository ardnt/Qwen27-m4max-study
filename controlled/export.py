"""Export completed synthetic trials using explicit field allowlists.

Local use only; never connects to an endpoint or publishes. Review the output
before distribution. Source service/session files are intentionally excluded.
"""
import argparse, hashlib, json, shutil
from pathlib import Path

FIELDS = '''id block family category repeat max_tokens thinking expected_input_tokens
arm case_id model phase warmup utc http_status usage output reasoning finish_reason
errors safety_abort client_ttft client_visible client_e2e client_decode_tps
backend_decode_tps backend_ttft backend_prefill runtime_counters_before
runtime_counters_after runtime_counter_deltas effective_prefill_tps
effective_output_tps prompt_tokens output_tokens cached_tokens json_serialization_ns
peak_family_footprint_bytes settings output_sha256 input_count_matches exact_match
match_outer_whitespace content_similarity valid python_syntax_valid'''.split()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path); parser.add_argument('destination',type=Path)
    args=parser.parse_args(); src=args.source; dst=args.destination
    assert (src/'qualification-complete').exists(), 'Incomplete experiment'
    assert (src/'verification.json').exists(), 'Verify locally before export'
    assert json.loads((src/'verification.json').read_text())['passed']
    dst.mkdir(parents=True,exist_ok=True)
    original=(src/'protocol.json').read_bytes(); proto=json.loads(original)
    proto['binary']='LOCAL_BINARY/splash'
    proto['export_note']='Originally collected privately; authorized for publication after final validation.'
    (dst/'protocol.json').write_text(json.dumps(proto,indent=2)+'\n')
    source_hashes={}
    for name in ('corpus.json.gz','summary.json','results.csv','verification.json'):
        shutil.copy2(src/name,dst/name)
        source_hashes[name]=hashlib.sha256((src/name).read_bytes()).hexdigest()
    rows=[]
    for line in (src/'raw.jsonl').read_text().splitlines():
        r=json.loads(line); out={k:r[k] for k in FIELDS if k in r}
        out['memory_samples']=[{k:s[k] for k in ('ns','pressure','swap_bytes','family_footprint_bytes','load')} for s in r['memory_samples']]
        rows.append(out)
    (dst/'raw.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
    decisions=[]
    for line in (src/'decisions.jsonl').read_text().splitlines():
        d=json.loads(line);h=d['health']
        decisions.append({k:d[k] for k in ('id','arm','block','case_id')} | {'health':{
            'status':h['status'],'warming':h['warming'],'memory':h['memory'],
            'ane_ffn':{k:h['ane_ffn'][k] for k in ('state','share','minimum_rows','reruns')},
            'transport':{'restarts':h['transport']['restarts']},
            'cache':{'semantic_planner':h['cache']['semantic_planner']}}})
    (dst/'decisions.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in decisions))
    starts=[json.loads(x) for x in (src/'worker-starts.jsonl').read_text().splitlines()]
    controls=[{'variant':x['variant'],'env':{k:('LOCAL_RESOURCE/'+Path(v).name if v.startswith('/') else v) for k,v in x['env'].items()},
               'command_sha256':hashlib.sha256(json.dumps(x['command']).encode()).hexdigest()} for x in starts]
    (dst/'worker-controls.json').write_text(json.dumps(controls,indent=2)+'\n')
    monitoring=[]
    for line in (src/'system-load.jsonl').read_text().splitlines():
        r=json.loads(line)
        percentages=[]
        for record in r.get('cpu_load',{}).get('stdout','').splitlines():
            fields=record.split()
            try:percentages.append({'cpu_percent':float(fields[1]),'memory_percent':float(fields[2])})
            except (ValueError,IndexError):pass
        monitoring.append({'utc':r['utc'],'system':{k:r['system'][k] for k in ('pressure','swap_bytes','family_footprint_bytes','load')},
            'thermal':{k:r['thermal'][k] for k in ('exit_code','stdout')},
            'power_command_exit_code':r['power']['exit_code'],
            'ac_power_reported':"Now drawing from 'AC Power'" in r['power']['stdout'],
            'top_process_percentages_unidentified':percentages})
    (dst/'system-monitor.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in monitoring))
    for name in ('raw.jsonl','decisions.jsonl','worker-starts.jsonl'):
        source_hashes[name]=hashlib.sha256((src/name).read_bytes()).hexdigest()
    (dst/'export-provenance.json').write_text(json.dumps({
        'source_protocol_sha256':hashlib.sha256(original).hexdigest(),
        'source_artifact_hashes':source_hashes,
        'redactions':['host paths','process identifiers','production health/configuration','disk-free capacity'],
        'preserved':['all individual timings','synthetic input corpus and outputs','native counters','family memory samples','decision receipts','randomized order'],
        'request_body_checks':'Original local verification checks each recorded serialized request against the corpus and across arms; network traces are not redistributed.'},indent=2)+'\n')
    (dst/'qualification-complete').touch()
    script=(src/'analyze.py').read_text()
    script=script.replace('import collections,csv,hashlib,json,math,random,statistics','import argparse,collections,csv,hashlib,json,math,random,statistics')
    script=script.replace('def main():\n',"def main():\n parser=argparse.ArgumentParser();parser.add_argument('--output-dir',type=Path,required=True);args=parser.parse_args();out=args.output_dir;out.mkdir(parents=True,exist_ok=True)\n",1)
    script=script.replace("(P/'results.csv').open", "(out/'results.csv').open").replace("(P/'summary.json').write_text","(out/'summary.json').write_text")
    script=script.replace(" print(json.dumps({k:summary[k] for k in ['measured','criteria','decision_rule_passed','comparisons','arm_statistics']},indent=2))", " print(json.dumps({'measured':summary['measured'],'criteria':summary['criteria'],'decision_rule_passed':summary['decision_rule_passed']}))")
    (dst/'analyze.py').write_text(script)
    print(f'Exported {len(rows)} rows to {dst}; review before publishing.')

if __name__=='__main__':main()
