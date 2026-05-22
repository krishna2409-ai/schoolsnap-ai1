import sqlite3
import os

db_path = os.path.join("backend", "schoolsnap.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get all image IDs from DB
cursor.execute("SELECT id FROM event_images")
db_ids = {row[0] for row in cursor.fetchall()}

# Get all filenames from previews folder
preview_dir = os.path.join("backend", "images", "previews")
folder_files = {f.split(".")[0] for f in os.listdir(preview_dir) if f.endswith(".jpg")}

print(f"Total IDs in DB: {len(db_ids)}")
print(f"Total files in folder: {len(folder_files)}")

intersection = db_ids.intersection(folder_files)
print(f"Overlap (matching IDs): {len(intersection)}")

if len(intersection) > 0:
    print("Example overlap ID:", list(intersection)[0])
else:
    print("NO OVERLAP FOUND.")
    print("Sample DB IDs:", list(db_ids)[:3])
    print("Sample Folder IDs:", list(folder_files)[:3])

conn.close()
