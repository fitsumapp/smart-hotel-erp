"""Inventory serializers."""
from users.serializers import *  # noqa: F401,F403

class InventoryCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = InventoryCategory
        fields = "__all__"


class SupplierSerializer(serializers.ModelSerializer):
    supplied_category_names = serializers.SerializerMethodField(read_only=True)

    def get_supplied_category_names(self, obj):
        return [cat.name for cat in obj.supplied_categories.all()]

    class Meta:
        model = Supplier
        fields = [
            "id", "name", "contact_person", "phone", "email",
            "address", "tin_number",
            "supplied_categories", "supplied_category_names",
            "supply_items",
            "created_at"
        ]


class InventoryItemSerializer(serializers.ModelSerializer):
    category_name = serializers.ReadOnlyField(source="category.name")
    category_type = serializers.ReadOnlyField(source="category.category_type")
    supplier_name = serializers.ReadOnlyField(source="last_supplier.name")

    class Meta:
        model = InventoryItem
        fields = [
            "id", "item_code", "name", "category", "category_name", "category_type", "unit", 
            "current_stock", "min_reorder_level", "unit_cost", "selling_price",
            "last_supplier", "supplier_name", "last_stocked_at", "created_at"
        ]
        read_only_fields = ["current_stock", "last_stocked_at", "created_at"]


class StockTransactionSerializer(serializers.ModelSerializer):
    item_name = serializers.ReadOnlyField(source="item.name")
    item_unit = serializers.ReadOnlyField(source="item.unit")
    supplier_name = serializers.ReadOnlyField(source="supplier.name")

    class Meta:
        model = StockTransaction
        fields = [
            "id", "item", "item_name", "item_unit", "transaction_type", 
            "quantity", "unit_cost", "supplier", "supplier_name", 
            "reference_number", "notes", "destination_dept", "destination_room",
            "logged_by_username", "timestamp", "reversal_of"
        ]
        read_only_fields = ["reversal_of", "logged_by_username", "timestamp"]


class RecipeBOMSerializer(serializers.ModelSerializer):
    menu_item_name = serializers.ReadOnlyField(source="menu_item.name")
    ingredient_name = serializers.ReadOnlyField(source="ingredient.name")
    ingredient_unit = serializers.ReadOnlyField(source="ingredient.unit")

    class Meta:
        model = RecipeBOM
        fields = [
            "id", "menu_item", "menu_item_name", "ingredient", 
            "ingredient_name", "ingredient_unit", "quantity_required"
        ]


