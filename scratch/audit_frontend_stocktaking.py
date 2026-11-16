import os, re

files = []
for root, dirs, fnames in os.walk('hotel-frontend/src'):
    for fn in fnames:
        if fn.endswith('.js') or fn.endswith('.jsx'):
            files.append(os.path.join(root, fn))

for fp in sorted(files):
    with open(fp, 'r', encoding='utf-8', errors='ignore') as f:
        text = f.read()
        if 'Stocktake' in text or 'Procurement' in text:
            print(f"{fp}:")
            for idx, line in enumerate(text.splitlines(), 1):
                if 'Stocktake' in line or 'Procurement' in line or 'stocktaking' in line:
                    if len(line.strip()) < 140:
                        print(f"  L{idx:4}: {line.strip()}")

