import os
import sys
import json
from decimal import Decimal

sys.path.insert(0, r"D:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment")
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
import django
django.setup()

from django.db.models import Sum, Q
from hotel.models import (
    InventoryItem, StockBatch, ItemLocationBalance, BatchLocationBalance, StockLocation,
    StockTransaction, GoodsReceiptNote, GoodsReceiptNoteItem,
    PurchaseOrder, PurchaseOrderItem, JournalEntry, JournalEntryItem,
    Account, InventoryWasteRecord, StockTransfer, StockTransferItem,
    StocktakeSession, StocktakeItem
)

target_item_codes = [
    'BEV-JUICE-01',
    'MB-SODA-01',
    'CORD-LIME-01',
    'PER-MILK-01',
    'BEEF-001',
    'POT-001',
    'STK-BROWSER-01',
    'STK-BROWSER-02',
    'ITM-DAIRY-MILK',
    'ITM-MEAT-BEEF',
    'REMED-ITM-01',
    'REMED-ITM-1793900106',
    'REMED-ITM-1793900629'
]

forensic_data = {}

for code in target_item_codes:
    try:
        item = InventoryItem.objects.get(item_code=code)
    except InventoryItem.DoesNotExist:
        print(f"ERROR: Item {code} not found!")
        continue

    # 1. Item Master
    u_cost = item.unit_cost or Decimal('0.00')
    master_val = item.current_stock * u_cost

    # 2. Batches
    batches = StockBatch.objects.filter(item=item).order_by('id')
    batch_list = []
    status_summary = {}
    for b in batches:
        st = b.status
        qty = float(b.current_quantity)
        cost = float(b.unit_cost)
        val = qty * cost
        b_locs = [{'loc': blb.location.code, 'qty': float(blb.quantity)} for blb in b.location_balances.all()]
        batch_list.append({
            'id': b.id,
            'batch_number': b.batch_number,
            'status': b.status,
            'current_quantity': qty,
            'initial_quantity': float(b.initial_quantity) if b.initial_quantity is not None else None,
            'unit_cost': cost,
            'valuation': val,
            'expiry_date': str(b.expiry_date) if b.expiry_date else None,
            'received_date': str(b.received_date) if b.received_date else None,
            'is_legacy': b.is_legacy,
            'locations': b_locs
        })
        if st not in status_summary:
            status_summary[st] = {'qty': Decimal('0.00'), 'val': Decimal('0.00'), 'count': 0}
        status_summary[st]['qty'] += b.current_quantity
        status_summary[st]['val'] += Decimal(str(val))
        status_summary[st]['count'] += 1

    # 3. Locations
    loc_bals = ItemLocationBalance.objects.filter(item=item).select_related('location').order_by('location__code')
    loc_list = []
    loc_total = Decimal('0.00')
    for lb in loc_bals:
        l_qty = lb.quantity
        loc_total += l_qty
        loc_list.append({
            'location_id': lb.location.id,
            'location_code': lb.location.code,
            'location_name': lb.location.name,
            'location_type': getattr(lb.location, 'location_type', 'unknown'),
            'is_active': lb.location.is_active,
            'quantity': float(l_qty),
            'valuation': float(l_qty * u_cost)
        })

    # 4. Transactions
    txs = StockTransaction.objects.filter(item=item).order_by('timestamp', 'id')
    tx_list = []
    for t in txs:
        tx_list.append({
            'id': t.id,
            'timestamp': str(t.timestamp),
            'transaction_type': t.transaction_type,
            'quantity': float(t.quantity),
            'unit_cost': float(t.unit_cost) if t.unit_cost else None,
            'direction': t.adjustment_direction,
            'batch_id': t.batch_id,
            'batch_num': t.batch.batch_number if t.batch else None,
            'location_code': t.location.code if t.location else None,
            'ref': t.reference_number,
            'notes': t.notes,
            'logged_by': t.logged_by_username,
            'reversal_of': t.reversal_of_id
        })

    # 5. GRNs
    grn_items = GoodsReceiptNoteItem.objects.filter(item=item).select_related('grn', 'grn__purchase_order', 'grn__supplier')
    grn_list = []
    for gi in grn_items:
        grn_list.append({
            'grn_id': gi.grn.id,
            'grn_number': gi.grn.grn_number,
            'po_number': gi.grn.purchase_order.po_number if gi.grn.purchase_order else None,
            'supplier': gi.grn.supplier.name if gi.grn.supplier else None,
            'received_date': str(gi.grn.received_date),
            'received_quantity': float(gi.quantity_received),
            'unit_cost': float(gi.unit_cost),
            'status': gi.grn.status
        })

    # 6. Purchase Orders
    po_items = PurchaseOrderItem.objects.filter(item=item).select_related('purchase_order', 'purchase_order__supplier')
    po_list = []
    for pi in po_items:
        po_list.append({
            'po_id': pi.purchase_order.id,
            'po_number': pi.purchase_order.po_number,
            'supplier': pi.purchase_order.supplier.name if pi.purchase_order.supplier else None,
            'ordered_qty': float(pi.quantity_ordered),
            'received_qty': float(pi.quantity_received),
            'unit_cost': float(pi.unit_price),
            'status': pi.purchase_order.status
        })

    # 7. Stock Transfers
    transfers = StockTransferItem.objects.filter(item=item).select_related('transfer', 'transfer__source_location', 'transfer__destination_location')
    transfer_list = []
    for ti in transfers:
        transfer_list.append({
            'transfer_id': ti.transfer.id,
            'transfer_number': ti.transfer.transfer_number,
            'source': ti.transfer.source_location.code if ti.transfer.source_location else None,
            'dest': ti.transfer.destination_location.code if ti.transfer.destination_location else None,
            'requested_qty': float(ti.quantity_requested),
            'dispatched_qty': float(ti.quantity_dispatched) if ti.quantity_dispatched is not None else None,
            'received_qty': float(ti.quantity_received) if ti.quantity_received is not None else None,
            'damaged_qty': float(ti.quantity_damaged) if ti.quantity_damaged is not None else None,
            'status': ti.transfer.status
        })

    # 8. Waste Records
    waste_recs = InventoryWasteRecord.objects.filter(item=item).order_by('id')
    waste_list = []
    for w in waste_recs:
        waste_list.append({
            'id': w.id,
            'waste_category': w.waste_category,
            'waste_source': w.waste_source,
            'entered_quantity': float(w.entered_quantity),
            'base_quantity': float(w.base_quantity),
            'total_cost_loss': float(w.total_cost_loss) if w.total_cost_loss else None,
            'stock_deducted': w.stock_deducted,
            'status': w.status,
            'journal_entry_id': w.journal_entry_id,
            'notes': w.notes
        })

    # 9. Stocktaking
    stk_items = StocktakeItem.objects.filter(item=item).select_related('session', 'session__location')
    stk_list = []
    for si in stk_items:
        stk_list.append({
            'session_id': si.session.id,
            'session_number': si.session.session_number,
            'title': si.session.title,
            'location': si.session.location.code if si.session.location else None,
            'status': si.session.status,
            'theoretical_qty': float(si.theoretical_quantity) if si.theoretical_quantity is not None else None,
            'counted_qty': float(si.counted_quantity) if si.counted_quantity is not None else None,
            'final_qty': float(si.final_quantity) if si.final_quantity is not None else None,
            'variance_qty': float(si.variance_quantity) if si.variance_quantity is not None else None,
            'variance_val': float(si.variance_value) if si.variance_value is not None else None,
            'batch': si.batch.batch_number if si.batch else None
        })

    # 10. Journal entries mentioning item
    jes = JournalEntry.objects.filter(
        Q(description__icontains=item.name) |
        Q(description__icontains=item.item_code) |
        Q(description__icontains=f"Item #{item.id}")
    ).order_by('date', 'id')
    je_list = []
    for j in jes:
        lines = []
        for l in j.items.all().select_related('account'):
            lines.append({
                'account_code': l.account.code,
                'account_name': l.account.name,
                'debit': float(l.amount_debit),
                'credit': float(l.amount_credit)
            })
        je_list.append({
            'id': j.id,
            'entry_number': j.entry_number,
            'date': str(j.date),
            'description': j.description,
            'lines': lines
        })

    forensic_data[code] = {
        'item_id': item.id,
        'item_code': item.item_code,
        'name': item.name,
        'category': item.category.name if item.category else None,
        'unit': item.unit,
        'unit_cost': float(u_cost),
        'current_stock': float(item.current_stock),
        'master_valuation': float(master_val),
        'batch_count': batches.count(),
        'batches': batch_list,
        'status_summary': {k: {'qty': float(v['qty']), 'val': float(v['val']), 'count': v['count']} for k, v in status_summary.items()},
        'location_count': loc_bals.count(),
        'locations': loc_list,
        'location_total_qty': float(loc_total),
        'location_total_val': float(loc_total * u_cost),
        'transactions': tx_list,
        'grns': grn_list,
        'pos': po_list,
        'transfers': transfer_list,
        'waste': waste_list,
        'stocktaking': stk_list,
        'journal_entries': je_list
    }

with open('scratch/forensic_13_items.json', 'w') as f:
    json.dump(forensic_data, f, indent=2)

print("Forensic data successfully exported to scratch/forensic_13_items.json")
