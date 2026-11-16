import ast
import re

with open("scratch/recovered_write_4552.py", "r", encoding="utf-8") as f:
    text_4552 = f.read()

with open("scratch/perfect_restored_views.py", "r", encoding="utf-8") as f:
    text_perfect = f.read()

with open("apps/inventory/views.py", "r", encoding="utf-8") as f:
    text_current = f.read()

# Extract full viewsets from text_4552
match_req = re.search(r'class PurchaseRequisitionViewSet\(.*?(?=\nclass |\Z)', text_4552, re.DOTALL)
purchase_req_code = match_req.group(0).strip()

match_po = re.search(r'class PurchaseOrderViewSet\(.*?(?=\nclass |\Z)', text_4552, re.DOTALL)
po_code = match_po.group(0).strip()

match_inv = re.search(r'class SupplierInvoiceViewSet\(.*?(?=\nclass |\Z)', text_4552, re.DOTALL)
inv_code = match_inv.group(0).strip()

# Extract full RFQ and Quotation ViewSets from text_perfect
match_rfq = re.search(r'class RequestForQuotationViewSet\(.*?(?=\nclass |\Z)', text_perfect, re.DOTALL)
rfq_code = match_rfq.group(0).strip()

match_sq = re.search(r'class SupplierQuotationViewSet\(.*?(?=\nclass |\Z)', text_perfect, re.DOTALL)
sq_raw = match_sq.group(0)
sq_code = sq_raw.split("def update(self, request, *args, **kwargs):")[0].strip()

# Read current apps/inventory/views.py class slices
current_matches = list(re.finditer(r'^(class [A-Za-z0-9_]+[^\n]*:)', text_current, re.MULTILINE))
slices = {}
for i, m in enumerate(current_matches):
    start = m.start()
    end = current_matches[i+1].start() if i+1 < len(current_matches) else len(text_current)
    header = m.group(1)
    cname = re.match(r'class ([A-Za-z0-9_]+)', header).group(1)
    body = text_current[start:end]
    slices[cname] = body.strip()

# Override all procurement viewsets with their complete action-decorated versions
slices["PurchaseRequisitionViewSet"] = purchase_req_code
slices["PurchaseOrderViewSet"] = po_code
slices["SupplierInvoiceViewSet"] = inv_code
slices["RequestForQuotationViewSet"] = rfq_code
slices["SupplierQuotationViewSet"] = sq_code

header_code = text_current[:current_matches[0].start()].strip()

ordered_class_names = [
    "InventoryCategoryViewSet",
    "SupplierViewSet",
    "InventoryItemViewSet",
    "StockTransactionViewSet",
    "RecipeBOMViewSet",
    "InventoryDashboardStatsView",
    "InventoryWasteRecordViewSet",
    "StockLocationViewSet",
    "StockBatchViewSet",
    "BatchLocationBalanceViewSet",
    "ItemLocationBalanceViewSet",
    "StockTransferViewSet",
    "ProcurementApprovalPolicyViewSet",
    "PurchaseRequisitionViewSet",
    "PurchaseOrderViewSet",
    "GoodsReceiptNoteViewSet",
    "SupplierInvoiceViewSet",
    "RequestForQuotationViewSet",
    "SupplierQuotationViewSet",
    "StocktakeSessionViewSet",
    "StocktakeScheduleViewSet",
    "InventoryExpiryAlertViewSet",
]

content = header_code + "\n\n"
for cname in ordered_class_names:
    content += slices[cname] + "\n\n"

# Verify AST parse
tree = ast.parse(content)
classes_in_result = [n.name for n in tree.body if isinstance(n, ast.ClassDef)]
print(f"Validation SUCCESS! Total classes: {len(classes_in_result)}")
assert len(classes_in_result) == 22

with open("apps/inventory/views.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Updated apps/inventory/views.py with full procurement actions! Total lines:", len(content.splitlines()))
