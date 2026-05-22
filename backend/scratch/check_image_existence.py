import sqlite3
import os

db_path = os.path.join("backend", "schoolsnap.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("--- Sample Paths from event_images ---")
cursor.execute("SELECT id, preview_path, original_path FROM event_images LIMIT 5")
rows = cursor.fetchall()
for row in rows:
    print(f"ID: {row[0]}")
    print(f"  Preview: {row[1]}")
    print(f"  Original: {row[2]}")

print("\n--- Checking if files exist locally ---")
for row in rows:
    # Check preview path
    p_path = row[1]
    # If it's an absolute path like D:\Projects\SNAP!\backend\images\..., it might be fine on Windows
    # but we need to see how the backend serves it.
    exists = os.path.exists(p_path)
    print(f"Path: {p_path} | Exists: {exists}")

conn.close()
