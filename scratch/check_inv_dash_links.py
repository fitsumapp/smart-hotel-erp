with open('hotel-frontend/src/pages/InventoryDashboard.js', 'r', encoding='utf-8') as f:
    text = f.read()

for term in ['stocktake', 'stocktaking', 'procurement', 'schedule']:
    occurrences = [idx for idx, line in enumerate(text.splitlines(), 1) if term in line.lower()]
    print(f"Term '{term}': {len(occurrences)} occurrences in InventoryDashboard.js")
    for lno in occurrences[:5]:
        print(f"  L{lno}: {text.splitlines()[lno-1].strip()[:100]}")

