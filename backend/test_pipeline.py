"""Test that DeepFace can extract a face from one of the stored selfies,
proving the pipeline works end-to-end."""
import os, json, sqlite3
from ai_service import ai_service

base_dir = r"D:\Projects\SNAP!\backend"
conn = sqlite3.connect(os.path.join(base_dir, "schoolsnap.db"))
conn.row_factory = sqlite3.Row

# Get a selfie that has a real file
selfies = conn.execute("SELECT * FROM selfies WHERE embedding_json IS NOT NULL LIMIT 5").fetchall()
print(f"Testing {len(selfies)} selfies...\n")

for s in selfies:
    path = s["file_path"]
    if not os.path.exists(path):
        # try relative path
        alt = os.path.join(base_dir, path)
        if os.path.exists(alt):
            path = alt
        else:
            print(f"  SKIP {s['id'][:12]}... file not found: {s['file_path']}")
            continue

    print(f"Extracting from: {path}")
    print(f"  File size: {os.path.getsize(path)} bytes")
    
    faces = ai_service.extract_faces(path)
    print(f"  Faces detected: {len(faces)}")
    for i, face in enumerate(faces):
        emb = face.get("embedding", [])
        print(f"    Face {i}: dim={len(emb)}, bbox={face.get('bbox')}, conf={face.get('confidence', 0):.3f}")
        print(f"    First 5 values: {emb[:5]}")
    print()

conn.close()
print("Done! If faces were detected, the model is working correctly.")
