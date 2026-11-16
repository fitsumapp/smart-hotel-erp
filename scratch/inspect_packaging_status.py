import subprocess
import os
import hashlib

output = subprocess.check_output(['git', 'status', '--porcelain']).decode('utf-8', errors='replace').splitlines()

tracked_modified = []
untracked = []

for line in output:
    code = line[:2]
    fname = line[3:].strip()
    if fname.startswith('"') and fname.endswith('"'):
        fname = fname[1:-1]
    if code in (' M', 'M ', 'MM'):
        tracked_modified.append(fname)
    elif code == '??':
        untracked.append(fname)

print(f"Tracked modified count: {len(tracked_modified)}")
print(f"Untracked count: {len(untracked)}")

# Categorize untracked
backend_core = []
migrations = []
frontend_core = []
tests = []
docs_evidence = []
scratch_temp = []
agent_internal = []
env_sensitive = []
other = []

for item in untracked:
    norm = item.replace('\\', '/')
    if norm.startswith('scratch/'):
        scratch_temp.append(norm)
    elif norm.startswith('.agents/'):
        agent_internal.append(norm)
    elif '.env' in norm:
        env_sensitive.append(norm)
    elif 'migrations/' in norm:
        migrations.append(norm)
    elif norm.startswith('hotel-frontend/src/'):
        frontend_core.append(norm)
    elif norm.startswith('docs/') or norm.startswith('DOCUMENTATION_') or norm.endswith('.md'):
        docs_evidence.append(norm)
    elif norm.startswith('hotel/') or norm.startswith('apps/'):
        if 'tests/' in norm or 'test_' in norm:
            tests.append(norm)
        else:
            backend_core.append(norm)
    elif norm.startswith('hotel_management_backend.egg-info'):
        scratch_temp.append(norm)
    else:
        other.append(norm)

print("\n--- Categorization of Untracked Items ---")
print(f"Backend Core Modules: {len(backend_core)}")
for f in backend_core:
    print(f"  {f}")

print(f"\nMigrations: {len(migrations)}")
for f in migrations:
    print(f"  {f}")

print(f"\nFrontend Core: {len(frontend_core)}")
for f in frontend_core:
    print(f"  {f}")

print(f"\nTests: {len(tests)}")
for f in tests:
    print(f"  {f}")

print(f"\nDocs & Evidence: {len(docs_evidence)}")
for f in docs_evidence:
    print(f"  {f}")

print(f"\nEnv / Sensitive (MUST EXCLUDE): {len(env_sensitive)}")
for f in env_sensitive:
    print(f"  {f}")

print(f"\nScratch / Temp / Build Artifacts (MUST EXCLUDE): {len(scratch_temp)}")
for f in scratch_temp[:10]:
    print(f"  {f}")
if len(scratch_temp) > 10:
    print(f"  ... and {len(scratch_temp) - 10} more")

print(f"\nInternal Agent Records (EXCLUDE): {len(agent_internal)}")
for f in agent_internal:
    print(f"  {f}")

print(f"\nOther: {len(other)}")
for f in other:
    print(f"  {f}")

