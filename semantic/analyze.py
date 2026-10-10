"""Recompute all focused results and qualification gates from individual rows."""
import argparse,ast,csv,gzip,hashlib,json,math,statistics,sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
from analyze import complete_counter_sum
from pathlib import Path

ROOT=Path(__file__).resolve().parent / "data"
def stats(values):
    v=sorted(x for x in values if x is not None)
    if not v:return None
    return {'n':len(v),'p50':statistics.median(v),'mean':statistics.mean(v),
            'p95_observed':v[math.ceil(.95*len(v))-1],
            'stdev':statistics.stdev(v) if len(v)>1 else None,'min':v[0],'max':v[-1]}
def delta(row,name):return row['runtime_counter_deltas'].get(name)
def validate_evidence(rows, cases):
    expected = {(mode, c['id']) for mode in ('off', 'on') for c in cases}
    actual = [(r['phase'], r['case_id']) for r in rows]
    if len(actual) != len(set(actual)) or set(actual) != expected:
        raise ValueError('Missing, duplicate, or unexpected measured cases')
    by_id = {c['id']: c for c in cases}
    for r in rows:
        c = by_id[r['case_id']]
        if r['output_sha256'] != hashlib.sha256(r['output'].encode()).hexdigest():
            raise ValueError('Output hash mismatch')
        if r['prompt_tokens'] != c['expected_input_tokens']:
            raise ValueError('Input token count mismatch')
        if 'expected' in c and r['output'].strip() != c['expected']:
            raise ValueError('Incorrect arithmetic answer')
        if c['family'] == 'code_regression':
            # Syntax validation only: does not establish behavioral correctness.
            code = r['output'].strip()
            if code.startswith('```'):
                code = '\n'.join(code.splitlines()[1:-1])
            ast.parse(code)
        if not r['valid'] or r['errors'] or r['safety_abort']:
            raise ValueError('Invalid measured sample')
        for name in ('client_ttft', 'client_e2e'):
            if not isinstance(r[name], (int,float)) or not math.isfinite(r[name]) or r[name] <= 0:
                raise ValueError('Missing or invalid client timing')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    all_rows=[json.loads(x) for x in (ROOT/'raw.jsonl').read_text().splitlines()]
    rows=[r for r in all_rows if not r['warmup'] and r['phase'] in ('off','on')]
    with gzip.open(ROOT/'corpus.json.gz', 'rt') as f: cases=json.load(f)['cases']
    validate_evidence(rows, cases)
    groups={};table=[]
    for mode in ('off','on'):
        families=sorted(set((r['family'],r['category']) for r in rows if r['phase']==mode))
        for family,stage in families:
            selected=[r for r in rows if (r['phase'],r['family'],r['category'])==(mode,family,stage)]
            key=f'{mode}/{family}/{stage}'
            data={'n':len(selected),'context':stats([r['prompt_tokens'] for r in selected]),
                  'ttft_seconds':stats([r['client_ttft'] for r in selected]),
                  'e2e_seconds':stats([r['client_e2e'] for r in selected]),
                  'cached_tokens':stats([r['cached_tokens'] for r in selected]),
                  'target_rows':stats([delta(r,'splash_target_prefill_rows_total') for r in selected]),
                  'draft_context_rows':stats([(delta(r,'splash_draft_context_materialization_rows_total') or 0)+
                                              (delta(r,'splash_draft_context_prompt_end_rows_total') or 0) for r in selected]),
                  'prefill_wall_ms':stats([delta(r,'splash_prefill_wall_milliseconds_total') for r in selected]),
                  'peak_family_gib':max(r['peak_family_footprint_bytes'] for r in selected)/2**30}
            if family=='code_regression':
                # Client chunk-delivery timing is not used for short answers.
                data['decode_backend_tps']=stats([r['backend_decode_tps'] for r in selected])
                data['draft_proposed']=complete_counter_sum(selected,'splash_drafted_tokens_total')
                data['draft_accepted']=complete_counter_sum(selected,'splash_accepted_draft_tokens_total')
                data['acceptance']=data['draft_accepted']/data['draft_proposed'] if data['draft_proposed'] and data['draft_accepted'] is not None and data['draft_accepted'] <= data['draft_proposed'] else None
            groups[key]=data
            table.append({'mode':mode,'family':family,'stage':stage,'n':data['n'],
                          'actual_context_p50':data['context']['p50'],'output_tokens_p50':statistics.median(r['output_tokens'] for r in selected),
                          'ttft_p50_s':data['ttft_seconds']['p50'],'ttft_p95_observed_s':data['ttft_seconds']['p95_observed'],
                          'cached_tokens_p50':data['cached_tokens']['p50'],'target_rows_p50':data['target_rows']['p50'],
                          'draft_context_rows_p50':data['draft_context_rows']['p50'],'peak_family_gib':data['peak_family_gib']})
    paired=[];index={(r['phase'],r['case_id']):r for r in rows}
    for r in [r for r in rows if r['phase']=='off']:
        improved=index.get(('on',r['case_id']))
        if not improved:continue
        paired.append({'case_id':r['case_id'],'output_sha256_equal':r['output_sha256']==improved['output_sha256'],
                       'old_ttft_s':r['client_ttft'],'new_ttft_s':improved['client_ttft'],
                       'ttft_saved_s':r['client_ttft']-improved['client_ttft'],
                       'ratio':r['client_ttft']/improved['client_ttft']})
    bundles={}
    for family in ('latest_1k','earlier_turn'):
        bundle_rows=[]
        for repeat in range(7):
            totals={mode:sum(r['client_e2e'] for r in rows if r['phase']==mode and r['family']==family and r['repeat']==repeat) for mode in ('off','on')}
            bundle_rows.append({'repeat':repeat,**totals,'saved':totals['off']-totals['on']})
        bundles[family]={'individual':bundle_rows,'off_e2e':stats([r['off'] for r in bundle_rows]),
                         'on_e2e':stats([r['on'] for r in bundle_rows]),'saved_seconds':stats([r['saved'] for r in bundle_rows])}
    traces=[json.loads(x) for x in (ROOT/'decision-traces.jsonl').read_text().splitlines()]
    planner=[r['health_after']['cache']['semantic_planner'] for r in traces if r['phase']=='on']
    swap_values=[m['swap_bytes'] for r in rows for m in r['memory_samples'] if m['swap_bytes'] is not None]
    pressure=[m['pressure'] for r in rows for m in r['memory_samples']]
    gates={'48_measured_samples_per_arm':all(sum(r['phase']==p for r in rows)==48 for p in ('off','on')),
           'all_samples_valid':all(r['valid'] and not r['safety_abort'] for r in rows),
           'all_actual_input_counts_match':all(r['input_count_matches'] for r in rows),
           'all_arithmetic_correct':all(r.get('match_outer_whitespace',True) for r in rows),
           'all_paired_outputs_identical':len(paired)==48 and all(r['output_sha256_equal'] for r in paired),
           'all_code_syntax_valid':all(r.get('python_syntax_valid') for r in rows if r['family']=='code_regression'),
           'both_complete_branch_bundles_improved':all(b['saved_seconds']['p50']>0 for b in bundles.values()),
           'normal_memory_pressure':set(pressure)=={1},'zero_swap':max(swap_values)==0,
           'cost_observations_available':bool(planner) and planner[-1]['cost_samples']>30,
           'no_invalid_native_plans':bool(planner) and planner[-1]['invalid']==0}
    result={'groups':groups,'paired_outputs':paired,'bundles':bundles,'gates':gates,
            'safe_to_install_under_tested_conditions':all(gates.values()),
            'memory':{'peak_family_gib':max(r['peak_family_footprint_bytes'] for r in rows)/2**30,
                      'swap_min_bytes':min(swap_values),'swap_max_bytes':max(swap_values),'pressure_levels':sorted(set(pressure))},
            'planner_last':planner[-1] if planner else None,
            'planner_maximum_us':max(p['maximum_plan_us'] for p in planner) if planner else None,
            'sample_classification':'Client TTFT/E2E and native counters verified; cost coefficients/predicted savings are estimates; n=1/3 pilots exploratory.'}
    args.output_dir.mkdir(parents=True,exist_ok=True)
    if args.check and result != json.loads((ROOT/'recorded-summary.json').read_text()):
        raise SystemExit('Statistics differ from historical recorded summary')
    (args.output_dir/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    with (args.output_dir/'results.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(table[0]));writer.writeheader();writer.writerows(table)
    (args.output_dir/'output-pairs.json').write_text(json.dumps(paired,indent=2)+'\n')
    print(json.dumps({'gates':gates,'memory':result['memory'],'bundles':{k:v['saved_seconds'] for k,v in bundles.items()},'planner_max_us':result['planner_maximum_us']},indent=2))

if __name__=='__main__':main()
