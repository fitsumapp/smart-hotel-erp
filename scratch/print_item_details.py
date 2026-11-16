import json

with open('scratch/forensic_13_items.json') as f:
    data = json.load(f)

for code, d in data.items():
    print("=" * 80)
    print(f"ITEM: {d['name']} ({code}) [ID: {d['item_id']}] Category: {d['category']}")
    print(f"  Master Stock: {d['current_stock']} {d['unit']} @ {d['unit_cost']} ETB = {d['master_valuation']} ETB")
    print(f"  Batch count: {d['batch_count']}, Location count: {d['location_count']}")
    print(f"  Batches:")
    for b in d['batches']:
        print(f"    - Batch #{b['id']} ({b['batch_number']}): qty={b['current_quantity']}, init={b['initial_quantity']}, cost={b['unit_cost']}, status={b['status']}, legacy={b['is_legacy']}, exp={b['expiry_date']}, locs={b['locations']}")
    print(f"  Locations:")
    for l in d['locations']:
        print(f"    - Loc {l['location_code']} ({l['location_name']}): qty={l['quantity']}, val={l['valuation']}")
    print(f"  Stock Transactions ({len(d['transactions'])}):")
    for t in d['transactions']:
        print(f"    - TX #{t['id']} | {t['timestamp']} | type={t['transaction_type']} | qty={t['quantity']} | dir={t['direction']} | ref={t['ref']} | batch={t['batch_num']} | loc={t['location_code']} | notes={t['notes']}")
    print(f"  GRNs ({len(d['grns'])}):")
    for g in d['grns']:
        print(f"    - GRN #{g['grn_id']} ({g['grn_number']}) | PO: {g['po_number']} | qty={g['received_quantity']} | date={g['received_date']}")
    print(f"  POs ({len(d['pos'])}):")
    for p in d['pos']:
        print(f"    - PO #{p['po_id']} ({p['po_number']}) | qty={p['ordered_qty']} | rec={p['received_qty']} | status={p['status']}")
    print(f"  Transfers ({len(d['transfers'])}):")
    for tr in d['transfers']:
        print(f"    - Transfer #{tr['transfer_id']} ({tr['transfer_number']}): {tr['source']} -> {tr['dest']} | req={tr['requested_qty']} | disp={tr['dispatched_qty']} | rec={tr['received_qty']} | dam={tr['damaged_qty']} | status={tr['status']}")
    print(f"  Waste Records ({len(d['waste'])}):")
    for w in d['waste']:
        print(f"    - Waste #{w['id']}: cat={w['waste_category']}, src={w['waste_source']}, entered={w['entered_quantity']}, base={w['base_quantity']}, loss={w['total_cost_loss']}, deducted={w['stock_deducted']}, status={w['status']}, je={w['journal_entry_id']}, notes={w['notes']}")
    print(f"  Stocktaking ({len(d['stocktaking'])}):")
    for s in d['stocktaking']:
        print(f"    - Session #{s['session_id']} ({s['session_number']}) | loc={s['location']} | status={s['status']} | theo={s['theoretical_qty']} | counted={s['counted_qty']} | final={s['final_qty']} | var_qty={s['variance_qty']} | var_val={s['variance_val']}")
    print(f"  Journal Entries ({len(d['journal_entries'])}):")
    for j in d['journal_entries']:
        print(f"    - JE #{j['id']} ({j['entry_number']}) | {j['date']} | {j['description']}")
        for l in j['lines']:
            print(f"        {l['account_code']} ({l['account_name']}): Dr={l['debit']} Cr={l['credit']}")

