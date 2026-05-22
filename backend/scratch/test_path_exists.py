import os
import sqlite3

db_path = os.path.join("backend", "schoolsnap.db")
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

row = cursor.execute("SELECT preview_path FROM event_images WHERE id='0a589002-5b42-4909-b64e-e3012c308908'").fetchone()
if row:
    path = row['preview_path']
    print(f"Path from DB: {path}")
    print(f"os.path.exists: {os.path.exists(path)}")
    
    # Try with corrected casing if it fails
    corrected = path.replace("D:", "d:")
    print(f"Corrected path: {corrected}")
    print(f"os.path.exists (corrected): {os.path.exists(corrected)}")

    # Try relative path
    rel_path = os.path.join("backend", "images", "previews", "0a589002-5b42-4909-b64e-e3012c308908.jpg")
    print(f"Relative path: {rel_path}")
    print(f"os.path.exists (relative): {os.path.exists(rel_path)}")

conn.close()
