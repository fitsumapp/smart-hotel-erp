import json

with open('scratch/forensic_13_items.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

for code in ['BEV-JUICE-01', 'MB-SODA-01', 'CORD-LIME-01', 'PER-MILK-01', 'BEEF-001', 'POT-001', 'STK-BROWSER-01', 'STK-BROWSER-02', 'ITM-DAIRY-MILK', 'ITM-MEAT-BEEF', 'REMED-ITM-01', 'REMED-ITM-1793900106', 'REMED-ITM-1793900629']:
    d = data[code]
    print(f"*** {code} ({d['name']}) ***")
    print(f"  Master Stock: {d['current_stock']} | Unit Cost: {d['unit_cost']} | Master Val: {d['master_valuation']}")
    print(f"  Batches ({d['batch_count']}): {[(b['batch_number'], b['current_quantity'], b['status'], b['is_legacy']) for b in d['batches']]}")
    print(f"  Locations ({d['location_count']}): {[(l['location_code'], l['quantity']) for l in d['locations']]}")
    print(f"  Tx count: {len(d['transactions'])}")
    for t in d['transactions']:
        print(f"    Tx: {t['timestamp'][:16]} | {t['transaction_type']} | qty={t['quantity']} ({t['direction']}) | loc={t['location_code']} | batch={t['batch_num']} | ref={t['ref']}")
    print(f"  GRNs: {d['grns']}")
    print(f"  POs: {d['pos']}")
    print(f"  Transfers: {d['transfers']}")
    print(f"  Waste: {d['waste']}")
    print(f"  Stocktaking count: {len(d['stocktaking'])}")
    for s in d['stocktaking']:
        if s['status'] in ['approved', 'under_review', 'recount_required']:
            print(f"    STK: {s['session_number']} | status={s['status']} | loc={s['location']} | theo={s['theoretical_qty']} | counted={s['counted_qty']} | var={s['variance_qty']}")
    print(f"  Journal Entries: {d['journal_entries']}")
    print("----------------------------------------------------------------")

