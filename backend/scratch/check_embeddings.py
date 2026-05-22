import sqlite3
import os
import json

db_path = os.path.join("backend", "schoolsnap.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("--- Checking Selfies Embeddings ---")
cursor.execute("SELECT id, child_id, embedding_json FROM selfies LIMIT 5")
rows = cursor.fetchall()
for row in rows:
    emb = json.loads(row[2]) if row[2] else None
    is_mock = all(v == 0.0 for v in emb[:20]) if emb else "N/A"
    print(f"Selfie ID: {row[0]} | Child: {row[1]} | Mock: {is_mock}")

print("\n--- Checking Event Faces Embeddings ---")
cursor.execute("SELECT image_id, embedding_json FROM event_faces LIMIT 5")
rows = cursor.fetchall()
for row in rows:
    emb = json.loads(row[1]) if row[1] else None
    is_mock = all(v == 0.0 for v in emb[:20]) if emb else "N/A"
    print(f"Image ID: {row[0]} | Mock: {is_mock}")

conn.close()
