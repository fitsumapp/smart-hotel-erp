with open('apps/inventory/views.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix 1: PurchaseRequisition queryset select_related
old_pr_qs = """class PurchaseRequisitionViewSet(viewsets.ModelViewSet):
    queryset = (
        PurchaseRequisition.objects.select_related("requester", "approved_by", "delivery_location")
        .prefetch_related("items__item")
        .order_by("-created_at")
    )"""

new_pr_qs = """class PurchaseRequisitionViewSet(viewsets.ModelViewSet):
    queryset = (
        PurchaseRequisition.objects.select_related("requested_by", "approved_by", "approval_tier")
        .prefetch_related("items__item")
        .order_by("-created_at")
    )"""

assert old_pr_qs in content, 'old_pr_qs not found'
content = content.replace(old_pr_qs, new_pr_qs, 1)

# Fix 2: Remove session_obj in PurchaseRequisitionViewSet approve
old_pr_approve = """    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        session_obj = self.get_object()
        notes = request.data.get("notes", "")"""

new_pr_approve = """    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        req_obj = self.get_object()
        notes = request.data.get("notes", "")"""

assert old_pr_approve in content, 'old_pr_approve not found'
content = content.replace(old_pr_approve, new_pr_approve, 1)

# Fix 3: Ensure StocktakeSessionViewSet approve calls self.get_object()
old_ss_approve = """    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        notes = request.data.get("notes", "")
        try:
            session = approve_stocktake_session("""

new_ss_approve = """    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        session_obj = self.get_object()
        notes = request.data.get("notes", "")
        try:
            session = approve_stocktake_session("""

assert old_ss_approve in content, 'old_ss_approve not found'
content = content.replace(old_ss_approve, new_ss_approve, 1)

with open('apps/inventory/views.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('SUCCESS: Cleanly updated PurchaseRequisitionViewSet and StocktakeSessionViewSet!')

