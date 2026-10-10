"""Offline, model-free verification. Requires Python 3.10+ and a C++20 compiler."""
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
ROOT = Path(__file__).resolve().parent

def run(args):
    subprocess.run(args, cwd=ROOT, check=True)

def main():
    manifest = json.loads((ROOT/'MANIFEST.json').read_text())
    for item in manifest['files']:
        data = (ROOT/item['path']).read_bytes()
        assert len(data) == item['bytes'] and hashlib.sha256(data).hexdigest() == item['sha256'], item['path']
    print(f"Verified {len(manifest['files'])} manifest entries", flush=True)
    with tempfile.TemporaryDirectory(prefix='qwen-study-') as directory:
        out = Path(directory)
        run([sys.executable,'analyze.py','--check','--output',str(out/'original.json')])
        run([sys.executable,'semantic/analyze.py','--check','--output-dir',str(out/'semantic')])
        run([sys.executable,'historical/full-benchmark/analyze.py'])
        run([sys.executable,'secondary/drift/analyze.py'])
        run([sys.executable,'controlled/verify.py'])
        run([sys.executable,'-m','unittest','discover','-s','tests','-p','test_*.py','-v'])
        compiler = shlex.split(os.environ.get('CXX','c++'))
        for name, source in [('anchor','tests/branch_anchor_test.cpp'),
                             ('planner','semantic/tests/planner_test.cpp'),
                             ('controller','semantic/tests/controller_test.cpp')]:
            binary = str(out/name)
            run(compiler+['-std=c++20','-O2','-Wall','-Wextra','-Werror','-I','semantic/include',source,'-o',binary])
            run([binary])
        for name in ('planner','controller'):
            binary=str(out/('final-'+name))
            run(compiler+['-std=c++20','-O2','-Wall','-Wextra','-Werror',
                '-I','controlled/final/include',f'controlled/final/tests/{name}_test.cpp','-o',binary])
            run([binary])
    print('All offline evidence and CPU tests passed. No inference or service changes.')

if __name__ == '__main__': main()
