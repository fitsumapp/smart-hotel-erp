import os
import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect(
    dbname="hotel_erp_staging",
    user="postgres",
    password=os.getenv("DB_PASSWORD", "postgres"),
    host=os.getenv("DB_HOST", "localhost"),
    port=os.getenv("DB_PORT", "5432"),
)
conn.autocommit = True
cur = conn.cursor(cursor_factory=RealDictCursor)

def describe_tables(table_names):
    for table in table_names:
        print(f"\n==================== TABLE: {table} ====================")
        cur.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
            ORDER BY ordinal_position;
        """, (table,))
        cols = cur.fetchall()
        for col in cols:
            print(f"  {col['column_name']} ({col['data_type']}) nullable={col['is_nullable']} default={col['column_default']}")

# Category 1: Batch & Expiry
print("--- 1. BATCH & EXPIRY TABLES ---")
describe_tables(['hotel_stockbatch', 'hotel_batchlocationbalance', 'hotel_stockbatchconsumption', 'hotel_inventoryitem', 'hotel_notification'])

# Category 2: Procurement
print("--- 2. PROCUREMENT TABLES ---")
describe_tables([
    'hotel_purchaserequisition', 'hotel_purchaserequisitionitem',
    'hotel_purchaseorder', 'hotel_purchaseorderitem',
    'hotel_requestforquotation', 'hotel_requestforquotationitem',
    'hotel_supplierquotation', 'hotel_supplierquotationitem',
    'hotel_goodsreceiptnote', 'hotel_goodsreceiptnoteitem',
    'hotel_supplierinvoice', 'hotel_supplierinvoiceitem',
    'hotel_procurementapprovalpolicy', 'hotel_procurementapprovaltier'
])

# Category 3: Stocktaking
print("--- 3. STOCKTAKING TABLES ---")
describe_tables(['hotel_stocktakesession', 'hotel_stocktakeitem', 'hotel_stocktransaction'])

cur.close()
conn.close()

