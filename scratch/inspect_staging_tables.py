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

# 1. Get all tables in public schema
cur.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public' 
    ORDER BY table_name;
""")
tables = [r['table_name'] for r in cur.fetchall()]
print(f"Total tables in hotel_erp_staging: {len(tables)}")
print("Tables:")
for t in tables:
    print(f"  - {t}")

cur.close()
conn.close()

