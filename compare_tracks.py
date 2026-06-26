from pathlib import Path
import re
p = Path('.')
files = sorted([f.name for f in p.iterdir() if f.suffix.lower() in {'.mp3', '.mp4'}])
html = p.read_text(encoding='utf-8')
sources = re.findall(r'<source src="([^"]+)"', html)
print('FILES', len(files))
print('SOURCES', len(sources))
print('---MISSING IN HTML---')
for f in files:
    if f not in sources:
        print(f)
print('---MISSING AS FILES---')
for s in sources:
    if s not in files:
        print(s)
