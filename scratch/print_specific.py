import json

with open('scratch/forensic_13_items.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

for code in ['CORD-LIME-01', 'PER-MILK-01']:
    d = data[code]
    print(f"*** {code} ({d['name']}) ***")
    print(f"  Master Stock: {d['current_stock']} | Unit Cost: {d['unit_cost']} | Master Val: {d['master_valuation']}")
    print(f"  Batches ({d['batch_count']}):")
    for b in d['batches']:
        print(f"    - {b['batch_number']}: qty={b['current_quantity']}, status={b['status']}, legacy={b['is_legacy']}, cost={b['unit_cost']}, locs={b['locations']}")
    print(f"  Locations ({d['location_count']}): {[(l['location_code'], l['quantity']) for l in d['locations']]}")
    print(f"  Tx count: {len(d['transactions'])}")
    for t in d['transactions']:
        print(f"    Tx: {t['timestamp'][:16]} | {t['transaction_type']} | qty={t['quantity']} ({t['direction']}) | loc={t['location_code']} | batch={t['batch_num']} | ref={t['ref']}")
    print(f"  GRNs: {d['grns']}")
    print(f"  POs: {d['pos']}")
    print(f"  Transfers: {d['transfers']}")
    print(f"  Waste: {d['waste']}")
    print(f"  Journal Entries: {d['journal_entries']}")
    print("----------------------------------------------------------------")

