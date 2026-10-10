"""Replay one randomized block/arm on an already isolated, configured endpoint.

Does not launch, reconfigure, clear caches, or stop any service. The operator
must supply the protocol's mode, exact binary and fresh cache/learner state.
Use the protocol order across separate worker launches for all 21 runs.
"""
import argparse,gzip,json,os,sys,urllib.parse
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent))
from benchmark import MemoryMonitor,request

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study',choices=('original','final'),required=True)
    parser.add_argument('--block',type=int,choices=range(7),required=True)
    parser.add_argument('--arm',required=True)
    parser.add_argument('--base-url',required=True)
    parser.add_argument('--model',required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--metrics-url')
    parser.add_argument('--timeout',type=float,default=120)
    parser.add_argument('--token-env',default='BENCH_API_KEY')
    args=parser.parse_args()
    url=urllib.parse.urlsplit(args.base_url)
    if url.scheme not in ('http','https') or not url.hostname or url.username or url.password:
        parser.error('Use an http(s) base URL without embedded credentials')
    if args.timeout<=0:parser.error('timeout must be positive')
    protocol=json.loads((ROOT/args.study/'protocol.json').read_text())
    if args.arm not in protocol['arms']:parser.error('arm is absent from selected protocol')
    corpus=json.loads(gzip.decompress((ROOT/args.study/'corpus.json.gz').read_bytes()))
    cases={c['id']:c for c in corpus['cases']};block=protocol['blocks'][args.block]
    args.label=f'b{args.block:02}-{args.arm}';args.include_connection_setup=True
    warm={'id':'warmup','family':'warmup','category':'prime','max_tokens':8,
          'expected_input_tokens':15,'messages':[{'role':'user','content':'Reply ready.'}]}
    headers={}
    if token:=os.environ.get(args.token_env):headers['Authorization']='Bearer '+token
    monitor=MemoryMonitor(True)
    try:
        with args.output.open('x') as out:
            monitor.start()
            for case in [warm]+[cases[k] for k in block['case_ids']]:
                row=request(case,args,headers,monitor)
                row.update(arm=args.arm,block=args.block,warmup=case['id']=='warmup',
                           clock_scope='connect/POST through SSE DONE',
                           preparation_scope='serialization excluded')
                out.write(json.dumps(row,ensure_ascii=False)+'\n');out.flush()
                print(case['id'],row['client_ttft'],row['valid'],flush=True)
                if not row['valid'] or row['input_count_matches'] is not True:
                    raise RuntimeError('Invalid transport/token sample; replay stopped')
    finally:monitor.finish()

if __name__=='__main__':main()
