import os, json, sqlite3

base_dir = r"D:\Projects\SNAP!\backend"

# Check directories
for d in ["uploads", "data", "selfies", "images"]:
    full = os.path.join(base_dir, d)
    if os.path.exists(full):
        count = sum(len(f) for _, _, f in os.walk(full))
        print(f"{d}/ exists, {count} files")
    else:
        print(f"{d}/ NOT FOUND")

# Check DB selfies
conn = sqlite3.connect(os.path.join(base_dir, "schoolsnap.db"))
conn.row_factory = sqlite3.Row
selfies = conn.execute("SELECT id, child_id, file_path, embedding_json IS NOT NULL as has_emb FROM selfies LIMIT 10").fetchall()
print(f"\nDB selfies: {len(selfies)}")
for s in selfies:
    sid = s["id"][:12]
    cid = s["child_id"][:12]
    exists = os.path.exists(s["file_path"])
    print(f"  id={sid}... child={cid}... has_emb={s['has_emb']} file_exists={exists} path={s['file_path']}")
    if s["has_emb"]:
        emb = json.loads(conn.execute("SELECT embedding_json FROM selfies WHERE id=?", (s["id"],)).fetchone()["embedding_json"])
        is_mock = all(v == 0.0 for v in emb)
        print(f"    dim={len(emb)}, is_mock={is_mock}, first_3={emb[:3]}")

# Check events
rows = conn.execute("SELECT id, name, folder_path, status, total_images, processed_images FROM events").fetchall()
print(f"\nEvents: {len(rows)}")
for r in rows:
    print(f"  {r['name']} (id={r['id'][:8]}...): status={r['status']}, {r['processed_images']}/{r['total_images']} images")

# Check event images
img_count = conn.execute("SELECT count(*) FROM event_images").fetchone()[0]
print(f"\nEvent Images total: {img_count}")

# Check faces
face_count = conn.execute("SELECT count(*) FROM event_faces").fetchone()[0]
print(f"\nEvent Faces total: {face_count}")

# Check some face records
if face_count > 0:
    face = conn.execute("SELECT image_id, embedding_json IS NOT NULL as has_emb, bbox FROM event_faces LIMIT 3").fetchall()
    print("Sample faces:")
    for f in face:
        print(f"  img_id={f['image_id'][:8]}... has_emb={f['has_emb']}, bbox={f['bbox']}")

conn.close()
