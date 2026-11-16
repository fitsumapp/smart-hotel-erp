with open('apps/inventory/views.py', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Update StocktakeSessionViewSet
target_session = """class StocktakeSessionViewSet(viewsets.ModelViewSet):
    \"\"\"
    Authoritative ViewSet for Dual-Mode Physical Stocktaking Sessions.
    Implements counting, recounting, approval, cancellation, and audit preservation.
    \"\"\"
    queryset = StocktakeSession.objects.all().select_related(
        "location", "category", "created_by", "counted_by", "reviewed_by", "journal_entry"
    ).prefetch_related("items__item")
    serializer_class = StocktakeSessionSerializer
    permission_classes = [HasStocktakeLocationPermission]

    def create(self, request, *args, **kwargs):
        location_id = request.data.get("location") or request.data.get("location_id")
        category_id = request.data.get("category") or request.data.get("category_id")
        counting_mode = request.data.get("counting_mode", "blind")
        title = request.data.get("title")

        if not location_id:
            return Response({"error": "location is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            session = create_stocktake_session("""

replacement_session = """class StocktakeSessionViewSet(viewsets.ModelViewSet):
    \"\"\"
    Authoritative ViewSet for Dual-Mode Physical Stocktaking Sessions.
    Implements counting, recounting, approval, cancellation, and audit preservation.
    \"\"\"
    serializer_class = StocktakeSessionSerializer
    permission_classes = [HasStocktakeLocationPermission]

    def get_queryset(self):
        user = self.request.user
        qs = StocktakeSession.objects.all().select_related(
            "location", "category", "created_by", "counted_by", "reviewed_by", "journal_entry"
        ).prefetch_related("items__item")

        # Enforce location scoping for non-admin/management users
        if user and user.is_authenticated and not (user.is_superuser or getattr(user, "role", "") in {"admin", "hotel_manager"}):
            from django.db.models import Q
            qs = qs.filter(
                Q(location__custodian=user)
                | Q(created_by=user)
                | Q(counted_by=user)
                | Q(schedule__assigned_staff=user)
                | Q(location__custodian__isnull=True)
            ).distinct()

        location_id = self.request.query_params.get("location")
        status_param = self.request.query_params.get("status")
        counting_mode = self.request.query_params.get("counting_mode")

        if location_id:
            qs = qs.filter(location_id=location_id)
        if status_param:
            qs = qs.filter(status=status_param)
        if counting_mode:
            qs = qs.filter(counting_mode=counting_mode)
        return qs

    def create(self, request, *args, **kwargs):
        location_id = request.data.get("location") or request.data.get("location_id")
        category_id = request.data.get("category") or request.data.get("category_id")
        counting_mode = request.data.get("counting_mode", "blind")
        title = request.data.get("title")

        if not location_id:
            return Response({"error": "location is required."}, status=status.HTTP_400_BAD_REQUEST)

        # Enforce location authorization on creation for non-admin staff
        user = request.user
        if user and not (user.is_superuser or getattr(user, "role", "") in {"admin", "hotel_manager"}):
            try:
                loc = StockLocation.objects.get(pk=location_id)
                if loc.custodian_id and loc.custodian_id != user.id:
                    return Response(
                        {"error": "You do not have permission to initiate stocktaking for this location."},
                        status=status.HTTP_403_FORBIDDEN,
                    )
            except StockLocation.DoesNotExist:
                return Response({"error": "Stock location not found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            session = create_stocktake_session("""

assert target_session in text, "target_session not found in apps/inventory/views.py"
text = text.replace(target_session, replacement_session, 1)

# 2. Update StocktakeScheduleViewSet
target_sched = """    def get_queryset(self):
        qs = StocktakeSchedule.objects.select_related("location", "category", "assigned_staff", "created_by").all()
        frequency = self.request.query_params.get("frequency")
        is_active = self.request.query_params.get("is_active")
        location_id = self.request.query_params.get("location")

        if frequency:
            qs = qs.filter(frequency=frequency)
        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() in ("true", "1"))
        if location_id:
            qs = qs.filter(location_id=location_id)
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)"""

replacement_sched = """    def get_queryset(self):
        user = self.request.user
        qs = StocktakeSchedule.objects.select_related("location", "category", "assigned_staff", "created_by").all()

        # Enforce location scoping for non-admin/management users
        if user and user.is_authenticated and not (user.is_superuser or getattr(user, "role", "") in {"admin", "hotel_manager"}):
            from django.db.models import Q
            qs = qs.filter(
                Q(location__custodian=user)
                | Q(assigned_staff=user)
                | Q(created_by=user)
                | Q(location__custodian__isnull=True)
            ).distinct()

        frequency = self.request.query_params.get("frequency")
        is_active = self.request.query_params.get("is_active")
        location_id = self.request.query_params.get("location")

        if frequency:
            qs = qs.filter(frequency=frequency)
        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() in ("true", "1"))
        if location_id:
            qs = qs.filter(location_id=location_id)
        return qs

    def create(self, request, *args, **kwargs):
        location_id = request.data.get("location")
        user = request.user
        if user and not (user.is_superuser or getattr(user, "role", "") in {"admin", "hotel_manager"}):
            if location_id:
                try:
                    loc = StockLocation.objects.get(pk=location_id)
                    if loc.custodian_id and loc.custodian_id != user.id:
                        return Response(
                            {"error": "You do not have permission to schedule stocktaking for this location."},
                            status=status.HTTP_403_FORBIDDEN,
                        )
                except StockLocation.DoesNotExist:
                    return Response({"error": "Stock location not found."}, status=status.HTTP_404_NOT_FOUND)
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)"""

assert target_sched in text, "target_sched not found in apps/inventory/views.py"
text = text.replace(target_sched, replacement_sched, 1)

with open('apps/inventory/views.py', 'w', encoding='utf-8', newline='') as f:
    f.write(text)

print("Updated apps/inventory/views.py successfully!")

