import sqlite3, os, json

conn = sqlite3.connect("schoolsnap.db")
conn.row_factory = sqlite3.Row

# Event images
rows = conn.execute("SELECT id, event_id, original_path, preview_path, faces_count FROM event_images LIMIT 5").fetchall()
print(f"Sample event images ({len(rows)}):")
for r in rows:
    orig_ok = os.path.exists(r["original_path"]) if r["original_path"] else False
    prev_ok = os.path.exists(r["preview_path"]) if r["preview_path"] else False
    print(f"  id={r['id'][:12]}  faces={r['faces_count']}  orig_exists={orig_ok}  preview_exists={prev_ok}")
    if r["original_path"]:
        print(f"    orig: {r['original_path']}")
    if r["preview_path"]:
        print(f"    prev: {r['preview_path']}")

# FAISS metadata sample
meta_path = "faiss_store.meta"
if os.path.exists(meta_path):
    with open(meta_path) as f:
        meta = json.load(f)
    print(f"\nFAISS metadata entries: {len(meta)}")
    for m in meta[:5]:
        print(f"  image_id={m.get('image_id','?')[:12]}  image_path={m.get('image_path','?')}")
else:
    print("\nNo faiss_store.meta found")

# Check static file serving setup
imgs_dir = os.path.join(".", "images")
if os.path.isdir(imgs_dir):
    subdirs = os.listdir(imgs_dir)
    print(f"\nimages/ subdirs: {subdirs}")
    for sd in subdirs:
        full = os.path.join(imgs_dir, sd)
        if os.path.isdir(full):
            count = len(os.listdir(full))
            print(f"  {sd}/ = {count} files")

conn.close()
