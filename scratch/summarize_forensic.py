import json

with open('scratch/forensic_13_items.json') as f:
    data = json.load(f)

print(f"{'Code':<22} | {'Master':<7} | {'ActBatch':<8} | {'QuarBatch':<9} | {'ExpBatch':<8} | {'LocSum':<7} | {'Cost':<7} | {'MasterVal':<10} | {'ActVal':<10} | {'Variance':<10}")
print("-" * 120)

for code, d in data.items():
    act_qty = d['status_summary'].get('active', {}).get('qty', 0.0)
    quar_qty = d['status_summary'].get('quarantined', {}).get('qty', 0.0)
    exp_qty = d['status_summary'].get('expired', {}).get('qty', 0.0)
    act_val = d['status_summary'].get('active', {}).get('val', 0.0)
    cost = d['unit_cost']
    m_qty = d['current_stock']
    m_val = d['master_valuation']
    loc_qty = d['location_total_qty']
    var = m_val - act_val
    print(f"{code:<22} | {m_qty:<7.2f} | {act_qty:<8.2f} | {quar_qty:<9.2f} | {exp_qty:<8.2f} | {loc_qty:<7.2f} | {cost:<7.2f} | {m_val:<10.2f} | {act_val:<10.2f} | {var:<10.2f}")

