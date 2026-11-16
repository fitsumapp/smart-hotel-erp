"""
Targeted Staging Database Cleanup Script for DEF-02.

Target Location: scratch/cleanup_staging_payroll.py
Execution Command (by Worker upon supervisor approval):
    .venv\\Scripts\\python.exe scratch/cleanup_staging_payroll.py

Authoritative Cleanup Scope:
- Purges ONLY the 3 draft payroll records created by ad-hoc verification in Milestone 1 Iteration 2:
  - PayrollEntry id=4: employee_name='Test', status='draft', basic_salary=1000.00
  - PayrollEntry id=5: employee_name='T',    status='draft', basic_salary=100.00
  - PayrollEntry id=6: employee_name='T',    status='draft', basic_salary=100.00
- Confirms 0 GL journal entries exist for these entries.
- Confirms 0 incoming foreign keys exist.
- Confirms all 37 staging user accounts remain 100% intact.
- Mandates atomic rollbacks for all future ad-hoc verifications.
"""

import os
import sys
from decimal import Decimal

# Bootstrap Django environment
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
import django
django.setup()

from django.db import connection, transaction
from hotel.models import PayrollEntry, JournalEntry
from users.models import User


def main():
    print("=" * 70)
    print("ACRMA HOTEL ERP — STAGING DATABASE PAYROLL CLEANUP (DEF-02)")
    print("=" * 70)

    # 1. Database Safety Assertion
    db_name = connection.settings_dict["NAME"]
    print(f"[*] Connected Database: {db_name}")
    if db_name != "hotel_erp_staging":
        raise RuntimeError(
            f"SAFETY ABORT: Expected database 'hotel_erp_staging', but connected to '{db_name}'. "
            "Cleanup script refuses to run against any other database."
        )

    # 2. Pre-Verification Forensics
    total_users_before = User.objects.count()
    total_payroll_before = PayrollEntry.objects.count()
    total_payroll_gl = JournalEntry.objects.filter(description__icontains="payroll").count()

    print(f"[*] Pre-cleanup User count: {total_users_before}")
    print(f"[*] Pre-cleanup PayrollEntry count: {total_payroll_before}")
    print(f"[*] Pre-cleanup Payroll JournalEntry count: {total_payroll_gl}")

    if total_users_before != 37:
        raise RuntimeError(f"INTEGRITY ERROR: Expected exactly 37 users in staging, found {total_users_before}.")

    if total_payroll_gl != 0:
        raise RuntimeError(f"FINANCIAL INTEGRITY ERROR: Found {total_payroll_gl} General Ledger entries mentioning payroll.")

    # Snapshot all user IDs before cleanup
    user_ids_before = set(User.objects.values_list("id", flat=True))

    # 3. Targeted Record Inspection
    target_ids = [4, 5, 6]
    entries = list(PayrollEntry.objects.filter(id__in=target_ids).order_by("id"))

    if len(entries) != 3:
        raise RuntimeError(
            f"FORENSIC MISMATCH: Expected exactly 3 records for IDs [4, 5, 6], found {len(entries)}. "
            f"Existing IDs: {[e.id for e in entries]}"
        )

    expected_specs = {
        4: {"name": "Test", "salary": Decimal("1000.00"), "dept": "kitchen", "status": "draft"},
        5: {"name": "T",    "salary": Decimal("100.00"),  "dept": "kitchen", "status": "draft"},
        6: {"name": "T",    "salary": Decimal("100.00"),  "dept": "kitchen", "status": "draft"},
    }

    print("[*] Inspecting target records:")
    for entry in entries:
        spec = expected_specs[entry.id]
        print(f"    - ID {entry.id}: name='{entry.employee_name}', status='{entry.status}', salary={entry.basic_salary}")

        assert entry.employee_name == spec["name"], (
            f"Assertion failed: Entry {entry.id} employee_name='{entry.employee_name}', expected '{spec['name']}'"
        )
        assert entry.status == spec["status"], (
            f"Assertion failed: Entry {entry.id} status='{entry.status}', expected '{spec['status']}'"
        )
        assert entry.basic_salary == spec["salary"], (
            f"Assertion failed: Entry {entry.id} basic_salary={entry.basic_salary}, expected {spec['salary']}"
        )
        assert entry.department == spec["dept"], (
            f"Assertion failed: Entry {entry.id} department='{entry.department}', expected '{spec['dept']}'"
        )

    # Verify no foreign key relations point to PayrollEntry
    related_models = [r.related_model.__name__ for r in PayrollEntry._meta.related_objects]
    if related_models:
        raise RuntimeError(f"INTEGRITY ERROR: Found incoming reverse relations to PayrollEntry: {related_models}")

    # 4. Targeted Atomic Deletion
    print("[*] Executing targeted atomic deletion for IDs [4, 5, 6]...")
    with transaction.atomic():
        deleted_count, details = PayrollEntry.objects.filter(id__in=target_ids).delete()
        print(f"[*] Deletion result: {deleted_count} record(s) deleted: {details}")

        if deleted_count != 3:
            raise RuntimeError(f"DELETION ANOMALY: Expected 3 deleted records, but got {deleted_count}. Transaction rolling back.")

    # 5. Post-Deletion Verification
    remaining_targets = PayrollEntry.objects.filter(id__in=target_ids).count()
    remaining_total_payroll = PayrollEntry.objects.count()
    total_users_after = User.objects.count()
    user_ids_after = set(User.objects.values_list("id", flat=True))

    print(f"[*] Post-cleanup target records remaining: {remaining_targets}")
    print(f"[*] Post-cleanup total PayrollEntry count: {remaining_total_payroll}")
    print(f"[*] Post-cleanup User count: {total_users_after}")

    assert remaining_targets == 0, f"Error: Target IDs still exist ({remaining_targets})"
    assert total_users_after == 37, f"Error: User count changed from 37 to {total_users_after}"
    assert user_ids_after == user_ids_before, "Error: User ID set mutated during cleanup!"

    print("=" * 70)
    print("SUCCESS: DEF-02 Staging Database Cleanup Completed Cleanly.")
    print("All 3 draft test payroll records purged. 0 GL entries affected.")
    print("All 37 staging user accounts remain 100% intact.")
    print("=" * 70)


if __name__ == "__main__":
    main()
