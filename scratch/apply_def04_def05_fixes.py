# 1. Update apps/orders/serializers.py for current_business_date safe representation
with open('apps/orders/serializers.py', 'r', encoding='utf-8') as f:
    ser_text = f.read()

date_field_def = """class SafeDateField(serializers.DateField):
    def to_representation(self, value):
        if hasattr(value, "date"):
            value = value.date()
        return super().to_representation(value)


class SystemSettingsSerializer(serializers.ModelSerializer):
    enabled_features = serializers.SerializerMethodField()
    current_business_date = SafeDateField(required=False)"""

target_ser = """class SystemSettingsSerializer(serializers.ModelSerializer):
    enabled_features = serializers.SerializerMethodField()"""

assert target_ser in ser_text, "target_ser not found in apps/orders/serializers.py"
ser_text = ser_text.replace(target_ser, date_field_def, 1)

with open('apps/orders/serializers.py', 'w', encoding='utf-8', newline='') as f:
    f.write(ser_text)
print("Updated apps/orders/serializers.py with SafeDateField!")

# 2. Update apps/inventory/views.py to call self.get_object() in all actions
with open('apps/inventory/views.py', 'r', encoding='utf-8') as f:
    views_text = f.read()

# Update record_counts
t_rec = """    @action(detail=True, methods=["post"], url_path="record-counts")
    def record_counts(self, request, pk=None):
        counts = request.data.get("counts") or request.data.get("items") or request.data.get("counts_data")"""

r_rec = """    @action(detail=True, methods=["post"], url_path="record-counts")
    def record_counts(self, request, pk=None):
        session_obj = self.get_object()
        counts = request.data.get("counts") or request.data.get("items") or request.data.get("counts_data")"""

assert t_rec in views_text, "t_rec not found"
views_text = views_text.replace(t_rec, r_rec, 1)

# Update request_recount
t_req = """    @action(detail=True, methods=["post"], url_path="request-recount")
    def request_recount(self, request, pk=None):
        item_ids = request.data.get("item_ids") or request.data.get("items")"""

r_req = """    @action(detail=True, methods=["post"], url_path="request-recount")
    def request_recount(self, request, pk=None):
        session_obj = self.get_object()
        item_ids = request.data.get("item_ids") or request.data.get("items")"""

assert t_req in views_text, "t_req not found"
views_text = views_text.replace(t_req, r_req, 1)

# Update submit_recount
t_sub = """    @action(detail=True, methods=["post"], url_path="submit-recount")
    def submit_recount(self, request, pk=None):
        recounts = ("""

r_sub = """    @action(detail=True, methods=["post"], url_path="submit-recount")
    def submit_recount(self, request, pk=None):
        session_obj = self.get_object()
        recounts = ("""

assert t_sub in views_text, "t_sub not found"
views_text = views_text.replace(t_sub, r_sub, 1)

# Update approve
t_app = """    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        notes = request.data.get("notes", "")"""

r_app = """    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        session_obj = self.get_object()
        notes = request.data.get("notes", "")"""

assert t_app in views_text, "t_app not found"
views_text = views_text.replace(t_app, r_app, 1)

# Update cancel
t_can = """    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        reason = request.data.get("reason", "")"""

r_can = """    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        session_obj = self.get_object()
        reason = request.data.get("reason", "")"""

assert t_can in views_text, "t_can not found"
views_text = views_text.replace(t_can, r_can, 1)

with open('apps/inventory/views.py', 'w', encoding='utf-8', newline='') as f:
    f.write(views_text)
print("Updated apps/inventory/views.py with self.get_object() calls!")

