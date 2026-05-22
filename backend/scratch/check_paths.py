
import sqlite3
import os

db_path = "schoolsnap.db"
if not os.path.exists(db_path):
    print(f"DB not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("--- Event Images Sample ---")
rows = cursor.execute("SELECT id, preview_path, original_path FROM event_images LIMIT 5").fetchall()
for row in rows:
    print(f"ID: {row['id']}")
    print(f"  Preview: {row['preview_path']}")
    print(f"  Original: {row['original_path']}")

conn.close()
