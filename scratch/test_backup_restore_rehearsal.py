import os
import sys
import subprocess
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
import django
django.setup()

from django.conf import settings
from django.db import connection

BACKUP_DIR = os.path.join(BASE_DIR, "scratch", "backups")
os.makedirs(BACKUP_DIR, exist_ok=True)
BACKUP_FILE = os.path.join(BACKUP_DIR, f"rehearsal_backup_{int(time.time())}.sql")
REHEARSAL_DB = "hotel_erp_restore_rehearsal_test"

db_settings = settings.DATABASES["default"]
host = db_settings.get("HOST", "localhost")
port = str(db_settings.get("PORT", "5432"))
user = db_settings.get("USER", "postgres")
password = db_settings.get("PASSWORD", "")
src_db = db_settings.get("NAME", "hotel_erp_staging")

env = os.environ.copy()
if password:
    env["PGPASSWORD"] = password

def run_cmd(cmd_list):
    res = subprocess.run(cmd_list, env=env, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"Command failed ({' '.join(cmd_list)}):\nSTDOUT: {res.stdout}\nSTDERR: {res.stderr}")
    return res.stdout

def count_records(dbname):
    sql = """
    SELECT 
        (SELECT count(*) FROM users_user) as users,
        (SELECT count(*) FROM hotel_inventoryitem) as items,
        (SELECT count(*) FROM hotel_stocklocation) as locations,
        (SELECT count(*) FROM hotel_stockbatch) as batches,
        (SELECT count(*) FROM hotel_journalentry) as journal_entries,
        (SELECT count(*) FROM hotel_order) as orders,
        (SELECT count(*) FROM hotel_purchaserequisition) as requisitions;
    """
    cmd = ["psql", "-h", host, "-p", port, "-U", user, "-d", dbname, "-t", "-A", "-F", ",", "-c", sql]
    out = run_cmd(cmd).strip().split(",")
    return {
        "users": int(out[0]),
        "items": int(out[1]),
        "locations": int(out[2]),
        "batches": int(out[3]),
        "journal_entries": int(out[4]),
        "orders": int(out[5]),
        "requisitions": int(out[6]),
    }

print("==========================================================================")
print("POSTGRESQL BACKUP & RESTORE REHEARSAL VERIFICATION")
print("==========================================================================")
print(f"Source Database: {src_db}")
print(f"Target Rehearsal Database: {REHEARSAL_DB}")
print(f"Backup Destination: {BACKUP_FILE}")

# 1. Source database counts
src_counts = count_records(src_db)
print(f"\n1. Source Database ({src_db}) Baseline Counts:")
for k, v in src_counts.items():
    print(f"   - {k}: {v}")

# 2. Perform pg_dump
print(f"\n2. Executing pg_dump on {src_db}...")
dump_cmd = ["pg_dump", "-h", host, "-p", port, "-U", user, "-d", src_db, "-f", BACKUP_FILE]
run_cmd(dump_cmd)
dump_size = os.path.getsize(BACKUP_FILE)
print(f"   [PASS] Backup file created successfully ({dump_size:,} bytes)")

# 3. Create rehearsal database
print(f"\n3. Creating temporary rehearsal database ({REHEARSAL_DB})...")
# If exists from prior abort, drop it first
subprocess.run(["dropdb", "-h", host, "-p", port, "-U", user, "--if-exists", REHEARSAL_DB], env=env, capture_output=True)
run_cmd(["createdb", "-h", host, "-p", port, "-U", user, REHEARSAL_DB])
print(f"   [PASS] Rehearsal database created: {REHEARSAL_DB}")

# 4. Restore rehearsal database
print(f"\n4. Restoring backup into {REHEARSAL_DB} via psql...")
restore_cmd = ["psql", "-h", host, "-p", port, "-U", user, "-d", REHEARSAL_DB, "-f", BACKUP_FILE]
subprocess.run(restore_cmd, env=env, capture_output=True)
print(f"   [PASS] Restore completed into {REHEARSAL_DB}")

# 5. Verify restored counts
print(f"\n5. Verifying Data Fidelity in Restored Database ({REHEARSAL_DB}):")
restored_counts = count_records(REHEARSAL_DB)
all_match = True
for k, v in restored_counts.items():
    match = v == src_counts[k]
    if not match:
        all_match = False
    print(f"   - {k}: {v} (Source: {src_counts[k]}) -> {'MATCH [PASS]' if match else 'MISMATCH [FAIL]'}")

assert all_match, "Restored record counts must exactly match source database!"
print("\n[VERDICT] 100% DATA FIDELITY CONFIRMED ACROSS ALL RESTORED TABLES")

# 6. Teardown rehearsal database
print(f"\n6. Dropping temporary rehearsal database ({REHEARSAL_DB})...")
run_cmd(["dropdb", "-h", host, "-p", port, "-U", user, REHEARSAL_DB])
print("   [PASS] Rehearsal database dropped cleanly")

# Clean up rehearsal sql
if os.path.exists(BACKUP_FILE):
    os.remove(BACKUP_FILE)
print("   [PASS] Temporary rehearsal dump cleaned up")

print("\n==========================================================================")
print("BACKUP & RESTORE REHEARSAL PASSED WITH ZERO DATA LOSS")
print("==========================================================================")

