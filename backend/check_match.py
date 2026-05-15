import os, json, sqlite3, numpy as np
from ai_service import ai_service

DB_PATH = r"backend/schoolsnap.db"
target_id = "2b7f4215-eec4-4e00-9e85-d11305265332"
selfie_path = os.path.join("backend", "images", "selfies", f"{target_id}.jpg")

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
row = conn.execute("SELECT embedding_json FROM selfies WHERE id=?", (target_id,)).fetchone()
old_emb = json.loads(row["embedding_json"])

print(f"File exists: {os.path.exists(selfie_path)}")
faces = ai_service.extract_faces(selfie_path)

if faces:
    new_emb = faces[0]["embedding"]
    print(f"Old first 3: {old_emb[:3]}")
    print(f"New first 3: {new_emb[:3]}")
    
    # Cosine similarity
    sim = np.dot(old_emb, new_emb)
    print(f"Cosine Similarity: {sim:.4f}")
else:
    print("New model failed to detect face in selfie!")

conn.close()
