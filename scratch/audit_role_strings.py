import os, re

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
py_files = []
for root, dirs, files in os.walk(BASE_DIR):
    if any(skip in root for skip in ['.venv', '.git', 'node_modules', '__pycache__', 'scratch']):
        continue
    for f in files:
        if f.endswith('.py'):
            py_files.append(os.path.join(root, f))

# Look for patterns like role == "...", role in ["...", "..."], role in {"...", "..."}
role_check_re = re.compile(r'role\s*(?:==|in|!=)\s*([\[\{\("][^\]\}\)]+[\]\}\)"])', re.IGNORECASE)

print(f"Scanning {len(py_files)} files for role checks...")
all_roles_found = set()
files_with_roles = {}

for p in py_files:
    rel_path = os.path.relpath(p, BASE_DIR)
    with open(p, 'r', encoding='utf-8', errors='ignore') as f:
        for idx, line in enumerate(f, 1):
            m = role_check_re.search(line)
            if m:
                matched_str = m.group(1)
                # extract quoted words
                words = re.findall(r'["\']([a-zA-Z0-9_\-]+)["\']', matched_str)
                if words:
                    all_roles_found.update(words)
                    files_with_roles.setdefault(rel_path, []).append((idx, line.strip(), words))

print("\n=== ALL ROLE IDENTIFIERS CHECKED IN CODE ===")
for r in sorted(all_roles_found):
    print(f"  - '{r}'")

print("\n=== DETAILS OF ROLE CHECKS BY FILE ===")
for fpath, items in sorted(files_with_roles.items()):
    print(f"\n--- {fpath} ---")
    for lno, line, words in items:
        print(f"  L{lno:4}: {words}  <--  {line}")

