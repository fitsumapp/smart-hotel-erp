import re

with open('hotel-frontend/src/pages/InventoryDashboard.js', 'r', encoding='utf-8') as f:
    text = f.read()

tabs = re.findall(r"setActiveTab\(['\"]([a-zA-Z0-9_\-]+)['\"]\)", text)
print("Tabs in InventoryDashboard:", sorted(set(tabs)))

# Look for sub-components or imports
imports = [line.strip() for line in text.splitlines() if line.startswith('import ') and ('stock' in line.lower() or 'procure' in line.lower() or 'batch' in line.lower())]
print("\nRelated imports in InventoryDashboard:")
for imp in imports:
    print("  ", imp)

