import os
import subprocess
import hashlib
import re

# Exclusion patterns
EXCLUDE_PREFIXES = [
    'scratch/',
    '.agents/',
    'hotel-frontend/.env',
    '-files',
    'hotel_management_backend.egg-info',
    'hotel-frontend/build/',
]

def should_exclude(filepath):
    norm = filepath.replace('\\', '/')
    for prefix in EXCLUDE_PREFIXES:
        if norm.startswith(prefix) or ('/' + prefix) in norm:
            return True
    if norm.endswith('.pyc') or '__pycache__' in norm or norm.endswith('.sql'):
        return True
    return False

# 1. Get status
status_lines = subprocess.check_output(['git', 'status', '--porcelain']).decode('utf-8', errors='replace').splitlines()

files_to_stage = []
files_excluded = []

for line in status_lines:
    code = line[:2]
    fname = line[3:].strip()
    if fname.startswith('"') and fname.endswith('"'):
        fname = fname[1:-1]
    
    norm_path = fname.replace('\\', '/')
    
    if should_exclude(norm_path):
        files_excluded.append(norm_path)
        continue

    # If it's a directory (untracked dir), expand its contents
    if os.path.isdir(fname):
        for root, dirs, files in os.walk(fname):
            for f in files:
                full_path = os.path.join(root, f).replace('\\', '/')
                if should_exclude(full_path):
                    files_excluded.append(full_path)
                else:
                    files_to_stage.append(full_path)
    else:
        files_to_stage.append(norm_path)

files_to_stage = sorted(list(set(files_to_stage)))
files_excluded = sorted(list(set(files_excluded)))

print(f"Total files identified for staging: {len(files_to_stage)}")
print(f"Total files/dirs identified for exclusion: {len(files_excluded)}")

# 2. Stage files in batches using git add
print("\nStaging files via git add...")
batch_size = 50
for i in range(0, len(files_to_stage), batch_size):
    batch = files_to_stage[i:i+batch_size]
    cmd = ['git', 'add'] + batch
    subprocess.check_call(cmd)

# 3. Verify staged files
staged = subprocess.check_output(['git', 'diff', '--cached', '--name-only']).decode('utf-8', errors='replace').splitlines()
staged = [s.strip().replace('\\', '/') for s in staged if s.strip()]
print(f"Total files currently staged in index: {len(staged)}")

missing = set(files_to_stage) - set(staged)
if missing:
    print(f"WARNING: Missing from staging: {missing}")
else:
    print("SUCCESS: All verified files are staged in Git index.")

unwanted_staged = [s for s in staged if should_exclude(s)]
if unwanted_staged:
    print(f"CRITICAL ERROR: Unwanted files staged: {unwanted_staged}")
else:
    print("SUCCESS: Zero excluded or sensitive files are staged.")

