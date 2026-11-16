import os
import subprocess
import hashlib
from datetime import datetime

status_lines = subprocess.check_output(['git', 'status', '--porcelain']).decode('utf-8', errors='replace').splitlines()

tracked_modified = []
untracked_core = []

for line in status_lines:
    code = line[:2]
    fname = line[3:].strip()
    if fname.startswith('"') and fname.endswith('"'):
        fname = fname[1:-1]
    
    # Exclude scratch, venv, caches, build artifacts
    if (fname.startswith('scratch/') or 
        fname.startswith('.venv') or 
        fname.startswith('hotel_management_backend.egg-info') or
        fname.endswith('.pyc') or
        '__pycache__' in fname or
        fname.startswith('.parcel-cache')):
        continue
    
    if code in (' M', 'M ', 'MM'):
        tracked_modified.append(fname)
    elif code == '??':
        untracked_core.append(fname)

print(f"Tracked Modified Files: {len(tracked_modified)}")
print(f"Untracked Core Files/Dirs: {len(untracked_core)}")

def get_file_info(filepath):
    if os.path.isfile(filepath):
        size = os.path.getsize(filepath)
        with open(filepath, 'rb') as f:
            sha256 = hashlib.sha256(f.read()).hexdigest()
        return size, sha256
    return None, None

print("\n=== TRACKED MODIFIED FILES ===")
for f in sorted(tracked_modified):
    size, sha256 = get_file_info(f)
    print(f"{f} | {size} bytes | SHA-256: {sha256}")

print("\n=== UNTRACKED CORE FILES / DIRS ===")
all_untracked_files = []
for item in sorted(untracked_core):
    if os.path.isfile(item):
        all_untracked_files.append(item)
    elif os.path.isdir(item):
        for root, dirs, files in os.walk(item):
            # filter pycache
            if '__pycache__' in root:
                continue
            for f in files:
                if f.endswith('.pyc'):
                    continue
                all_untracked_files.append(os.path.join(root, f).replace('\\', '/'))

for f in sorted(all_untracked_files):
    size, sha256 = get_file_info(f)
    print(f"{f} | {size} bytes | SHA-256: {sha256}")

# Calculate Composite Release Checksum
all_release_files = sorted(list(set(tracked_modified + all_untracked_files)))
hasher = hashlib.sha256()
for f in all_release_files:
    if os.path.isfile(f):
        with open(f, 'rb') as fp:
            hasher.update(fp.read())

print(f"\nTotal Release Files: {len(all_release_files)}")
print(f"Composite Release Source Checksum (SHA-256): {hasher.hexdigest()}")

