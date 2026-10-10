"""Recompute statistics offline. No inference, service changes, or publication."""
import argparse,collections,csv,hashlib,json,math,random,statistics
from pathlib import Path
P=Path(__file__).resolve().parent
ARMS=('heuristic','simple','planner')
def stats(x):
 x=sorted(float(v) for v in x if v is not None)
 if not x:return None
 n=len(x)
 return dict(n=n,mean=statistics.mean(x),p50=statistics.median(x),p90_nearest_rank=x[math.ceil(.9*n)-1],p95_nearest_rank=x[math.ceil(.95*n)-1],min=x[0],max=x[-1],sample_stdev=statistics.stdev(x) if n>1 else None)
def paired(base,test):
 changes=[100*(base[b]-test[b])/base[b] for b in sorted(set(base)&set(test))]
 differences=[base[b]-test[b] for b in sorted(set(base)&set(test))]
 rng=random.Random(202610101234);boot=[]
 for _ in range(20000):boot.append(statistics.median(rng.choices(changes,k=len(changes))))
 boot.sort();pos=sum(v>0 for v in changes);neg=sum(v<0 for v in changes);n=pos+neg
 p=min(1,2*sum(math.comb(n,k) for k in range(min(pos,neg)+1))/2**n) if n else 1
 return dict(paired_reductions_percent=changes,reductions=stats(changes),saved_seconds=stats(differences),bootstrap_median_95pct=[boot[499],boot[19499]],wins=pos,ties=len(changes)-n,exact_two_sided_sign_p=p)
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--output-dir',type=Path,required=True);args=parser.parse_args();out=args.output_dir;out.mkdir(parents=True,exist_ok=True)
 allrows=[json.loads(s) for s in (P/'raw.jsonl').read_text().splitlines()];rows=[r for r in allrows if not r['warmup']]
 protocol=json.loads((P/'protocol.json').read_text())
 complete=(P/'qualification-complete').exists()
 if not complete:raise SystemExit('Experiment incomplete: analysis withheld to avoid optional stopping.')
 assert len(rows)==315 and len(allrows)==336
 assert len({(r['arm'],r['case_id']) for r in rows})==315
 csvrows=[]
 for r in rows:
  d=r['runtime_counter_deltas'];code=r['family']=='code'
  decode_ms=d.get('splash_decode_wall_milliseconds_total',0)
  native_decode=d.get('splash_decode_output_tokens_total',0)/decode_ms*1000 if code and decode_ms>0 else None
  draft=d.get('splash_drafted_tokens_total',0);accept=d.get('splash_accepted_draft_tokens_total',0)
  samples=r['memory_samples']
  cr={k:r[k] for k in ['id','case_id','arm','block','family','category','prompt_tokens','output_tokens','cached_tokens','client_ttft','client_visible','client_e2e','peak_family_footprint_bytes','valid','input_count_matches','output_sha256','finish_reason']}
  cr.update(native_decode_tps=native_decode,client_code_decode_tps=r['client_decode_tps'] if code else None,target_rows=d.get('splash_target_prefill_rows_total'),draft_prefill_rows=d.get('splash_draft_context_prompt_end_rows_total'),draft_materialization_rows=d.get('splash_draft_context_materialization_rows_total'),draft_avoided_rows=d.get('splash_draft_context_avoided_rows_total'),draft_proposed=draft,draft_accepted=accept,acceptance=accept/draft if draft else None,native_decode_ms=decode_ms,native_prefill_ms=d.get('splash_prefill_wall_milliseconds_total'),native_peak_bytes=r['runtime_counters_after'].get('splash_memory_peak_bytes'),swap_max=max(s['swap_bytes'] for s in samples),pressure_max=max(s['pressure'] for s in samples),arithmetic_correct=r.get('match_outer_whitespace') if not code else None,python_syntax_valid=r.get('python_syntax_valid') if code else None,errors=json.dumps(r['errors']),safety_abort=json.dumps(r['safety_abort']))
  csvrows.append(cr)
 with (out/'results.csv').open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(csvrows[0]));w.writeheader();w.writerows(csvrows)
 grouped=collections.defaultdict(list)
 for r in csvrows:grouped[(r['arm'],r['family'],r['category'])].append(r)
 stages=[]
 for (arm,family,category),rs in sorted(grouped.items()):
  stages.append(dict(arm=arm,family=family,category=category,n=len(rs),**{m:stats(r[m] for r in rs) for m in ['client_ttft','client_e2e','native_decode_tps','client_code_decode_tps','target_rows','draft_prefill_rows','draft_materialization_rows','cached_tokens','acceptance','native_prefill_ms','peak_family_footprint_bytes']}))
 totals={a:{b:sum(r['client_e2e'] for r in rows if r['arm']==a and r['block']==b) for b in range(7)} for a in ARMS}
 comparisons={f'{a}_vs_{b}':paired(totals[b],totals[a]) for a,b in [('planner','simple'),('planner','heuristic'),('simple','heuristic')]}
 family_comparisons={}
 for fam in sorted(set(r['family'] for r in rows)):
  ft={a:{b:sum(r['client_e2e'] for r in rows if r['arm']==a and r['block']==b and r['family']==fam) for b in range(7)} for a in ARMS}
  family_comparisons[fam]=dict(totals=ft,planner_vs_heuristic=paired(ft['heuristic'],ft['planner']),planner_vs_simple=paired(ft['simple'],ft['planner']),simple_vs_heuristic=paired(ft['heuristic'],ft['simple']))
 triples=collections.defaultdict(list)
 for r in rows:triples[r['case_id']].append(r)
 mismatches=[{'case_id':k,'outputs':{r['arm']:r['output'] for r in rs},'tokens':{r['arm']:r['output_tokens'] for r in rs}} for k,rs in triples.items() if len({(r['output_sha256'],r['reasoning'],r['output_tokens']) for r in rs})!=1]
 armstats={}
 for a in ARMS:
  rs=[r for r in csvrows if r['arm']==a]
  armstats[a]=dict(block_total=stats(totals[a].values()),summed_e2e=sum(r['client_e2e'] for r in rs),peak_family_gib=max(r['peak_family_footprint_bytes'] for r in rs)/2**30,peak_native_gib=max(r['native_peak_bytes'] for r in rs)/2**30,target_rows=sum(r['target_rows'] for r in rs),draft_prefill_rows=sum(r['draft_prefill_rows'] for r in rs),draft_materialization_rows=sum(r['draft_materialization_rows'] for r in rs),draft_avoided_rows=sum(r['draft_avoided_rows'] for r in rs),max_swap_bytes=max(r['swap_max'] for r in rs),code_native_tps=stats(r['native_decode_tps'] for r in rs),code_client_tps=stats(r['client_code_decode_tps'] for r in rs),code_acceptance=stats(r['acceptance'] for r in rs if r['family']=='code'))
 decisions=[json.loads(s) for s in (P/'decisions.jsonl').read_text().splitlines()]
 prs=[d['health']['cache']['semantic_planner'] for d in decisions if d['arm']=='planner']
 planner=dict(chooser_us=stats(d['last_plan_us'] for d in prs),max_reported_chooser_us=max(d['maximum_plan_us'] for d in prs),last_reasons=dict(collections.Counter(d['last_decision']['reason'] for d in prs)),selected_count=stats(len(d['last_decision']['selected']) for d in prs),max_invalid=max(d['invalid'] for d in prs))
 comp=comparisons['planner_vs_simple'];correct=all(r['arithmetic_correct'] for r in csvrows if r['family']!='code');safe=all(not r['safety_abort'] and not r['errors'] for r in rows)
 criteria=dict(cold_regression_at_most_3pct=family_comparisons['unrelated']['planner_vs_heuristic']['reductions']['p50']>=-3,median_reduction_at_least_10pct=comp['reductions']['p50']>=10,at_least_six_wins=comp['wins']>=6,all_arithmetic_correct=correct,all_paired_outputs_identical=not mismatches,no_safety_abort=safe,peak_no_more_than_30gib=max(a['peak_family_gib'] for a in armstats.values())<=30)
 summary=dict(complete=complete,measured=len(rows),warmups=len(allrows)-len(rows),independent_blocks=7,block_totals=totals,comparisons=comparisons,family_comparisons=family_comparisons,arm_statistics=armstats,stages=stages,planner=planner,output_mismatches=mismatches,all_code_syntax_valid=all(r['python_syntax_valid'] for r in csvrows if r['family']=='code'),criteria=criteria,decision_rule_passed=all(criteria.values()),limitations=['Single machine; synthetic held-out microbenchmarks, not sampled production traffic.','Heuristic, conservative simple and conservative planner share the final binary; no released-stock comparison.','Only seven independent blocks; p95 at n7 is the sample maximum.','Tiny outputs arrive within one speculative batch: raw client decode TPS is invalid for them and omitted from CSV.','Code native output counter includes runtime-specific boundaries; do not compare to other runtimes without aligning definitions.','Identical hard memory budgets, not identical occupied RAM.','Chooser timing excludes LCP observation; request E2E includes it.','No global eviction opportunity-cost objective or memory-budget sweep.','The comparison identifies the combined planner effect, not the value of each planner feature.'])
 (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
 print(json.dumps({'measured':summary['measured'],'criteria':summary['criteria'],'decision_rule_passed':summary['decision_rule_passed']}))
if __name__=='__main__':main()
