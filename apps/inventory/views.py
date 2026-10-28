"""Inventory API views extracted from the legacy facade."""
# Shared imports and compatibility helpers live in users.views during migration.
from users.views import *  # noqa: F401,F403
from django.core.exceptions import PermissionDenied, ValidationError
from hotel.models import InventoryWasteRecord
from .selectors import select_inventory_items, select_stock_transactions
from .serializers import InventoryWasteRecordSerializer
from .services import (
    approve_waste_entry,
    record_stock_change,
    record_waste_entry,
    reject_waste_entry,
    reverse_stock_transaction,
    reverse_waste_entry,
)
from rest_framework.decorators import action


class InventoryCategoryViewSet(viewsets.ModelViewSet):
    queryset = InventoryCategory.objects.all()
    serializer_class = InventoryCategorySerializer
    permission_classes = [IsInventoryManager]


class SupplierViewSet(viewsets.ModelViewSet):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    permission_classes = [IsSupplierOperator]


class InventoryItemViewSet(viewsets.ModelViewSet):
    def get_queryset(self):
        return select_inventory_items(self.request.query_params)

    serializer_class = InventoryItemSerializer
    permission_classes = [IsInventoryManager]


class StockTransactionViewSet(viewsets.ModelViewSet):
    def get_queryset(self):
        return select_stock_transactions(self.request.query_params)

    serializer_class = StockTransactionSerializer
    permission_classes = [IsInventoryManager]

    def update(self, request, *args, **kwargs):
        return Response({"error": "Stock history is immutable."}, status=405)

    def destroy(self, request, *args, **kwargs):
        return Response({"error": "Stock history is immutable; reverse it instead."}, status=405)

    @action(detail=True, methods=["post"], url_path="reverse")
    def reverse(self, request, pk=None):
        if request.user.role not in ("admin", "inventory") and not request.user.is_superuser:
            return Response({"error": "Inventory manager or administrator role required."}, status=403)
        try:
            reversal, created = reverse_stock_transaction(
                transaction_id=pk, reason=request.data.get("reason"),
                logged_by_username=request.user.username,
            )
        except StockTransaction.DoesNotExist:
            return Response({"error": "Stock transaction not found."}, status=404)
        return Response(StockTransactionSerializer(reversal).data, status=201 if created else 200)

    def perform_create(self, serializer):
        with transaction.atomic():
            data = serializer.validated_data
            item, transaction_inst = record_stock_change(
                item_id=data["item"].pk, transaction_type=data["transaction_type"],
                quantity=data["quantity"], unit_cost=data["unit_cost"],
                supplier=data.get("supplier"), reference_number=data.get("reference_number"),
                notes=data.get("notes"), destination_dept=data.get("destination_dept"),
                destination_room=data.get("destination_room"),
                logged_by_username=self.request.user.username,
            )
            serializer.instance = transaction_inst
            qty = transaction_inst.quantity

            # --- Post General Ledger Journal Entry ---
            try:
                total_cost = to_decimal(qty * transaction_inst.unit_cost)
                if total_cost > 0:
                    if transaction_inst.transaction_type == "purchase":
                        pay_acct = "2000" if transaction_inst.supplier else "1000"
                        post_journal_entry(
                            description=f"Auto JV: Inventory Purchase - {item.name} ({qty} {item.unit})",
                            items=[
                                {
                                    "account_code": "1300", # Inventory Asset
                                    "debit": total_cost,
                                    "credit": Decimal("0.00")
                                },
                                {
                                    "account_code": pay_acct, # Cash or Accounts Payable
                                    "debit": Decimal("0.00"),
                                    "credit": total_cost
                                }
                            ]
                        )
                    elif transaction_inst.transaction_type == "issuance":
                        post_journal_entry(
                            description=f"Auto JV: Inventory Issuance - {item.name} ({qty} {item.unit})",
                            items=[
                                {
                                    "account_code": "5000", # COGS
                                    "debit": total_cost,
                                    "credit": Decimal("0.00")
                                },
                                {
                                    "account_code": "1300", # Inventory Asset
                                    "debit": Decimal("0.00"),
                                    "credit": total_cost
                                }
                            ]
                        )
            except Exception as e:
                print(f"GL Auto-post error for stock transaction: {e}")


class RecipeBOMViewSet(viewsets.ModelViewSet):
    queryset = RecipeBOM.objects.all()
    serializer_class = RecipeBOMSerializer
    permission_classes = [IsInventoryManager]

    from rest_framework.decorators import action
    @action(detail=False, methods=['post'], url_path='bulk-save')
    def bulk_save(self, request):
        menu_item_id = request.data.get('menu_item')
        ingredients = request.data.get('ingredients', [])

        if not menu_item_id:
            return Response({"error": "menu_item is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            menu_item = MenuItem.objects.get(id=menu_item_id)
        except MenuItem.DoesNotExist:
            return Response({"error": "Menu item not found"}, status=status.HTTP_404_NOT_FOUND)

        with transaction.atomic():
            # Delete old mappings for this menu item
            RecipeBOM.objects.filter(menu_item=menu_item).delete()

            # Create new ones
            for ing_data in ingredients:
                ing_id = ing_data.get('ingredient')
                qty = ing_data.get('quantity_required')
                if not ing_id or qty is None or float(qty) <= 0:
                    continue
                try:
                    ingredient = InventoryItem.objects.get(id=ing_id)
                    RecipeBOM.objects.create(
                        menu_item=menu_item,
                        ingredient=ingredient,
                        quantity_required=Decimal(str(qty))
                    )
                except InventoryItem.DoesNotExist:
                    pass

        return Response({"status": "success", "message": "Recipe mapped successfully"})


class InventoryDashboardStatsView(APIView):
    permission_classes = [IsInventoryManager]

    def get(self, request):
        from django.db.models import Sum, F, ExpressionWrapper, DecimalField
        items = InventoryItem.objects.select_related("category")
        total_items = items.count()
        total_valuation = items.aggregate(
            total=Sum(ExpressionWrapper(
                F("current_stock") * F("unit_cost"),
                output_field=DecimalField(max_digits=18, decimal_places=2),
            ))
        )["total"] or 0
        low_stock_items = items.filter(current_stock__lt=F("min_reorder_level"))
        low_stock_count = low_stock_items.count()

        suppliers_count = Supplier.objects.count()

        low_stock_list = []
        for item in low_stock_items:
            low_stock_list.append({
                "id": item.id,
                "name": item.name,
                "item_code": item.item_code,
                "current_stock": float(item.current_stock),
                "min_reorder_level": float(item.min_reorder_level),
                "unit": item.unit,
                "category_name": item.category.name,
            })

        return Response({
            "total_items": total_items,
            "total_valuation": float(total_valuation),
            "low_stock_count": low_stock_count,
            "suppliers_count": suppliers_count,
            "low_stock_items": low_stock_list
        }, status=status.HTTP_200_OK)


class InventoryWasteRecordViewSet(viewsets.ModelViewSet):
    permission_classes = [IsInventoryManager]
    serializer_class = InventoryWasteRecordSerializer

    def get_queryset(self):
        qs = InventoryWasteRecord.objects.select_related("item", "source_dispatch", "stock_transaction").all()
        item_id = self.request.query_params.get("item")
        category = self.request.query_params.get("category")
        source = self.request.query_params.get("source")
        status_param = self.request.query_params.get("status")
        if item_id:
            qs = qs.filter(item_id=item_id)
        if category:
            qs = qs.filter(waste_category=category)
        if source:
            qs = qs.filter(waste_source=source)
        if status_param:
            qs = qs.filter(status=status_param)
        return qs.order_by("-recorded_at")

    def create(self, request, *args, **kwargs):
        idempotency_key = request.headers.get("Idempotency-Key") or request.data.get("idempotency_key")
        if not idempotency_key or not str(idempotency_key).strip():
            return Response({"error": "An Idempotency-Key header is required."}, status=status.HTTP_400_BAD_REQUEST)

        item_id = request.data.get("item")
        entered_qty = request.data.get("entered_quantity")
        entered_unit = request.data.get("entered_unit")
        waste_category = request.data.get("waste_category")
        waste_source = request.data.get("waste_source")
        notes = request.data.get("notes", "")
        storage_area = request.data.get("storage_area", "")
        source_dispatch_id = request.data.get("source_dispatch")

        if not item_id or entered_qty is None or not entered_unit or not waste_category or not waste_source:
            return Response(
                {"error": "item, entered_quantity, entered_unit, waste_category, and waste_source are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            record, created = record_waste_entry(
                item_id=item_id,
                entered_quantity=entered_qty,
                entered_unit=entered_unit,
                waste_category=waste_category,
                waste_source=waste_source,
                idempotency_key=str(idempotency_key).strip(),
                notes=notes,
                storage_area=storage_area,
                source_dispatch_id=source_dispatch_id,
                logged_by_username=request.user.username if request.user else "system",
            )
        except ValidationError as e:
            msg = e.message if hasattr(e, "message") else ("; ".join(e.messages) if hasattr(e, "messages") else str(e))
            if "Idempotency key was already used for a different" in msg:
                return Response({"error": msg}, status=status.HTTP_409_CONFLICT)
            return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(record)
        return Response(serializer.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    def update(self, request, *args, **kwargs):
        return Response({"error": "Waste records are immutable; reverse them instead."}, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def destroy(self, request, *args, **kwargs):
        return Response({"error": "Waste records are immutable; reverse them instead."}, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        if getattr(request.user, "role", "") != "admin" and not getattr(request.user, "is_superuser", False):
            return Response({"error": "Administrator role required to approve waste."}, status=status.HTTP_403_FORBIDDEN)

        justification = request.data.get("justification", "")
        try:
            waste = approve_waste_entry(
                waste_id=pk,
                reviewer=request.user,
                justification=justification,
            )
        except InventoryWasteRecord.DoesNotExist:
            return Response({"error": "Waste record not found."}, status=status.HTTP_404_NOT_FOUND)
        except PermissionDenied as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except ValidationError as e:
            msg = e.message if hasattr(e, "message") else ("; ".join(e.messages) if hasattr(e, "messages") else str(e))
            if "independent administrator review is required" in msg or "cannot approve their own" in msg:
                return Response({"error": msg}, status=status.HTTP_403_FORBIDDEN)
            return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(waste)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        if getattr(request.user, "role", "") != "admin" and not getattr(request.user, "is_superuser", False):
            return Response({"error": "Administrator role required to reject waste."}, status=status.HTTP_403_FORBIDDEN)

        reason = request.data.get("reason")
        if not reason or not str(reason).strip():
            return Response({"error": "A rejection reason is required."}, status=status.HTTP_400_BAD_REQUEST)

        justification = request.data.get("justification", "")
        try:
            waste = reject_waste_entry(
                waste_id=pk,
                reviewer=request.user,
                reason=reason,
                justification=justification,
            )
        except InventoryWasteRecord.DoesNotExist:
            return Response({"error": "Waste record not found."}, status=status.HTTP_404_NOT_FOUND)
        except PermissionDenied as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except ValidationError as e:
            msg = e.message if hasattr(e, "message") else ("; ".join(e.messages) if hasattr(e, "messages") else str(e))
            if "independent administrator review is required" in msg or "cannot reject their own" in msg:
                return Response({"error": msg}, status=status.HTTP_403_FORBIDDEN)
            return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(waste)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="reverse")
    def reverse(self, request, pk=None):
        if request.user.role not in ("admin", "inventory") and not request.user.is_superuser:
            return Response({"error": "Inventory manager or administrator role required."}, status=status.HTTP_403_FORBIDDEN)
        reason = request.data.get("reason")
        if not reason or not str(reason).strip():
            return Response({"error": "A reversal reason is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            reversal, created = reverse_waste_entry(
                waste_id=pk,
                reason=reason,
                logged_by_username=request.user.username if request.user else "system",
            )
        except InventoryWasteRecord.DoesNotExist:
            return Response({"error": "Waste record not found."}, status=status.HTTP_404_NOT_FOUND)
        except ValidationError as e:
            msg = e.message if hasattr(e, "message") else ("; ".join(e.messages) if hasattr(e, "messages") else str(e))
            return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(reversal)
        return Response(serializer.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
