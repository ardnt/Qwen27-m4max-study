"""Regenerate hashes after reviewing all changes; not a privacy audit."""
import hashlib
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
EXCLUDE = {'.git', '__pycache__', '.build'}
GENERATED = {'MANIFEST.json','semantic/data/summary.json','semantic/data/results.csv','semantic/data/output-pairs.json'}
files = []
for path in sorted(ROOT.rglob('*')):
    relative = path.relative_to(ROOT)
    if not path.is_file() or EXCLUDE.intersection(relative.parts) or str(relative) in GENERATED:
        continue
    data = path.read_bytes()
    files.append(dict(path=relative.as_posix(), bytes=len(data), sha256=hashlib.sha256(data).hexdigest()))
(ROOT/'MANIFEST.json').write_text(json.dumps({'files':files,'uncompressed_bytes':sum(f['bytes'] for f in files),
    'scope':'All distributed files except this manifest; historical artifact included. Hashes establish integrity, not privacy or authenticity.'},indent=2)+'\n')
print('Hashed',len(files),'files')
