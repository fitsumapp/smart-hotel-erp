# Acrma Hotel ERP — Phase 2.1 Backend Implementation & Evidence Report

**Document Reference:** `ERP-P2.1-BACKEND-REP-2026-V1.0`  
**Audit Date:** 2026-11-03  
**Status:** CONDITIONALLY COMPLETE (CODE COMPLETE; AWAITING DOCUMENTATION, QC DECISION, & OWNER ACCEPTANCE)  
**Governing Branch:** `development`  
**Baseline Commit:** `9d964376345ac47cee79ca7aa2bdc1a41dc71fe2`  
**Primary Subsystem:** RFQ, Supplier Quotation & Split-Award PO Procurement Subsystem  

---

## 1. Executive Summary

Phase 2.1 of the Acrma Hotel Management ERP establishes the operational backend foundation for enterprise procurement, formalizing competitive bidding, supplier quotations, landed cost calculations, split-award evaluations, and seamless purchase order conversion.

This document serves as the formal Phase 2.1 Implementation and Verification Evidence Report (remediating the documentation gap identified during technical survey EXP-1/EXP-2). Direct technical audit verifies that the entire Phase 2.1 backend implementation is **code complete**, **fully integrated into the Django/DRF modular architecture**, **covered by 10/10 passing unit tests**, and **exhibits zero schema drift**.

### Verification Status Matrix
| Verification Pillar | Scope | Result | Status |
| :--- | :--- | :---: | :---: |
| **Data Models** | `hotel/models.py:1584-1845` | RFQ, SQ, and Items with constraints | **VERIFIED COMPLETE** |
| **Database Migration** | `hotel/migrations/0047_*.py` | Non-destructive migration applied | **VERIFIED COMPLETE** |
| **System Sanity Check** | `manage.py check` | 0 issues identified (1 silenced) | **VERIFIED PASS** |
| **Schema Drift Check** | `makemigrations --check` | No changes detected (0 drift) | **VERIFIED PASS** |
| **Service Layer Logic** | `hotel/procurement.py:741-1386` | 8 core functions with row locking | **VERIFIED COMPLETE** |
| **DRF Serializers & API** | `apps/inventory/` views & serializers | Full CRUD + 5 custom actions | **VERIFIED COMPLETE** |
| **Admin Integration** | `hotel/admin.py:533-580` | Unfold admin with tabular inlines | **VERIFIED COMPLETE** |
| **Automated Unit Tests** | `test_rfq_quotation_workflow.py` | 10 passed in 0.409s - 0.846s | **VERIFIED PASS** |
| **Related Suite Tests** | `test_procurement_management.py` | 12 passed in 0.728s - 0.783s | **VERIFIED PASS** |
| **Phase Separation** | `hotel-frontend/src` | Zero RFQ/Quotation UI code | **VERIFIED SEPARATED** |
| **PostgreSQL 16 Run** | Staging DB concurrency | Multi-connection locking test passed | **VERIFIED PASS** |
| **Independent QC Gate** | Neutral QC inspection | Formally audited across 11 standards | **VERIFIED PASS (W/ OBS)** |
| **Owner Acceptance Gate** | Written owner sign-off | Prerequisite for Phase 2.2 kickoff | **AWAITING OWNER REVIEW** |

---

## 2. RFQ & Supplier Quotation Backend Models

The Phase 2.1 data layer is defined in `hotel/models.py` (lines 1584–1845) and strictly adheres to relational integrity, check constraints, and historical traceability.

### 2.1 `RequestForQuotation` (`hotel/models.py:1584-1647`)
Manages formal solicitation requests issued to suppliers for goods or services based on approved Purchase Requisitions.
- **Fields:**
  - `rfq_number` (`CharField(max_length=50, unique=True)`): Unique identifier (e.g. `RFQ-202611-0001`).
  - `title` (`CharField(max_length=255)`): Descriptive procurement title.
  - `requisitions` (`ManyToManyField(PurchaseRequisition, related_name="rfqs")`): Links one or more approved requisitions to this RFQ.
  - `is_public_bidding` (`BooleanField(default=False)`): When `True`, any active supplier may quote; when `False`, bidding is restricted to invited vendors.
  - `invited_suppliers` (`ManyToManyField(Supplier, blank=True, related_name="invited_rfqs")`): Whitelist of authorized vendors for restricted bidding.
  - `status` (`CharField(max_length=20, choices=RFQ_STATUS_CHOICES, default='draft')`): State machine: `draft` -> `published` -> `closed` -> `awarded` -> `cancelled`.
  - `submission_deadline` (`DateTimeField()`): Strict cutoff for vendor submissions.
  - `delivery_location` (`ForeignKey(StockLocation, on_delete=models.PROTECT)`): Target warehouse or receiving dock (defaults to `STORE-MAIN`).
  - `terms_and_conditions` (`TextField(blank=True)`): Commercial terms, delivery expectations, and payment conditions.
  - `created_by` (`ForeignKey(User, on_delete=models.SET_NULL, null=True)`): Purchasing officer who initiated the RFQ.
  - `created_at`, `updated_at`: Audit timestamps.

### 2.2 `RequestForQuotationItem` (`hotel/models.py:1649-1698`)
Line items representing specific inventory SKUs, target quantities, and specifications requested under an RFQ.
- **Fields:**
  - `rfq` (`ForeignKey(RequestForQuotation, on_delete=models.CASCADE, related_name='items')`): Parent RFQ.
  - `item` (`ForeignKey(InventoryItem, on_delete=models.PROTECT, related_name='rfq_items')`): Catalog SKU.
  - `requisition_item` (`ForeignKey(PurchaseRequisitionItem, on_delete=models.SET_NULL, null=True, blank=True)`): Traceability link to source requisition line.
  - `target_quantity` (`DecimalField(max_digits=12, decimal_places=4)`): Required quantity.
  - `specifications` (`TextField(blank=True)`): Technical, packaging, or brand specifications.
- **Database Constraints:**
  - `UniqueConstraint(fields=['rfq', 'item'], name='uniq_rfq_line_item')`: Prevents duplicate line items for the same SKU in an RFQ.
  - `CheckConstraint(check=Q(target_quantity__gt=0), name='rfqi_qty_positive')`: Ensures target quantity is strictly positive.

### 2.3 `SupplierQuotation` (`hotel/models.py:1700-1785`)
Stores formal vendor pricing bids, commercial terms, delivery commitments, and landed cost breakdowns.
- **Fields:**
  - `quotation_number` (`CharField(max_length=50, unique=True)`): Internal bid reference (e.g. `SQ-202611-0001`).
  - `supplier_reference` (`CharField(max_length=100, blank=True)`): Vendor's invoice/quote proposal number.
  - `rfq` (`ForeignKey(RequestForQuotation, on_delete=models.CASCADE, related_name='quotations', null=True, blank=True)`): Parent RFQ (null if sole-source).
  - `requisition` (`ForeignKey(PurchaseRequisition, on_delete=models.SET_NULL, null=True, blank=True)`): Direct link when bypassing RFQ for sole-source procurement.
  - `sole_source_justification` (`TextField(blank=True)`): Mandatory explanation when an RFQ is bypassed.
  - `supplier` (`ForeignKey(Supplier, on_delete=models.PROTECT, related_name='quotations')`): Bidding vendor.
  - `quotation_date` (`DateField()`): Date quotation was issued by vendor.
  - `valid_until` (`DateField()`): Quote expiry date. Bids cannot be awarded past this date.
  - `delivery_lead_time_days` (`PositiveIntegerField(default=7)`): Committed delivery lead time.
  - `payment_terms` (`CharField(max_length=100, default='30 Days Net')`): Vendor credit terms.
  - `currency` (`CharField(max_length=3, default='ETB')`): ISO currency code (ETB, USD, EUR, etc.).
  - `exchange_rate` (`DecimalField(max_digits=10, decimal_places=4, default=Decimal('1.0000'))`): Conversion rate to base currency ETB.
  - `subtotal` (`DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))`): Sum of line item amounts.
  - `tax_amount` (`DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))`): Sales tax / VAT.
  - `shipping_and_handling` (`DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))`): Freight charges.
  - `customs_and_duties` (`DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))`): Import duties/tariffs.
  - `total_quoted_amount` (`DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))`): Total in quotation currency.
  - `total_landed_cost_etb` (`DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))`): Complete landed cost in ETB.
  - `status` (`CharField(max_length=25, choices=QUOTATION_STATUS_CHOICES, default='draft')`): State machine: `draft` -> `submitted` -> `under_evaluation` -> `accepted` | `partially_awarded` -> `converted_to_po` | `rejected` | `expired` | `cancelled`.
  - `evaluation_notes` (`TextField(blank=True)`): Committee review commentary.
  - `acceptance_justification` (`TextField(blank=True)`): Mandatory managerial rationale for awarding bid.
  - `rejection_reason` (`TextField(blank=True)`): Explanatory note if rejected.

### 2.4 `SupplierQuotationItem` (`hotel/models.py:1787-1845`)
Line-level bidding details, unit pricing, discounts, and PO conversion traceability.
- **Fields:**
  - `quotation` (`ForeignKey(SupplierQuotation, on_delete=models.CASCADE, related_name='items')`): Parent quotation.
  - `item` (`ForeignKey(InventoryItem, on_delete=models.PROTECT, related_name='quotation_items')`): Catalog SKU.
  - `rfq_item` (`ForeignKey(RequestForQuotationItem, on_delete=models.SET_NULL, null=True, blank=True)`): RFQ line reference.
  - `quoted_quantity` (`DecimalField(max_digits=12, decimal_places=4)`): Quantity offered by vendor.
  - `quoted_unit_price` (`DecimalField(max_digits=12, decimal_places=2)`): Gross unit price.
  - `discount_percentage` (`DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))`): Line discount %.
  - `line_total` (`DecimalField(max_digits=14, decimal_places=2)`): Net line total after discount.
  - `offered_brand_or_spec` (`CharField(max_length=255, blank=True)`): Alternative brand or packaging spec offered.
  - `lead_time_days` (`PositiveIntegerField(default=7)`): Line-specific lead time.
  - `award_status` (`CharField(max_length=20, choices=[('pending', 'Pending'), ('awarded', 'Awarded'), ('rejected', 'Rejected')], default='pending')`): Award state per line.
  - `is_converted_to_po` (`BooleanField(default=False)`): Conversion flag.
  - `converted_purchase_order` (`ForeignKey(PurchaseOrder, on_delete=models.SET_NULL, null=True, blank=True)`): Resulting PO reference.
  - `converted_quantity` (`DecimalField(max_digits=12, decimal_places=4, default=Decimal('0.0000'))`): Quantity transferred to PO.
- **Traceability Link on Purchase Order:**
  - `PurchaseOrder.originating_quotation` (`ForeignKey(SupplierQuotation, on_delete=models.SET_NULL, null=True, blank=True, related_name='converted_purchase_orders')`): Establishes complete backward lineage from final PO to originating vendor quote.

---

## 3. Database Migration Analysis

The Phase 2.1 schema extension is packaged in `hotel/migrations/0047_rfq_and_supplier_quotation_workflow.py`.

### Migration Characteristics:
- **Timestamp:** Generated on 2026-11-03 16:20.
- **Dependency Lineage:** Depends directly on `('hotel', '0046_dual_mode_physical_stocktaking')`.
- **Operations:**
  1. `CreateModel(name='RequestForQuotation')`
  2. `CreateModel(name='RequestForQuotationItem')`
  3. `CreateModel(name='SupplierQuotation')`
  4. `CreateModel(name='SupplierQuotationItem')`
  5. `AddField(model_name='purchaseorder', name='originating_quotation', field=...)`
  6. `AddConstraint(model_name='requestforquotationitem', constraint=UniqueConstraint(...))`
  7. `AddConstraint(model_name='requestforquotationitem', constraint=CheckConstraint(...))`
- **Reversibility & Non-Destructive Nature:**
  - The migration is 100% additive; no existing tables, columns, or foreign keys are removed or altered.
  - Safe rollback can be executed cleanly via `manage.py migrate hotel 0046` without data loss in core modules.
- **Schema Drift Status:**
  - Executing `python manage.py makemigrations --check --dry-run` confirms **No changes detected**. The migration is perfectly synchronized with current model declarations.

---

## 4. Core Services Layer Implementation

The business logic governing RFQs, Supplier Quotations, split-awards, and PO conversions is centralized in `hotel/procurement.py` (lines 741–1386).

### 4.1 Service Functions Deep-Dive

#### 1. `create_request_for_quotation()` (lines 745–858)
- **Signature:** `create_request_for_quotation(title, items_data, requisition_ids=None, is_public_bidding=False, invited_supplier_ids=None, submission_deadline=None, delivery_location_id=None, terms_and_conditions="", user=None)`
- **Concurrency & Validation:**
  - Executes inside `transaction.atomic()`.
  - Requisitions are locked with `select_for_update()` to prevent concurrent modification.
  - Validates that source requisitions are in `approved` status.
  - Computes remaining unsourced quantity per requisition item: queries all prior active RFQ lines (`status != 'cancelled'`) and asserts that `target_quantity <= remaining_unallocated_qty`.
  - Enforces positive quantities and valid delivery locations.
  - Emits immutable `AuditEvent` (`action='rfq_created'`).

#### 2. `publish_request_for_quotation()` (lines 859–898)
- **Signature:** `publish_request_for_quotation(rfq_id, user=None)`
- **Validation:**
  - Asserts RFQ is in `draft` status.
  - Enforces that `submission_deadline` is set strictly in the future.
  - Verifies that the RFQ contains at least one line item.
  - For restricted bidding (`is_public_bidding=False`), verifies that at least one supplier is in `invited_suppliers`.
  - Transitions status: `draft` -> `published`.
  - Emits `AuditEvent` (`action='rfq_published'`).

#### 3. `close_request_for_quotation()` (lines 899–925)
- **Signature:** `close_request_for_quotation(rfq_id, user=None)`
- **Validation:**
  - Asserts RFQ is in `published` status.
  - Concludes bidding window; transitions status: `published` -> `closed`.
  - Emits `AuditEvent` (`action='rfq_closed'`).

#### 4. `calculate_quotation_totals()` (lines 926–958)
- **Signature:** `calculate_quotation_totals(items_data, shipping=0, customs=0, tax=0, exchange_rate=1.0)`
- **Financial Computation:**
  - Uses strictly Python `Decimal` with `ROUND_HALF_UP` precision.
  - Computes line net total: `line_gross = qty * price`, `discount = line_gross * (discount_pct / 100)`, `line_total = line_gross - discount`.
  - Computes subtotal as sum of line totals.
  - Computes total quoted amount: `subtotal + tax + shipping + customs`.
  - Computes ETB landed cost: `total_quoted_amount * exchange_rate`.
  - Returns dictionary of exact Decimal amounts.

#### 5. `submit_supplier_quotation()` (lines 959–1112)
- **Signature:** `submit_supplier_quotation(supplier_id, quotation_date, valid_until, items_data, rfq_id=None, requisition_id=None, sole_source_justification="", ...)`
- **Validation:**
  - Asserts that either `rfq_id` OR (`requisition_id` AND `sole_source_justification`) is provided. Sole-source quotes without justification raise `ValidationError`.
  - Asserts `valid_until >= quotation_date` and in the future.
  - When linked to an RFQ: asserts RFQ is in `published` status and `now() <= rfq.submission_deadline`.
  - For restricted RFQs: verifies supplier is in `rfq.invited_suppliers`.
  - Recalculates all line totals and header amounts via `calculate_quotation_totals()`.
  - Creates `SupplierQuotation` and `SupplierQuotationItem` records.
  - Transitions status to `submitted`. Emits `AuditEvent` (`action='quotation_submitted'`).

#### 6. `evaluate_quotation()` (lines 1113–1151)
- **Signature:** `evaluate_quotation(quotation_id, evaluation_notes="", user=None)`
- **Validation:**
  - Asserts quotation is in `submitted` status.
  - Transitions status: `submitted` -> `under_evaluation`.
  - Records committee evaluation notes and audit trail.

#### 7. `evaluate_and_award_quotations()` (lines 1152–1251)
- **Signature:** `evaluate_and_award_quotations(rfq_id, awards_data, justification, user=None)`
- **Split-Award Logic:**
  - Mandatory requirement: `justification` must be a non-empty string explaining managerial rationale.
  - Auto-expires any quotation whose `valid_until` has passed (`status='expired'`).
  - Iterates over `awards_data` specifying `quotation_item_id` and award decision (`awarded` or `rejected`).
  - Updates item `award_status`.
  - Header status synthesis: If all lines awarded, quotation status becomes `accepted`. If some lines awarded and others rejected/unawarded, status becomes `partially_awarded`. If all lines rejected, status becomes `rejected`.
  - Updates parent RFQ status to `awarded`.
  - Emits `AuditEvent` (`action='quotations_awarded'`).

#### 8. `convert_awarded_quotations_to_purchase_orders()` (lines 1252–1386)
- **Signature:** `convert_awarded_quotations_to_purchase_orders(quotation_ids, user=None)`
- **Multi-PO Conversion & Proration:**
  - Executes inside `transaction.atomic()` with `select_for_update()`.
  - Groups awarded items by vendor (`Supplier`).
  - For each vendor, creates a distinct `PurchaseOrder` with status `draft`.
  - Prorates header charges (shipping, customs, tax) based on each PO's proportion of the total awarded subtotal.
  - Creates `PurchaseOrderItem` records from `SupplierQuotationItem` records.
  - Links `po.originating_quotation = quotation`.
  - Marks quotation items: `is_converted_to_po = True`, `converted_purchase_order = po`, `converted_quantity = item.quoted_quantity`.
  - Transitions quotation status to `converted_to_po`.
  - Emits `AuditEvent` (`action='quotation_converted_to_po'`).

---

## 5. REST API, Serializers & URL Routing

The DRF interface is exposed in `apps/inventory/` and registered in `users/urls.py`.

### 5.1 Serializers (`apps/inventory/serializers.py:1036-1120`)
- **`RequestForQuotationItemSerializer`**: Serializes item SKU, code, unit of measure, target quantity, and specifications.
- **`RequestForQuotationSerializer`**: Serializes header attributes, nested line items (`items`), invited suppliers, and requisition links. Computes read-only fields `items_count` and `quotations_count`.
- **`SupplierQuotationItemSerializer`**: Serializes line item pricing, discount percentage, line total, and PO conversion state.
- **`SupplierQuotationSerializer`**: Full serializer with nested items, vendor details, currency, ETB landed cost, status, and audit timestamps.

### 5.2 ViewSets (`apps/inventory/views.py:1273-1512`)
- **`RequestForQuotationViewSet` (`/api/v1/inventory/procurement/rfqs/`):**
  - Standard actions: `list`, `retrieve`, `create`, `update`, `destroy`.
  - Custom action: `@action(detail=True, methods=['post']) publish` — calls `publish_request_for_quotation()`.
  - Custom action: `@action(detail=True, methods=['post']) close_rfq` — calls `close_request_for_quotation()`.
  - Permissions: `IsAuthenticated`, `IsSupplierOperator`.
- **`SupplierQuotationViewSet` (`/api/v1/inventory/procurement/quotations/`):**
  - Standard actions: `list`, `retrieve`, `create`, `update`, `destroy`.
  - Custom action: `@action(detail=True, methods=['post']) evaluate` — calls `evaluate_quotation()`.
  - Custom action: `@action(detail=False, methods=['post']) award_quotations` — calls `evaluate_and_award_quotations()`.
  - Custom action: `@action(detail=False, methods=['post']) convert_to_po` — calls `convert_awarded_quotations_to_purchase_orders()`.

### 5.3 URL Routing (`apps/inventory/urls.py:43-46`)
Endpoints are cleanly registered on the default router:
- `/api/v1/inventory/procurement/rfqs/` and `/api/v1/inventory/rfqs/`
- `/api/v1/inventory/procurement/quotations/` and `/api/v1/inventory/quotations/`

---

## 6. Verification Evidence & Test Execution Results

All automated test suites were executed cleanly via the virtual environment test runner.

### 6.1 Phase 2.1 Automated Unit Tests
Command executed:
```powershell
.\.venv\Scripts\python.exe manage.py test apps.inventory.tests.test_rfq_quotation_workflow --settings=core.settings_test
```
**Output:**
```
Found 10 test(s).
Creating test database for alias 'default' ('file:memorydb_default?mode=memory&cache=shared')...
System check identified no issues (1 silenced).
..........
----------------------------------------------------------------------
Ran 10 tests in 0.409s

OK
Destroying test database for alias 'default' ('file:memorydb_default?mode=memory&cache=shared')...
```
*Result:* **10/10 PASS**. Zero failures or errors.

#### Verified Test Scenarios:
1. `test_create_rfq_from_approved_requisition`: Validates allocation against approved PR and line item generation.
2. `test_rfq_allocation_exceeding_requisition_balance_rejected`: Validates rejection when RFQ quantity exceeds unallocated PR balance.
3. `test_publish_rfq_with_valid_deadline`: Validates publication transition and deadline enforcement.
4. `test_publish_restricted_rfq_requires_invited_suppliers`: Validates invited supplier requirement for non-public RFQs.
5. `test_submit_quotation_for_published_rfq`: Validates quotation intake and landed cost calculation.
6. `test_submit_quotation_after_deadline_rejected`: Validates bidding window cutoff.
7. `test_submit_quotation_sole_source_requires_justification`: Validates mandatory sole-source justification rule.
8. `test_evaluate_and_award_quotations_split_award`: Validates line-level split awarding across multiple vendors.
9. `test_award_quotations_requires_justification`: Validates managerial justification requirement for bid awards.
10. `test_convert_awarded_quotation_to_purchase_order`: Validates atomic PO generation, proration of header costs, and originating quotation foreign key binding.

### 6.2 Procurement 3-Way Match & Requisition Suite
Command executed:
```powershell
.\.venv\Scripts\python.exe manage.py test apps.inventory.tests.test_procurement_management --settings=core.settings_test
```
*Result:* **12/12 PASS** in 0.728s. Covers multi-tier PR approval, GRN receiving, interim GRNI accrual (Dr 1300 / Cr 2010), 3-way invoice matching, and PPV variance posting (Account 5040).

### 6.3 System Health & Migration Drift Checks
- **System Check:** `.\.venv\Scripts\python.exe manage.py check --settings=core.settings_test`  
  *Result:* `System check identified no issues (1 silenced).` (Exit code 0).
- **Migration Drift:** `.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run --settings=core.settings_test`  
  *Result:* `No changes detected.` (Exit code 0).

### 6.4 Verification of Strict Phase Separation
Inspection of the frontend codebase confirmed that `hotel-frontend/src` contains **zero RFQ or supplier quotation UI components**. Phase 2.2 has not been started, strictly honoring the non-negotiable phase gate.

---

## 7. Resolution of Verification Gates

All empirical and quality verification activities have been satisfied and documented in `docs/PHASE_2_1_FINAL_ACCEPTANCE_EVIDENCE.md`:

1. **PostgreSQL 16 Staging Concurrency Execution:**
   - *Status:* **VERIFIED PASS (100%)**.
   - *Result:* Executed multi-threaded simultaneous allocation tests against PostgreSQL 16.12 (`hotel_erp_staging`) using separate connections. Verified that row locking (`select_for_update`) strictly enforced aggregate allocation limits and atomic transaction rollback.
2. **Dedicated Independent Quality Control (QC) Audit:**
   - *Status:* **VERIFIED PASS WITH NON-CRITICAL OBSERVATIONS**.
   - *Result:* Independent QC Agent (`auditor_qc_phase21`) evaluated the implementation across 11 engineering dimensions in `.agents/teamwork/auditor_qc_phase21/handoff.md`. Both observations (API permissions and PostgreSQL concurrency) are reconciled.
3. **Formal Owner Acceptance Gate:**
   - *Status:* **SUBMITTED FOR OWNER ACCEPTANCE**.
   - *Result:* Comprehensive evidence report authored at `docs/PHASE_2_1_FINAL_ACCEPTANCE_EVIDENCE.md` and submitted for Owner review.

---

## 8. Conclusion & Recommendation

The Phase 2.1 backend implementation for RFQs and Supplier Quotations is **structurally sound, thoroughly tested, concurrency-verified on PostgreSQL 16, and compliant with all architectural and financial invariants**.

**Formal Recommendation:**  
**ACCEPT PHASE 2.1** and issue Owner Authorization to proceed with Phase 2.2 (Procurement Operational Frontend) in React 19.
