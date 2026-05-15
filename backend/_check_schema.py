import database as db

conn = db.get_connection()
cols = conn.execute("PRAGMA table_info(event_images)").fetchall()
print("event_images cols:", [c[1] for c in cols])
row = conn.execute("SELECT * FROM event_images LIMIT 1").fetchone()
if row:
    print("Keys:", list(row.keys()))
conn.close()
