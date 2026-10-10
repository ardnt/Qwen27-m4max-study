"""Sequential fixed-corpus requests to an existing endpoint; no service control."""
import argparse
import datetime
import gzip
import hashlib
import http.client
import json
import os
import platform
import random
import re
import socket
import subprocess
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def metrics(url, headers):
    if not url:
        return {}
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            text = response.read().decode()
    except (OSError, ValueError):
        return {}
    result = {}
    for line in text.splitlines():
        if line.startswith('#'):
            continue
        fields = line.split()
        if len(fields) == 2 and '{' not in fields[0]:
            try:
                result[fields[0]] = float(fields[1])
            except ValueError:
                pass
    return result

class MemoryMonitor:
    """Observe macOS pressure/swap and interrupt the client on unsafe growth."""
    def __init__(self, enabled):
        self.enabled = enabled and platform.system() == 'Darwin'
        self.stop = threading.Event()
        self.lock = threading.Lock()
        self.connection = None
        self.reason = None
        self.samples = []
        self.started = time.perf_counter()
        self.thread = threading.Thread(target=self.run, daemon=True)

    def sample(self):
        pressure = subprocess.run(['sysctl', '-n', 'kern.memorystatus_vm_pressure_level'],
                                  capture_output=True, text=True, timeout=2)
        swap = subprocess.run(['sysctl', 'vm.swapusage'], capture_output=True,
                              text=True, timeout=2)
        match = re.search(r'used\s*=\s*([0-9.]+)([KMG])', swap.stdout)
        return {'elapsed_seconds': time.perf_counter() - self.started,
                'pressure': int(pressure.stdout.strip()) if pressure.returncode == 0 else None,
                'swap_bytes': (int(float(match[1]) * {'K': 1024, 'M': 1024**2, 'G': 1024**3}[match[2]])
                               if match else None)}

    def run(self):
        if not self.enabled:
            return
        while not self.stop.is_set():
            try:
                sample = self.sample()
                with self.lock:
                    self.samples.append(sample)
                    recent = [s for s in self.samples
                              if sample['elapsed_seconds'] - s['elapsed_seconds'] <= 10
                              and s['swap_bytes'] is not None]
                    if sample['pressure'] == 4:
                        self.reason = 'critical macOS memory pressure'
                    if sample['swap_bytes'] is not None and recent:
                        if sample['swap_bytes'] - min(s['swap_bytes'] for s in recent) >= 512 * 1024**2:
                            self.reason = 'at least 512 MiB of swap growth within 10 seconds'
                    connection = self.connection
                if self.reason and connection is not None and connection.sock is not None:
                    try:
                        connection.sock.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass
                    return
            except (OSError, ValueError, subprocess.TimeoutExpired):
                pass
            self.stop.wait(.5)

    def start(self):
        if self.enabled:
            initial = self.sample()
            self.samples.append(initial)
            if initial['pressure'] == 4:
                raise RuntimeError('critical memory pressure before benchmarking')
            self.thread.start()

    def finish(self):
        self.stop.set()
        if self.thread.is_alive():
            self.thread.join(timeout=3)

def request(case, args, headers, monitor):
    if monitor.reason:
        raise RuntimeError(monitor.reason)
    before = metrics(args.metrics_url, headers)
    if before.get('splash_frontend_active', 0) > 0 or before.get('splash_scheduler_queued', 0) > 0:
        raise RuntimeError('endpoint already has active or queued requests')
    body = {'model': args.model, 'messages': case['messages'], 'temperature': 0,
            'seed': 20261010, 'max_tokens': case['max_tokens'], 'stream': True,
            'stream_options': {'include_usage': True}, 'tool_choice': 'none',
            'reasoning_effort': 'none', 'chat_template_kwargs': {'enable_thinking': False}}
    assert 'tools' not in body
    prepare = time.perf_counter_ns()
    payload = json.dumps(body, ensure_ascii=False).encode()
    prepare = time.perf_counter_ns() - prepare
    url = urllib.parse.urlsplit(args.base_url.rstrip('/') + '/chat/completions')
    factory = http.client.HTTPSConnection if url.scheme == 'https' else http.client.HTTPConnection
    conn = factory(url.hostname, url.port, timeout=args.timeout)
    with monitor.lock:
        monitor.connection = conn
        sample_begin = len(monitor.samples)
    first = visible = last = None
    usage = None
    output, reasoning, extras, errors = [], [], {}, []
    tool_calls = False
    finish = None
    stream_done = False
    status = None
    started = time.perf_counter_ns()
    connection_setup_seconds = None
    try:
        conn.connect()
        connection_setup_seconds = (time.perf_counter_ns() - started) / 1e9
        if monitor.reason:
            raise RuntimeError(monitor.reason)
        # Successful request timers intentionally exclude connection setup.
        started = time.perf_counter_ns()
        conn.request('POST', url.path + ('?' + url.query if url.query else ''), payload,
                     {'Content-Type': 'application/json', **headers})
        response = conn.getresponse()
        status = response.status
        if status != 200:
            errors.append('HTTP ' + str(status))
            response.read()
        else:
            if 'text/event-stream' not in (response.getheader('Content-Type') or ''):
                raise ValueError('endpoint did not return an SSE stream')
            while line := response.readline():
                now = time.perf_counter_ns()
                line = line.strip()
                if not line.startswith(b'data:'):
                    continue
                data = line[5:].strip()
                if data == b'[DONE]':
                    stream_done = True
                    break
                event = json.loads(data)
                if event.get('error'):
                    errors.append('server error event')
                if event.get('usage'):
                    usage = event['usage']
                for key in ('timings', 'metrics', 'speculative'):
                    if key in event:
                        extras[key] = event[key]
                for choice in event.get('choices', []):
                    delta = choice.get('delta', {})
                    content = delta.get('content') or ''
                    thought = delta.get('reasoning_content') or delta.get('reasoning') or ''
                    if content or thought:
                        first = first or now
                        last = now
                    if content:
                        visible = visible or now
                        output.append(content)
                    if thought:
                        reasoning.append(thought)
                    tool_calls = tool_calls or bool(delta.get('tool_calls'))
                    finish = choice.get('finish_reason') or finish
    except (OSError, ValueError, RuntimeError, http.client.HTTPException) as exc:
        errors.append(type(exc).__name__)
    finally:
        ended = time.perf_counter_ns()
        with monitor.lock:
            monitor.connection = None
        conn.close()
    after = metrics(args.metrics_url, headers)
    counters = {k: after[k] - before[k] for k in before.keys() & after.keys()
                if k.startswith('splash_') and (k.endswith('_total') or k.endswith('_sum'))}
    if status == 200 and (not stream_done or finish is None):
        errors.append('incomplete SSE response: missing finish reason or DONE')
    if any(v < 0 for v in counters.values()):
        errors.append('runtime counters reset during request')
    concurrent = counters.get('splash_requests_submitted_total')
    if concurrent is not None and concurrent != 1:
        errors.append('counter interval includes other requests')
    if monitor.reason:
        errors.append(monitor.reason)
    text = ''.join(output)
    actual_input = (usage or {}).get('prompt_tokens')
    actual_output = (usage or {}).get('completion_tokens')
    input_matches = actual_input == case['expected_input_tokens'] if actual_input is not None else None
    row = {'case_id': case['id'], 'family': case['family'], 'category': case['category'],
           'phase': args.label, 'repeat': case.get('repeat'), 'warmup': case['id'] == 'spec-prime',
           'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
           'http_status': status, 'connection_setup_seconds': connection_setup_seconds, 'client_ttft': (first - started) / 1e9 if first else None,
           'client_visible': (visible - started) / 1e9 if visible else None,
           'client_e2e': (ended - started) / 1e9, 'json_serialization_ns': prepare,
           'prompt_tokens': actual_input, 'output_tokens': actual_output,
           'cached_tokens': (usage or {}).get('prompt_tokens_details', {}).get('cached_tokens'),
           'reasoning_tokens': (usage or {}).get('completion_tokens_details', {}).get('reasoning_tokens'),
           'expected_input_tokens': case['expected_input_tokens'], 'input_count_matches': input_matches,
           'output': text, 'reasoning': ''.join(reasoning), 'output_sha256': hashlib.sha256(text.encode()).hexdigest(),
           'finish_reason': finish, 'tool_calls_seen': tool_calls, 'errors': errors,
           'settings': {k: v for k, v in body.items() if k not in ('messages', 'model')},
           'backend_metrics': extras, 'runtime_counter_deltas': counters,
           'memory_samples': monitor.samples[sample_begin:],
           'peak_family_footprint_bytes': None, 'backend_decode_tps': extras.get('timings', {}).get('predicted_per_second'),
           'client_decode_tps': None, 'effective_prefill_tps': None,
           'effective_output_tps': actual_output / ((ended - started) / 1e9) if actual_output else None}
    row['valid'] = (status == 200 and not errors and not tool_calls and first is not None
                    and isinstance(actual_input, int) and actual_input > 0
                    and isinstance(actual_output, int) and actual_output > 0)
    return row

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', required=True, help='OpenAI-compatible base URL including /v1')
    parser.add_argument('--model', required=True)
    parser.add_argument('--label', required=True, help='Build/configuration name recorded with each result')
    parser.add_argument('--output', type=Path, required=True, help='New JSONL output file; existing files are refused')
    parser.add_argument('--suite', choices=('branch', 'prefill', 'speculation', 'all', 'semantic'), required=True)
    parser.add_argument('--metrics-url', help='Optional native Prometheus endpoint; otherwise internal counters unavailable')
    parser.add_argument('--token-env', default='BENCH_API_KEY', help='Read a key from this environment variable; never record it')
    parser.add_argument('--timeout', type=float, default=120)
    args = parser.parse_args()
    parsed = urllib.parse.urlsplit(args.base_url)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
        parser.error('base URL must be http(s), without embedded credentials')
    if args.timeout <= 0:
        parser.error('timeout must be positive')
    corpus_path = ROOT / ('semantic/data/corpus.json.gz' if args.suite == 'semantic' else 'data/prompts.json.gz')
    with gzip.open(corpus_path, 'rt') as f:
        corpus = json.load(f)
    cases = {case['id']: case for case in corpus['cases']}
    ids = list(cases) if args.suite == 'semantic' else ['spec-prime']
    if args.suite in ('speculation', 'all'):
        generation = [f'spec-{category}-{r}' for category in ('english', 'arabic', 'python') for r in range(7)]
        random.Random(202610102).shuffle(generation)
        ids += generation
    if args.suite in ('prefill', 'all'):
        ids += [f'cold-{r}' for r in range(7)]
    if args.suite in ('branch', 'all'):
        ids += [f'branch-{r}-{stage}' for r in range(7) for stage in ('prime', 'changed', 'repeat')]
    headers = {}
    if token := os.environ.get(args.token_env):
        headers['Authorization'] = 'Bearer ' + token
    monitor = MemoryMonitor(True)
    try:
        monitor.start()
        with args.output.open('x') as f:
            for identifier in ids:
                row = request(cases[identifier], args, headers, monitor)
                f.write(json.dumps(row, ensure_ascii=False) + '\n')
                f.flush()
                print(identifier, 'TTFT', row['client_ttft'], 'input', row['prompt_tokens'],
                      'reused', row['cached_tokens'], 'valid', row['valid'], flush=True)
                if not row['valid']:
                    raise RuntimeError('Invalid sample; stopped without controlling the service')
    finally:
        monitor.finish()

if __name__ == '__main__':
    main()
