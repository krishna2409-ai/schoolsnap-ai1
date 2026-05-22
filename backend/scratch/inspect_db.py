import sqlite3
import os

db_path = os.path.join("backend", "schoolsnap.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("--- Tables in schoolsnap.db ---")
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()
for table in tables:
    print(table[0])

print("\n--- Rows count ---")
for table in tables:
    t_name = table[0]
    count = cursor.execute(f"SELECT COUNT(*) FROM {t_name}").fetchone()[0]
    print(f"{t_name}: {count}")

conn.close()
