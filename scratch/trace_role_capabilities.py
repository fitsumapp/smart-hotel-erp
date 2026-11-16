"""
Inspect capabilities of each role across all modules:
1. Users & Auth (login, MFA, profile, user management)
2. Stock & Stocktaking (sessions, schedules, counts, recount, approve, cancel, delete)
3. Inventory & Batches (items, categories, balances, batches, waste, transfers)
4. Procurement (requisitions, RFQs, quotations, POs, GRNs, supplier invoices)
5. POS & Orders (create, add items, send to KDS, prepare bill, settle, handover)
6. KDS & Bar Station (view queue, start prep, ready, serve)
7. Rooms & Reservations (catalog, booking, check-in, checkout, folio charges, minibar)
8. Finance & Accounting (journals, trial balance, ledgers, cashier shifts, night audit)
9. System Settings (update settings, view settings, features)
10. Reports (occupancy, timing, police, X/Z reports, finance dashboard)
"""
import os, sys
BASE_DIR = os.getcwd()
if BASE_DIR not in sys.path: sys.path.insert(0, BASE_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
import django; django.setup()
import core.urls

from django.contrib.auth import get_user_model
User = get_user_model()

print("Ready to trace roles and permissions.")

