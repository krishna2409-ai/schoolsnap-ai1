import sqlite3, json, os

conn = sqlite3.connect("schoolsnap.db")
conn.row_factory = sqlite3.Row
rows = conn.execute("SELECT id, file_path, embedding_json FROM selfies").fetchall()
deleted = 0
for r in rows:
    emb = json.loads(r["embedding_json"] or "[]")
    if all(v == 0.0 for v in emb):
        conn.execute("DELETE FROM selfies WHERE id = ?", (r["id"],))
        if os.path.exists(r["file_path"]):
            os.remove(r["file_path"])
        deleted += 1
        print("Deleted mock selfie:", r["id"][:12])
conn.commit()
remaining = conn.execute("SELECT COUNT(*) as c FROM selfies").fetchone()["c"]
print(f"Cleaned {deleted} mock selfies. Remaining real: {remaining}")
conn.close()
