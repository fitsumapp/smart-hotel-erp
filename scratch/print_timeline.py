import json

with open('scratch/forensic_13_items.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

for code, d in data.items():
    print('================================================================')
    print(f"{code} : {d['name']} ({d['unit']}) @ {d['unit_cost']} ETB")
    print(f"  Master Stock: {d['current_stock']} | Valuation: {d['master_valuation']} ETB")
    print(f"  Status summary: {d['status_summary']}")
    print(f"  Locations (sum={d['location_total_qty']}): {d['locations']}")
    print(f"  Batches ({d['batch_count']}):")
    for b in d['batches']:
        print(f"    - {b['batch_number']}: qty={b['current_quantity']}, status={b['status']}, legacy={b['is_legacy']}, cost={b['unit_cost']}, locs={b['locations']}")
    print(f"  Transactions ({len(d['transactions'])}):")
    for t in d['transactions']:
        print(f"    - [{t['timestamp'][:19]}] {t['transaction_type']} | qty={t['quantity']} ({t['direction']}) | loc={t['location_code']} | batch={t['batch_num']} | ref={t['ref']}")
    print(f"  GRNs: {len(d['grns'])} | POs: {len(d['pos'])} | Transfers: {len(d['transfers'])} | Waste: {len(d['waste'])} | Stocktake: {len(d['stocktaking'])} | JEs: {len(d['journal_entries'])}")
    if d['transfers']:
        for tr in d['transfers']:
            print(f"    Transfer: {tr}")
    if d['waste']:
        for w in d['waste']:
            print(f"    Waste: {w}")
    if d['stocktaking']:
        for st in d['stocktaking']:
            print(f"    Stocktake: {st}")
    if d['journal_entries']:
        for je in d['journal_entries']:
            print(f"    JE: {je}")
