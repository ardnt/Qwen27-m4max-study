import copy
import gzip
import importlib.util
import io
import json
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import analyze
import benchmark

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("semantic_analysis", ROOT / "semantic/analyze.py")
semantic = importlib.util.module_from_spec(spec)
spec.loader.exec_module(semantic)

class EvidenceTests(unittest.TestCase):
    def test_partial_or_reset_counters_are_unavailable(self):
        rows = [{'runtime_counter_deltas': {'x': 10}}, {'runtime_counter_deltas': {}}]
        self.assertIsNone(analyze.complete_counter_sum(rows, 'x'))
        rows[1]['runtime_counter_deltas']['x'] = -1
        self.assertIsNone(analyze.complete_counter_sum(rows, 'x'))
        rows[1]['runtime_counter_deltas']['x'] = float('nan')
        self.assertIsNone(analyze.complete_counter_sum(rows, 'x'))
        rows[1]['runtime_counter_deltas']['x'] = 0
        self.assertEqual(analyze.complete_counter_sum(rows, 'x'), 10)

    def test_raw_outputs_and_pair_completeness_are_verified(self):
        rows = [json.loads(s) for s in (ROOT/'semantic/data/raw.jsonl').read_text().splitlines()]
        rows = [r for r in rows if not r['warmup'] and r['phase'] in ('off','on')]
        with gzip.open(ROOT/'semantic/data/corpus.json.gz', 'rt') as f:
            cases = json.load(f)['cases']
        semantic.validate_evidence(rows, cases)
        with self.assertRaises(ValueError): semantic.validate_evidence(rows[:-1], cases)
        with self.assertRaises(ValueError): semantic.validate_evidence(rows + [rows[0]], cases)
        damaged = copy.deepcopy(rows)
        damaged[0]['output'] = 'incorrect but old valid flag remains true'
        with self.assertRaises(ValueError): semantic.validate_evidence(damaged, cases)

    def test_connection_failure_is_recorded_as_invalid(self):
        class Connection:
            def __init__(self, *a, **kw): pass
            def connect(self): raise ConnectionRefusedError('unavailable')
            def close(self): pass
        args = SimpleNamespace(metrics_url=None, model='fixture', base_url='http://localhost/v1',
                               timeout=1, label='unit-test')
        monitor = SimpleNamespace(reason=None, lock=threading.Lock(), samples=[], connection=None)
        case = dict(id='test', family='test', category='test', messages=[], max_tokens=8, expected_input_tokens=10)
        with patch.object(benchmark.http.client, 'HTTPConnection', Connection):
            row = benchmark.request(case, args, {}, monitor)
        self.assertFalse(row['valid'])
        self.assertIn('ConnectionRefusedError', row['errors'])
        self.assertIsNone(row['client_ttft'])

    def test_truncated_sse_is_not_a_successful_benchmark(self):
        event = {'choices':[{'delta':{'content':'hello'}}],
                 'usage':{'prompt_tokens':10,'completion_tokens':1}}
        class Response(io.BytesIO):
            status = 200
            def getheader(self, key): return 'text/event-stream'
        class Connection:
            def __init__(self, *a, **kw): pass
            def connect(self): pass
            def request(self, *a, **kw): pass
            def getresponse(self): return Response(('data: '+json.dumps(event)+'\n\n').encode())
            def close(self): pass
        args = SimpleNamespace(metrics_url=None, model='fixture', base_url='http://localhost/v1',
                               timeout=1, label='unit-test')
        monitor = SimpleNamespace(reason=None, lock=threading.Lock(), samples=[], connection=None)
        case = dict(id='test', family='test', category='test', messages=[], max_tokens=8, expected_input_tokens=10)
        with patch.object(benchmark.http.client, 'HTTPConnection', Connection):
            row = benchmark.request(case, args, {}, monitor)
        self.assertFalse(row['valid'])
        self.assertTrue(any('incomplete SSE' in e for e in row['errors']))

    def test_controlled_clock_includes_connect_without_changing_historical_clock(self):
        event={'choices':[{'delta':{'content':'hello'},'finish_reason':'stop'}],
               'usage':{'prompt_tokens':10,'completion_tokens':1}}
        clock=[0]
        class Response(io.BytesIO):
            status=200
            def getheader(self,key):return 'text/event-stream'
            def readline(self,*a):
                clock[0]+=10_000_000
                return super().readline(*a)
        class Connection:
            def __init__(self,*a,**kw):pass
            def connect(self):clock[0]+=2_000_000_000
            def request(self,*a,**kw):clock[0]+=3_000_000_000
            def getresponse(self):return Response(('data: '+json.dumps(event)+'\n\ndata: [DONE]\n').encode())
            def close(self):pass
        args=SimpleNamespace(metrics_url=None,model='fixture',base_url='http://localhost/v1',timeout=10,label='clock')
        monitor=SimpleNamespace(reason=None,lock=threading.Lock(),samples=[],connection=None)
        case=dict(id='test',family='test',category='test',messages=[],max_tokens=8,expected_input_tokens=10)
        with patch.object(benchmark.http.client,'HTTPConnection',Connection),patch.object(benchmark.time,'perf_counter_ns',lambda:clock[0]):
            historical=benchmark.request(case,args,{},monitor)
            clock[0]=0;args.include_connection_setup=True
            controlled=benchmark.request(case,args,{},monitor)
        self.assertTrue(historical['valid'] and controlled['valid'])
        self.assertAlmostEqual(controlled['client_ttft']-historical['client_ttft'],2)
        self.assertAlmostEqual(controlled['client_e2e']-historical['client_e2e'],2)

if __name__ == '__main__': unittest.main()
