import os, re

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
py_files = []
for root, dirs, files in os.walk(BASE_DIR):
    if any(skip in root for skip in ['.venv', '.git', 'node_modules', '__pycache__']):
        continue
    for f in files:
        if f.endswith('.py'):
            py_files.append(os.path.join(root, f))

pattern = re.compile(r'(user\.role|request\.user\.role|getattr\(.*?role.*?\)|user\.is_superuser|user\.is_staff)', re.IGNORECASE)

print(f"Scanning {len(py_files)} python files for role / superuser checks...")
findings = {}
for p in py_files:
    rel_path = os.path.relpath(p, BASE_DIR)
    with open(p, 'r', encoding='utf-8', errors='ignore') as f:
        for idx, line in enumerate(f, 1):
            if pattern.search(line):
                findings.setdefault(rel_path, []).append((idx, line.strip()))

for fpath, matches in sorted(findings.items()):
    print(f"\n=== {fpath} ({len(matches)} checks) ===")
    for lno, text in matches[:10]:
        print(f"  L{lno:4}: {text}")
    if len(matches) > 10:
        print(f"  ... and {len(matches) - 10} more")

