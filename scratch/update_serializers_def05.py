with open('apps/orders/serializers.py', 'r', encoding='utf-8') as f:
    text = f.read()

target = """        if getattr(obj, "module_finance", True):
            features.extend(["finance", "payments"])
        return features"""

replacement = """        if getattr(obj, "module_finance", True):
            features.extend(["finance", "payments"])
        return features

    def validate_near_expiry_warning_days(self, value):
        if value is not None:
            if value < 1 or value > 365:
                raise serializers.ValidationError("Near-expiry warning window must be a positive integer between 1 and 365 days.")
        return value"""

assert target in text, "target not found in apps/orders/serializers.py"
text = text.replace(target, replacement, 1)

with open('apps/orders/serializers.py', 'w', encoding='utf-8', newline='') as f:
    f.write(text)

print("Updated apps/orders/serializers.py successfully!")

