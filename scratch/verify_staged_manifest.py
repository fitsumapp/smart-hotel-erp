import subprocess
import hashlib
import os

staged_files = subprocess.check_output(['git', 'diff', '--cached', '--name-only']).decode('utf-8', errors='replace').splitlines()
staged_files = [f.strip().replace('\\', '/') for f in staged_files if f.strip()]

print(f"Total Staged Files: {len(staged_files)}")

# Group by category
backend_apps = []
migrations = []
frontend_files = []
tests = []
docs = []
other = []

for f in staged_files:
    if 'migrations/' in f:
        migrations.append(f)
    elif f.startswith('hotel-frontend/'):
        frontend_files.append(f)
    elif 'tests/' in f or 'test_' in f:
        tests.append(f)
    elif f.startswith('docs/') or f.endswith('.md'):
        docs.append(f)
    elif f.startswith('apps/') or f.startswith('hotel/') or f.startswith('users/') or f.startswith('core/'):
        backend_apps.append(f)
    else:
        other.append(f)

print(f"\n1. Backend App & Logic Files: {len(backend_apps)}")
for f in sorted(backend_apps):
    print(f"   {f}")

print(f"\n2. Migrations: {len(migrations)}")
for f in sorted(migrations):
    print(f"   {f}")

print(f"\n3. Frontend Files: {len(frontend_files)}")
for f in sorted(frontend_files):
    print(f"   {f}")

print(f"\n4. Automated Test Files: {len(tests)}")
for f in sorted(tests):
    print(f"   {f}")

print(f"\n5. Documentation & Evidence: {len(docs)}")
for f in sorted(docs):
    print(f"   {f}")

# Composite checksum of staged files
hasher = hashlib.sha256()
for f in sorted(staged_files):
    if os.path.isfile(f):
        with open(f, 'rb') as fp:
            hasher.update(fp.read())

print(f"\nComposite Staged Release Source Checksum (SHA-256): {hasher.hexdigest()}")

