# Handoff Report: Procurement ViewSet RBAC Architecture (DEF-01)

**Agent:** Explorer 1 (`explorer_m1_it3_1`)  
**Mission:** Milestone 1 Iteration 3: Procurement ViewSet RBAC Explorer  
**Target Backend Files:** `apps/inventory/views.py`, `users/permissions.py`  
**Date:** 2026-11-09T18:46:00Z  

---

## 1. Observation

### 1.1 Current ViewSet Permission Declarations in `apps/inventory/views.py`
Direct inspection of `apps/inventory/views.py` via AST inspection (`scratch/audit_viewsets.py`) and source verification confirmed the exact permission configuration across all inventory and procurement viewsets:

```python
# apps/inventory/views.py:696-699
class ProcurementApprovalPolicyViewSet(viewsets.ModelViewSet):
    queryset = ProcurementApprovalPolicy.objects.prefetch_related("tiers").order_by("-is_active", "name")
    serializer_class = ProcurementApprovalPolicySerializer
    permission_classes = [IsInventoryManager]

# apps/inventory/views.py:701-708
class PurchaseRequisitionViewSet(viewsets.ModelViewSet):
    queryset = (
        PurchaseRequisition.objects.select_related("requested_by", "approved_by", "approval_tier")
        .prefetch_related("items__item")
        .order_by("-created_at")
    )
    serializer_class = PurchaseRequisitionSerializer
    permission_classes = [IsAuthenticated]  # <--- DEF-01: NO ROLE CHECK

# apps/inventory/views.py:820-827
class PurchaseOrderViewSet(viewsets.ModelViewSet):
    queryset = (
        PurchaseOrder.objects.select_related("requisition", "supplier", "delivery_location", "issued_by")
        .prefetch_related("items__item", "grns")
        .order_by("-created_at")
    )
    serializer_class = PurchaseOrderSerializer
    permission_classes = [IsAuthenticated]  # <--- DEF-01: NO ROLE CHECK

# apps/inventory/views.py:884-891
class GoodsReceiptNoteViewSet(viewsets.ModelViewSet):
    queryset = (
        GoodsReceiptNote.objects.select_related("purchase_order", "supplier", "location", "received_by", "journal_entry")
        .prefetch_related("items__item", "items__batch")
        .order_by("-created_at")
    )
    serializer_class = GoodsReceiptNoteSerializer
    permission_classes = [IsAuthenticated]  # <--- DEF-01: NO ROLE CHECK

# apps/inventory/views.py:938-945
class SupplierInvoiceViewSet(viewsets.ModelViewSet):
    queryset = (
        SupplierInvoice.objects.select_related("supplier", "purchase_order", "matched_by", "approved_by", "journal_entry")
        .prefetch_related("items__item")
        .order_by("-created_at")
    )
    serializer_class = SupplierInvoiceSerializer
    permission_classes = [IsAuthenticated]  # <--- DEF-01: NO ROLE CHECK

# apps/inventory/views.py:1021-1028
class RequestForQuotationViewSet(viewsets.ModelViewSet):
    queryset = (
        RequestForQuotation.objects.select_related("delivery_location", "created_by")
        .prefetch_related("requisitions", "invited_suppliers", "items__item", "quotations")
        .order_by("-created_at")
    )
    serializer_class = RequestForQuotationSerializer
    permission_classes = [IsAuthenticated]  # <--- DEF-01: NO ROLE CHECK

# apps/inventory/views.py:1117-1124
class SupplierQuotationViewSet(viewsets.ModelViewSet):
    queryset = (
        SupplierQuotation.objects.select_related("supplier", "rfq", "requisition", "evaluated_by", "accepted_by")
        .prefetch_related("items__item", "items__converted_purchase_order", "purchase_orders")
        .order_by("-created_at")
    )
    serializer_class = SupplierQuotationSerializer
    permission_classes = [IsAuthenticated]  # <--- DEF-01: NO ROLE CHECK
```

### 1.2 ViewSet Permissions Summary Matrix
| # | ViewSet | Route Mount (`apps/inventory/urls.py`) | Declared `permission_classes` | Role Gating Status |
|---|---|---|---|---|
| 1 | `ProcurementApprovalPolicyViewSet` | `/procurement/policies/` | `[IsInventoryManager]` | Gated to `admin`, `inventory`, `hotel_manager` |
| 2 | `PurchaseRequisitionViewSet` | `/procurement/requisitions/` | `[IsAuthenticated]` | **UNPROTECTED** (HTTP 200 to all roles) |
| 3 | `PurchaseOrderViewSet` | `/procurement/orders/` | `[IsAuthenticated]` | **UNPROTECTED** (HTTP 200 to all roles) |
| 4 | `GoodsReceiptNoteViewSet` | `/procurement/grns/` | `[IsAuthenticated]` | **UNPROTECTED** (HTTP 200 to all roles) |
| 5 | `SupplierInvoiceViewSet` | `/procurement/invoices/` | `[IsAuthenticated]` | **UNPROTECTED** (HTTP 200 to all roles) |
| 6 | `RequestForQuotationViewSet` | `/procurement/rfqs/` | `[IsAuthenticated]` | **UNPROTECTED** (HTTP 200 to all roles) |
| 7 | `SupplierQuotationViewSet` | `/procurement/quotations/` | `[IsAuthenticated]` | **UNPROTECTED** (HTTP 200 to all roles) |

### 1.3 Existing Permissions in `users/permissions.py`
Inspection of `users/permissions.py` (lines 92–146) revealed that procurement permission classes were already defined in Iteration 1:

```python
# users/permissions.py:92-96
class IsInventoryManager(BasePermission):
    message = "Inventory manager or hotel administrator access is required."
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_active and (user.is_superuser or getattr(user, "role", "") in {"admin", "inventory", "hotel_manager"}))

# users/permissions.py:99-103
class IsProcurementOperator(BasePermission):
    message = "Procurement officer, inventory manager, or hotel administrator access is required."
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_active and (user.is_superuser or getattr(user, "role", "") in {"admin", "inventory", "hotel_manager"}))

# users/permissions.py:106-110
class IsProcurementOrFinanceOperator(BasePermission):
    message = "Procurement, finance, or hotel administrator access is required."
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_active and (user.is_superuser or getattr(user, "role", "") in {"admin", "inventory", "finance", "hotel_manager"}))

# users/permissions.py:131-146
class IsSupplierOperator(BasePermission):
    """Allow active inventory staff, finance staff, or hotel administrators access to suppliers."""
    message = "Inventory, finance, or hotel administrator access is required."
    def has_permission(self, request, view):
        user = request.user
        return bool(
            user and user.is_authenticated and user.is_active and
            (user.is_superuser or user.role in {"admin", "inventory", "finance"})
        )
```
**Key Observation:** `IsProcurementOperator` and `IsProcurementOrFinanceOperator` are already defined and imported into `apps/inventory/views.py:95-96`. However, they were never applied to the viewsets, leaving 6 out of 7 procurement viewsets using `[IsAuthenticated]`.  
Furthermore, `IsSupplierOperator` (line 144) currently omits `hotel_manager`.

### 1.4 Unprotected Custom Action Endpoints
The following mutating custom actions currently inherit `[IsAuthenticated]` and lack action-level role guards:

| ViewSet | Action | Route | Mutation / Impact |
|---|---|---|---|
| `PurchaseOrderViewSet` | `receive_grn` | `POST /procurement/orders/<id>/receive-grn/` | Creates GRN, seeds stock, increments batches, posts General Ledger journal entries (Dr 1300 / Cr 2010). |
| `PurchaseRequisitionViewSet` | `convert_to_po` | `POST /procurement/requisitions/<id>/convert-to-po/` | Issues legally binding Purchase Order from requisition. |
| `PurchaseRequisitionViewSet` | `approve` | `POST /procurement/requisitions/<id>/approve/` | Approves requisition (service validates tier role + SoD, but API boundary has no initial filter). |
| `PurchaseRequisitionViewSet` | `reject` | `POST /procurement/requisitions/<id>/reject/` | Marks requisition rejected; no role check at view boundary. |
| `SupplierInvoiceViewSet` | `approve` | `POST /procurement/invoices/<id>/approve/` | Posts settlement General Ledger journal entry: Dr 2010 (GRNI) / Cr 2000 (Accounts Payable) / Dr/Cr 5040 (PPV). |
| `SupplierInvoiceViewSet` | `match_and_record` | `POST /procurement/invoices/match-and-record/` | Records invoice against PO/GRN with price variance calculation. |
| `RequestForQuotationViewSet` | `publish` | `POST /procurement/rfqs/<id>/publish/` | Publishes RFQ to invited suppliers. |
| `RequestForQuotationViewSet` | `close_rfq` | `POST /procurement/rfqs/<id>/close/` | Closes bidding window. |
| `SupplierQuotationViewSet` | `award_quotations` | `POST /procurement/quotations/award/` | Accepts vendor quotations, marks rejected quotes. |
| `SupplierQuotationViewSet` | `convert_to_po` | `POST /procurement/quotations/convert-to-po/` | Issues Purchase Orders from awarded bids. |

### 1.5 Automated Regression Test Baseline (`test_procurement_management.py`)
Execution of the test suite against isolated PostgreSQL test database (`test_hotel_erp_staging`):
- Command: `.venv\Scripts\python.exe manage.py test apps.inventory.tests.test_procurement_management --noinput`
- Result: `Ran 12 tests in 63.948s. OK.`
- Critical Observation in `test_12_procurement_lifecycle_full_e2e_api_journey` (lines 608–681):
  ```python
  # 1. API: Requisition creation by chef (kitchen)
  self.client.force_authenticate(user=self.chef)  # role="kitchen"
  req_res = self.client.post("/api/users/procurement/requisitions/", {
      "department": "kitchen",
      "delivery_location": self.main_store.id,
      "items": [{"item_id": item.id, "quantity_requested": 10, "estimated_unit_cost": "150.00"}],
  }, format="json")
  self.assertEqual(req_res.status_code, status.HTTP_201_CREATED)  # <--- Expects 201 Created for kitchen staff!
  ```
  If `PurchaseRequisitionViewSet` completely blocks the `kitchen` role with `HTTP 403 Forbidden`, this existing regression test will immediately fail.

---

## 2. Logic Chain

1. **Premise 1 (Policy Requirement):** The hotel operates on a Single-Tenant / Single-Hotel ERP architecture (`PROJECT.md`). General procurement operations (RFQs, vendor quotations, awards, purchase order issuance, loading dock goods receipt, and accounts payable invoice matching) are centralized functions restricted exclusively to `admin`, `superuser`, `hotel_manager`, `inventory`, and `finance`.
2. **Premise 2 (API Vulnerability):** Currently, 6 out of 7 procurement viewsets enforce only `permission_classes = [IsAuthenticated]`. Consequently, unprivileged departmental staff (`kitchen`, `bar`, `waiter`, `cashier`, `reception`, `housekeeping`, `customer`) receive `HTTP 200 OK` on list and retrieve endpoints and can invoke mutating actions (`receive-grn`, `convert-to-po`, `match-and-record`, `approve`).
3. **Premise 3 (Separation of Duties & Role Segregation):**
   - Dock Receiving (`receive_grn` on `PurchaseOrderViewSet` and `create` on `GoodsReceiptNoteViewSet`): Physically checking in goods and seeding inventory batches belongs strictly to warehouse/inventory staff (`inventory`, `hotel_manager`, `admin`). `finance` must NOT create receiving notes or seed stock batches.
   - Financial Settlement Approval (`approve` on `SupplierInvoiceViewSet`): Posting liabilities to Accounts Payable (Account 2000) and clearing GRNI (Account 2010) is a financial accounting event. To enforce Separation of Duties (SoD), the inventory storekeeper who received the goods must NOT approve payment to the supplier. This action belongs exclusively to `finance`, `admin`, and `superuser`.
   - PO Conversion & Awards: Converting requisitions or quotations to binding POs belongs to procurement operators (`inventory`, `hotel_manager`, `admin`).
4. **Premise 4 (PurchaseRequisition Architectural Alternatives):**
   - *Option A (Fully Centralized Requisitions):* Gate `PurchaseRequisitionViewSet` strictly to `IsProcurementOrFinanceOperator`. Departmental staff cannot submit requisitions via API. However, this causes immediate regression test failure in `test_procurement_management.py:609` (where `self.chef` submits a kitchen requisition).
   - *Option B (Department-Scoped Requisition Submission — Recommended):* Allow internal operational department heads/staff (`kitchen`, `bar`, `housekeeping`) to submit requisitions, but enforce row-level scoping in `get_queryset()` so they can only list/retrieve their own department's requisitions (`requested_by=user` or `department=role`). Block external customers (`customer`), line staff (`waiter`, `cashier`), and restrict downstream actions (`convert_to_po`) strictly to `IsProcurementOperator`.
5. **Conclusion:** Implementing role-based permission classes and action-level overrides across the 7 viewsets eliminates DEF-01, protects financial and stock integrity, enforces Separation of Duties, and maintains full test suite compatibility.

---

## 3. Caveats

1. **Staging Database Mutation Warning:** When executing ad-hoc verification scripts via Python, all verification calls must run within transaction atomic rollbacks (`with transaction.atomic(): ... transaction.set_rollback(True)`) or isolated Django test runners to avoid recurring DEF-02 staging database mutations.
2. **Customer / Supplier Role Identity (DEF-06):** External suppliers authenticate with `role="customer"` and interact via supplier portal endpoints (`/api/users/suppliers/...`). They must be strictly blocked (`HTTP 403 Forbidden`) from all internal hotel procurement viewsets.
3. **Frontend Compatibility:** The frontend `hotel-frontend/src/pages/procurement/ProcurementCenter.jsx` calls `GET /procurement/requisitions/`, `rfqs/`, `quotations/`, `orders/`, and `invoices/` when rendering KPIs. The permission class `IsProcurementOrFinanceOperator` ensures that both `inventory` and `finance` users can load the dashboard without broken KPI cards.

---

## 4. Conclusion & Concrete Implementation Proposal

### 4.1 Permission Classes to Define / Update in `users/permissions.py`

#### 4.1.1 Update `IsSupplierOperator` to include `hotel_manager`
```python
class IsSupplierOperator(BasePermission):
    """Allow active inventory staff, finance staff, hotel managers, or hotel administrators access to suppliers."""

    message = "Inventory, finance, or hotel administrator access is required."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and (
                user.is_superuser
                or getattr(user, "role", "") in {"admin", "inventory", "finance", "hotel_manager"}
            )
        )
```

#### 4.1.2 Define `IsPurchaseRequisitionStaff` (for Option B — Department-Scoped Requisitions)
```python
class IsPurchaseRequisitionStaff(BasePermission):
    """
    Allow administrative and procurement staff full access.
    Allow active operational departmental staff (kitchen, bar, housekeeping) to submit and view scoped requisitions.
    Strictly deny external customers (customer role) and dining line staff (waiter, cashier).
    """

    message = "Staff procurement requisition access is required."

    ALLOWED_DEPARTMENTAL_ROLES = {
        "admin",
        "hotel_manager",
        "inventory",
        "finance",
        "kitchen",
        "bar",
        "housekeeping",
    }

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated and user.is_active):
            return False
        if user.is_superuser:
            return True
        return getattr(user, "role", "") in self.ALLOWED_DEPARTMENTAL_ROLES
```

---

### 4.2 Concrete Code Proposals for `apps/inventory/views.py`

#### 4.2.1 Imports Update
Ensure `users.permissions` imports include:
```python
from users.permissions import (
    HasStocktakeLocationPermission,
    IsAdminOrReadOnly,
    IsBatchOperator,
    IsFinanceStaff,
    IsHotelAdmin,
    IsInventoryManager,
    IsProcurementOperator,
    IsProcurementOrFinanceOperator,
    IsPurchaseRequisitionStaff,  # New
    IsSupplierOperator,
)
```

---

#### 4.2.2 ViewSet 1: `ProcurementApprovalPolicyViewSet`
**Current:** `permission_classes = [IsInventoryManager]`  
**Proposal:** Retain `permission_classes = [IsInventoryManager]` (or `[IsProcurementOperator]`).  
- Gated to: `admin`, `superuser`, `hotel_manager`, `inventory`.
- Denied: All departmental staff and customers receive `HTTP 403 Forbidden`.

---

#### 4.2.3 ViewSet 2: `PurchaseOrderViewSet`
**Current:** `permission_classes = [IsAuthenticated]`  
**Proposal:**
```python
class PurchaseOrderViewSet(viewsets.ModelViewSet):
    queryset = (
        PurchaseOrder.objects.select_related("requisition", "supplier", "delivery_location", "issued_by")
        .prefetch_related("items__item", "grns")
        .order_by("-created_at")
    )
    serializer_class = PurchaseOrderSerializer
    permission_classes = [IsProcurementOrFinanceOperator]

    def get_queryset(self):
        qs = super().get_queryset()
        supplier_id = self.request.query_params.get("supplier")
        status_param = self.request.query_params.get("status")
        po_number = self.request.query_params.get("po_number")
        if supplier_id:
            qs = qs.filter(supplier_id=supplier_id)
        if status_param:
            qs = qs.filter(status=status_param)
        if po_number:
            qs = qs.filter(po_number__icontains=po_number)
        return qs

    def create(self, request, *args, **kwargs):
        # Only procurement officers / managers can create purchase orders
        user = request.user
        if not (user.is_superuser or getattr(user, "role", "") in {"admin", "hotel_manager", "inventory"}):
            return Response(
                {"error": "Only inventory and procurement managers can create purchase orders."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        user = request.user
        if not (user.is_superuser or getattr(user, "role", "") in {"admin", "hotel_manager", "inventory"}):
            return Response(
                {"error": "Only inventory and procurement managers can modify purchase orders."},
                status=status.HTTP_403_FORBIDDEN,
            )
        po = self.get_object()
        if po.status not in ("draft", "issued"):
            return Response(
                {"error": f"Cannot modify purchase order #{po.po_number} in '{po.status}' status."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        return Response(
            {"error": "Purchase orders cannot be deleted; cancel instead."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    @action(detail=True, methods=["post"], url_path="receive-grn", permission_classes=[IsProcurementOperator])
    def receive_grn(self, request, pk=None):
        delivery_note = request.data.get("delivery_note_number", "")
        location_id = request.data.get("location")
        receipt_items = request.data.get("items", [])
        notes = request.data.get("notes", "")

        if not receipt_items:
            return Response({"error": "Receipt items are required for goods receipt."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            grn = receive_goods_receipt_note(
                purchase_order_id=pk,
                receiver=request.user,
                delivery_note_number=delivery_note,
                location_id=location_id,
                receipt_items=receipt_items,
                notes=notes,
            )
            serializer = GoodsReceiptNoteSerializer(grn)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            msg = e.message if hasattr(e, "message") else ("; ".join(e.messages) if hasattr(e, "messages") else str(e))
            return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
```
- **Access Rule:** Departmental staff (`kitchen`, `waiter`, etc.) receive `HTTP 403 Forbidden` across all routes. `finance` receives `HTTP 200 OK` on `list`/`retrieve`, but `HTTP 403 Forbidden` on `create`, `update`, and `receive-grn`.

---

#### 4.2.4 ViewSet 3: `GoodsReceiptNoteViewSet`
**Current:** `permission_classes = [IsAuthenticated]`  
**Proposal:**
```python
class GoodsReceiptNoteViewSet(viewsets.ModelViewSet):
    queryset = (
        GoodsReceiptNote.objects.select_related("purchase_order", "supplier", "location", "received_by", "journal_entry")
        .prefetch_related("items__item", "items__batch")
        .order_by("-created_at")
    )
    serializer_class = GoodsReceiptNoteSerializer
    permission_classes = [IsProcurementOrFinanceOperator]

    def get_queryset(self):
        qs = super().get_queryset()
        po_id = self.request.query_params.get("purchase_order")
        supplier_id = self.request.query_params.get("supplier")
        location_id = self.request.query_params.get("location")
        status_param = self.request.query_params.get("status")
        if po_id:
            qs = qs.filter(purchase_order_id=po_id)
        if supplier_id:
            qs = qs.filter(supplier_id=supplier_id)
        if location_id:
            qs = qs.filter(location_id=location_id)
        if status_param:
            qs = qs.filter(status=status_param)
        return qs

    def create(self, request, *args, **kwargs):
        # Dock receiving restricted strictly to inventory, hotel_manager, and admin
        user = request.user
        if not (user.is_superuser or getattr(user, "role", "") in {"admin", "hotel_manager", "inventory"}):
            return Response(
                {"error": "Goods receiving is restricted to warehouse and inventory staff."},
                status=status.HTTP_403_FORBIDDEN,
            )
        po_id = request.data.get("purchase_order")
        delivery_note = request.data.get("delivery_note_number", "")
        location_id = request.data.get("location")
        receipt_items = request.data.get("items", [])
        notes = request.data.get("notes", "")

        if not po_id:
            return Response({"error": "purchase_order is required."}, status=status.HTTP_400_BAD_REQUEST)
        if not receipt_items:
            return Response({"error": "Receipt items are required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            grn = receive_goods_receipt_note(
                purchase_order_id=po_id,
                receiver=request.user,
                delivery_note_number=delivery_note,
                location_id=location_id,
                receipt_items=receipt_items,
                notes=notes,
            )
            serializer = self.get_serializer(grn)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            msg = e.message if hasattr(e, "message") else ("; ".join(e.messages) if hasattr(e, "messages") else str(e))
            return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
```
- **Access Rule:** Departmental staff receive `HTTP 403 Forbidden`. Finance receives read access to inspect GRNs during invoice matching. Dock physical creation is reserved for `inventory`, `hotel_manager`, `admin`.

---

#### 4.2.5 ViewSet 4: `SupplierInvoiceViewSet`
**Current:** `permission_classes = [IsAuthenticated]`  
**Proposal:**
```python
class SupplierInvoiceViewSet(viewsets.ModelViewSet):
    queryset = (
        SupplierInvoice.objects.select_related("supplier", "purchase_order", "matched_by", "approved_by", "journal_entry")
        .prefetch_related("items__item")
        .order_by("-created_at")
    )
    serializer_class = SupplierInvoiceSerializer
    permission_classes = [IsProcurementOrFinanceOperator]

    def get_queryset(self):
        qs = super().get_queryset()
        po_id = self.request.query_params.get("purchase_order")
        supplier_id = self.request.query_params.get("supplier")
        match_status_param = self.request.query_params.get("match_status")
        is_paid = self.request.query_params.get("is_paid")
        if po_id:
            qs = qs.filter(purchase_order_id=po_id)
        if supplier_id:
            qs = qs.filter(supplier_id=supplier_id)
        if match_status_param:
            qs = qs.filter(match_status=match_status_param)
        if is_paid is not None:
            qs = qs.filter(is_paid=is_paid.lower() in ("true", "1"))
        return qs

    def create(self, request, *args, **kwargs):
        po_id = request.data.get("purchase_order")
        vendor_inv_num = request.data.get("vendor_invoice_number")
        inv_date = request.data.get("invoice_date")
        due_date = request.data.get("due_date")
        billed_items = request.data.get("items", [])
        tax_amount = request.data.get("tax_amount", Decimal("0.00"))
        notes = request.data.get("notes", "")

        if not po_id or not vendor_inv_num or not inv_date or not billed_items:
            return Response(
                {"error": "purchase_order, vendor_invoice_number, invoice_date, and items are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            inv = match_and_record_supplier_invoice(
                purchase_order_id=po_id,
                vendor_invoice_number=vendor_inv_num,
                invoice_date=inv_date,
                due_date=due_date,
                billed_items=billed_items,
                matched_by=request.user,
                tax_amount=tax_amount,
                notes=notes,
            )
            serializer = self.get_serializer(inv)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            msg = e.message if hasattr(e, "message") else ("; ".join(e.messages) if hasattr(e, "messages") else str(e))
            return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["post"], url_path="match-and-record")
    def match_and_record(self, request):
        return self.create(request)

    @action(detail=True, methods=["post"], url_path="approve", permission_classes=[IsFinanceStaff])
    def approve(self, request, pk=None):
        override_variance = request.data.get("override_variance", False)
        if isinstance(override_variance, str):
            override_variance = override_variance.lower() in ("true", "1")
        justification = request.data.get("variance_justification", "")
        try:
            inv = approve_supplier_invoice(
                invoice_id=pk,
                approver=request.user,
                override_variance=override_variance,
                variance_justification=justification,
            )
            return Response(self.get_serializer(inv).data, status=status.HTTP_200_OK)
        except ValidationError as e:
            msg = e.message if hasattr(e, "message") else ("; ".join(e.messages) if hasattr(e, "messages") else str(e))
            return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
```
- **Access Rule:** Departmental staff receive `HTTP 403 Forbidden`. Crucially, `@action(..., permission_classes=[IsFinanceStaff])` on `approve` ensures that `inventory` staff cannot approve invoices or trigger GL settlement postings (SoD).

---

#### 4.2.6 ViewSet 5: `RequestForQuotationViewSet`
**Current:** `permission_classes = [IsAuthenticated]`  
**Proposal:**
```python
class RequestForQuotationViewSet(viewsets.ModelViewSet):
    queryset = (
        RequestForQuotation.objects.select_related("delivery_location", "created_by")
        .prefetch_related("requisitions", "invited_suppliers", "items__item", "quotations")
        .order_by("-created_at")
    )
    serializer_class = RequestForQuotationSerializer
    permission_classes = [IsProcurementOrFinanceOperator]

    def create(self, request, *args, **kwargs):
        user = request.user
        if not (user.is_superuser or getattr(user, "role", "") in {"admin", "hotel_manager", "inventory"}):
            return Response({"error": "Only procurement officers can create RFQs."}, status=status.HTTP_403_FORBIDDEN)
        # ... standard creation logic ...

    @action(detail=True, methods=["post"], url_path="publish", permission_classes=[IsProcurementOperator])
    def publish(self, request, pk=None):
        # ...
    
    @action(detail=True, methods=["post"], url_path="close", permission_classes=[IsProcurementOperator])
    def close_rfq(self, request, pk=None):
        # ...
```
- **Access Rule:** Departmental staff receive `HTTP 403 Forbidden`. Finance can inspect RFQs. Only `inventory`, `hotel_manager`, `admin` can create, publish, or close RFQs.

---

#### 4.2.7 ViewSet 6: `SupplierQuotationViewSet`
**Current:** `permission_classes = [IsAuthenticated]`  
**Proposal:**
```python
class SupplierQuotationViewSet(viewsets.ModelViewSet):
    queryset = (
        SupplierQuotation.objects.select_related("supplier", "rfq", "requisition", "evaluated_by", "accepted_by")
        .prefetch_related("items__item", "items__converted_purchase_order", "purchase_orders")
        .order_by("-created_at")
    )
    serializer_class = SupplierQuotationSerializer
    permission_classes = [IsProcurementOrFinanceOperator]

    def create(self, request, *args, **kwargs):
        user = request.user
        if not (user.is_superuser or getattr(user, "role", "") in {"admin", "hotel_manager", "inventory"}):
            return Response({"error": "Only procurement officers can log supplier quotations."}, status=status.HTTP_403_FORBIDDEN)
        # ... standard creation logic ...

    @action(detail=True, methods=["post"], url_path="evaluate", permission_classes=[IsProcurementOperator])
    def evaluate(self, request, pk=None):
        # ...

    @action(detail=False, methods=["post"], url_path="award", permission_classes=[IsProcurementOperator])
    def award_quotations(self, request):
        # ...

    @action(detail=False, methods=["post"], url_path="convert-to-po", permission_classes=[IsProcurementOperator])
    def convert_to_po(self, request):
        # ...
```
- **Access Rule:** Departmental staff receive `HTTP 403 Forbidden`. Finance has read access. Evaluation, contract awards, and conversion to POs are strictly restricted to `IsProcurementOperator`.

---

#### 4.2.8 ViewSet 7: `PurchaseRequisitionViewSet` — Comparison of Options A & B

##### Option A: Fully Centralized Procurement (All Staff Blocked)
```python
class PurchaseRequisitionViewSet(viewsets.ModelViewSet):
    queryset = (
        PurchaseRequisition.objects.select_related("requested_by", "approved_by", "approval_tier")
        .prefetch_related("items__item")
        .order_by("-created_at")
    )
    serializer_class = PurchaseRequisitionSerializer
    permission_classes = [IsProcurementOrFinanceOperator]

    @action(detail=True, methods=["post"], url_path="convert-to-po", permission_classes=[IsProcurementOperator])
    def convert_to_po(self, request, pk=None):
        # ...
```
- **Evaluation:**
  - *Pros:* Simple, uniform policy.
  - *Cons:* Breaks regression test `test_procurement_management.py:609` (`self.chef` receives 403 instead of 201). Requires test fixture update.

##### Option B: Department-Scoped Requisition Submission (Recommended)
```python
class PurchaseRequisitionViewSet(viewsets.ModelViewSet):
    queryset = (
        PurchaseRequisition.objects.select_related("requested_by", "approved_by", "approval_tier")
        .prefetch_related("items__item")
        .order_by("-created_at")
    )
    serializer_class = PurchaseRequisitionSerializer
    permission_classes = [IsPurchaseRequisitionStaff]

    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset()

        # Privileged staff: global property-wide visibility
        if user.is_superuser or getattr(user, "role", "") in {"admin", "hotel_manager", "inventory", "finance"}:
            status_param = self.request.query_params.get("status")
            dept = self.request.query_params.get("department")
            if status_param:
                qs = qs.filter(status=status_param)
            if dept:
                qs = qs.filter(department=dept)
            return qs

        # Departmental staff (kitchen, bar, housekeeping): strictly row-scoped
        user_role = getattr(user, "role", "").lower()
        from django.db.models import Q
        return qs.filter(Q(requested_by=user) | Q(department__iexact=user_role))

    def create(self, request, *args, **kwargs):
        user = request.user
        user_role = getattr(user, "role", "").lower()
        department = request.data.get("department")
        delivery_location = request.data.get("delivery_location")
        items = request.data.get("items", [])
        notes = request.data.get("notes", "")

        is_privileged = user.is_superuser or user_role in {"admin", "hotel_manager", "inventory"}

        # Departmental validation: non-privileged users cannot request for another department
        if not is_privileged:
            if department and department.lower() != user_role:
                return Response(
                    {"error": f"Staff with role '{user_role}' cannot submit requisitions for department '{department}'."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            if not department:
                department = user_role

        if not department:
            return Response({"error": "Department is required."}, status=status.HTTP_400_BAD_REQUEST)
        if not items:
            return Response({"error": "Requisition items are required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            req = request_purchase_requisition(
                requester=request.user,
                department=department,
                delivery_location=delivery_location,
                items=items,
                notes=notes,
            )
            serializer = self.get_serializer(req)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            msg = e.message if hasattr(e, "message") else ("; ".join(e.messages) if hasattr(e, "messages") else str(e))
            return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], url_path="convert-to-po", permission_classes=[IsProcurementOperator])
    def convert_to_po(self, request, pk=None):
        # Strictly restricted to IsProcurementOperator (admin, hotel_manager, inventory)
        # Departmental staff receive HTTP 403 Forbidden
        # ... standard convert_to_po logic ...

    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        # approve_purchase_requisition enforces Tier roles & Separation of Duties (no self-approval)
        req_obj = self.get_object()
        notes = request.data.get("notes", "")
        try:
            req = approve_purchase_requisition(requisition_id=pk, approver=request.user, notes=notes)
            return Response(self.get_serializer(req).data, status=status.HTTP_200_OK)
        except ValidationError as e:
            msg = e.message if hasattr(e, "message") else ("; ".join(e.messages) if hasattr(e, "messages") else str(e))
            return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionDenied as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
```
- **Evaluation:** Option B provides the optimal balance: it prevents departmental staff from viewing or tampering with other departments' requests, blocks conversion to POs, blocks customers and line staff, and preserves 100% backward compatibility with `test_procurement_management.py`.

---

### 4.3 Action-Level Protection Matrix

| ViewSet | Endpoint / Action | Base Permission | Action Permission | Roles Allowed (`200`/`201`) | Roles Blocked (`403 Forbidden`) |
|---|---|---|---|---|---|
| `ProcurementApprovalPolicyViewSet` | `GET/POST/PUT/DELETE` | `IsInventoryManager` | Default | `admin`, `superuser`, `hotel_manager`, `inventory` | `finance`, `kitchen`, `bar`, `waiter`, `cashier`, `reception`, `housekeeping`, `customer` |
| `PurchaseOrderViewSet` | `GET /orders/` (list/retrieve) | `IsProcurementOrFinanceOperator` | Default | `admin`, `hotel_manager`, `inventory`, `finance` | `kitchen`, `bar`, `waiter`, `cashier`, `reception`, `housekeeping`, `customer` |
| `PurchaseOrderViewSet` | `POST /orders/` (create) | `IsProcurementOrFinanceOperator` | Role check in method | `admin`, `hotel_manager`, `inventory` | `finance`, and all departmental staff |
| `PurchaseOrderViewSet` | `PUT /orders/<id>/` (update) | `IsProcurementOrFinanceOperator` | Role check in method | `admin`, `hotel_manager`, `inventory` | `finance`, and all departmental staff |
| `PurchaseOrderViewSet` | `POST /orders/<id>/receive-grn/` | `IsProcurementOrFinanceOperator` | `IsProcurementOperator` | `admin`, `hotel_manager`, `inventory` | `finance`, and all departmental staff |
| `GoodsReceiptNoteViewSet` | `GET /grns/` (list/retrieve) | `IsProcurementOrFinanceOperator` | Default | `admin`, `hotel_manager`, `inventory`, `finance` | `kitchen`, `bar`, `waiter`, `cashier`, `reception`, `housekeeping`, `customer` |
| `GoodsReceiptNoteViewSet` | `POST /grns/` (create) | `IsProcurementOrFinanceOperator` | Role check in method | `admin`, `hotel_manager`, `inventory` | `finance`, and all departmental staff |
| `SupplierInvoiceViewSet` | `GET /invoices/` (list/retrieve) | `IsProcurementOrFinanceOperator` | Default | `admin`, `hotel_manager`, `inventory`, `finance` | `kitchen`, `bar`, `waiter`, `cashier`, `reception`, `housekeeping`, `customer` |
| `SupplierInvoiceViewSet` | `POST /invoices/` & `match-and-record` | `IsProcurementOrFinanceOperator` | Default | `admin`, `hotel_manager`, `inventory`, `finance` | All departmental staff |
| `SupplierInvoiceViewSet` | `POST /invoices/<id>/approve/` | `IsProcurementOrFinanceOperator` | `IsFinanceStaff` | `admin`, `superuser`, `finance` | `inventory` (SoD enforcement), and all departmental staff |
| `RequestForQuotationViewSet` | `GET /rfqs/` (list/retrieve) | `IsProcurementOrFinanceOperator` | Default | `admin`, `hotel_manager`, `inventory`, `finance` | All departmental staff |
| `RequestForQuotationViewSet` | `POST /rfqs/` (create) | `IsProcurementOrFinanceOperator` | Role check in method | `admin`, `hotel_manager`, `inventory` | `finance`, and all departmental staff |
| `RequestForQuotationViewSet` | `POST /rfqs/<id>/publish/` | `IsProcurementOrFinanceOperator` | `IsProcurementOperator` | `admin`, `hotel_manager`, `inventory` | `finance`, and all departmental staff |
| `RequestForQuotationViewSet` | `POST /rfqs/<id>/close/` | `IsProcurementOrFinanceOperator` | `IsProcurementOperator` | `admin`, `hotel_manager`, `inventory` | `finance`, and all departmental staff |
| `SupplierQuotationViewSet` | `GET /quotations/` (list/retrieve) | `IsProcurementOrFinanceOperator` | Default | `admin`, `hotel_manager`, `inventory`, `finance` | All departmental staff |
| `SupplierQuotationViewSet` | `POST /quotations/` (create) | `IsProcurementOrFinanceOperator` | Role check in method | `admin`, `hotel_manager`, `inventory` | `finance`, and all departmental staff |
| `SupplierQuotationViewSet` | `POST /quotations/<id>/evaluate/` | `IsProcurementOrFinanceOperator` | `IsProcurementOperator` | `admin`, `hotel_manager`, `inventory` | `finance`, and all departmental staff |
| `SupplierQuotationViewSet` | `POST /quotations/award/` | `IsProcurementOrFinanceOperator` | `IsProcurementOperator` | `admin`, `hotel_manager`, `inventory` | `finance`, and all departmental staff |
| `SupplierQuotationViewSet` | `POST /quotations/convert-to-po/` | `IsProcurementOrFinanceOperator` | `IsProcurementOperator` | `admin`, `hotel_manager`, `inventory` | `finance`, and all departmental staff |
| `PurchaseRequisitionViewSet` | `GET /requisitions/` (list/retrieve) | `IsPurchaseRequisitionStaff` | Default + row filter in `get_queryset()` | Management/Finance (all), Departmental (own dept only) | `waiter`, `cashier`, `customer` |
| `PurchaseRequisitionViewSet` | `POST /requisitions/` (create) | `IsPurchaseRequisitionStaff` | Role/department check in `create()` | Management (any dept), Departmental (own dept only) | `waiter`, `cashier`, `customer` |
| `PurchaseRequisitionViewSet` | `POST /requisitions/<id>/convert-to-po/` | `IsPurchaseRequisitionStaff` | `IsProcurementOperator` | `admin`, `hotel_manager`, `inventory` | `finance`, and all departmental staff |
| `PurchaseRequisitionViewSet` | `POST /requisitions/<id>/approve/` | `IsPurchaseRequisitionStaff` | Tier logic + SoD | Approver matching tier required role (not requester) | Non-matching tier roles & self-approver |

---

## 5. Verification Method

To verify these RBAC protections once implemented:

1. **Automated Test Suite Verification:**
   ```powershell
   .venv\Scripts\python.exe manage.py test apps.inventory.tests.test_procurement_management --noinput
   .venv\Scripts\python.exe manage.py test apps.inventory.tests.test_rfq_quotation_workflow --noinput
   ```
2. **Dedicated RBAC Denial Test Suite:**
   Create and execute a test asserting `HTTP 403 Forbidden` across each restricted role (`waiter`, `cashier`, `kitchen`, `bar`, `customer`) for each of the 7 viewset routes:
   - `GET /api/users/procurement/orders/` -> `HTTP 403` for waiter/cashier/kitchen
   - `POST /api/users/procurement/orders/<id>/receive-grn/` -> `HTTP 403` for waiter/kitchen/finance
   - `POST /api/users/procurement/invoices/<id>/approve/` -> `HTTP 403` for inventory/kitchen
   - `POST /api/users/procurement/requisitions/<id>/convert-to-po/` -> `HTTP 403` for kitchen/waiter
   - `GET /api/users/procurement/rfqs/` -> `HTTP 403` for waiter/kitchen/customer
   - `GET /api/users/procurement/quotations/` -> `HTTP 403` for waiter/kitchen/customer
3. **Invalidation Conditions:**
   - Any HTTP 200 returned to `waiter`, `cashier`, or `customer` on any procurement endpoint invalidates the fix.
   - Any permission leak allowing `inventory` staff to approve supplier invoices invalidates the Separation of Duties requirement.
   - Any regression causing `test_12_procurement_lifecycle_full_e2e_api_journey` to fail invalidates the implementation.
