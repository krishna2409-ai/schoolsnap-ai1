"""
Smart FAISS rebuild — uses DB cache where available, re-extracts where missing.
Ensures 100% coverage with maximum speed.
"""
import json
import os
import database as db
from ai_service import ai_service
from vector_store import vector_store

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INDEX_PATH = os.path.join(BASE_DIR, "faiss_store")

def build_smart(conn) -> int:
    """Build from cache but fill gaps via extraction."""
    rows = conn.execute(
        "SELECT id, event_id, original_path, preview_path FROM event_images"
    ).fetchall()
    
    indexed = 0
    total = len(rows)
    
    for i, row in enumerate(rows):
        image_id = row["id"]
        event_id = row["event_id"]
        image_path = row["original_path"]
        preview_path = row["preview_path"] or image_path
        
        # 1. Try cache
        faces = conn.execute(
            "SELECT embedding_json, bbox, confidence FROM event_faces WHERE image_id = ?", (image_id,)
        ).fetchall()
        
        if not faces and os.path.exists(image_path):
            # 2. Extract and cache if missing
            print(f"  [{i+1}/{total}] 🔍 Miss: {os.path.basename(image_path)} -> Extracting...", end=" ", flush=True)
            try:
                extracted = ai_service.extract_faces(image_path)
                print(f"found {len(extracted)} faces")
                for f in extracted:
                    conn.execute(
                        "INSERT INTO event_faces (image_id, embedding_json, bbox, confidence) VALUES (?,?,?,?)",
                        (image_id, json.dumps(f['embedding']), json.dumps(f['bbox']), f.get('confidence',0.0))
                    )
                conn.commit()
                # Re-fetch the newly added faces
                faces = conn.execute(
                    "SELECT embedding_json, bbox, confidence FROM event_faces WHERE image_id = ?", (image_id,)
                ).fetchall()
            except Exception as e:
                print(f"FAIL: {e}")
                continue
        elif faces:
            # print(f"  [{i+1}/{total}] ⚡ Cache: {os.path.basename(image_path)}")
            pass
        else:
            print(f"  [{i+1}/{total}] ⚠️ Missing file: {image_path}")

        # 3. Add to FAISS pool
        if faces:
            embeddings = [json.loads(f["embedding_json"]) for f in faces]
            metadata = [
                {
                    "image_path": preview_path,
                    "image_id": image_id,
                    "bbox": json.loads(f["bbox"]) if f["bbox"] else [0,0,0,0],
                    "event_id": event_id,
                    "source": "event",
                }
                for f in faces
            ]
            vector_store.add_embeddings(embeddings, metadata)
            indexed += len(faces)
            
    return indexed

def build_from_selfies(conn) -> int:
    """Add all selfie embeddings to FAISS."""
    rows = conn.execute(
        "SELECT s.id, s.file_path, s.embedding_json, c.name as child_name "
        "FROM selfies s JOIN children c ON c.id = s.child_id "
        "WHERE s.embedding_json IS NOT NULL"
    ).fetchall()

    indexed = 0
    for row in rows:
        try:
            emb = json.loads(row["embedding_json"])
        except Exception:
            continue
        if not emb or all(v == 0.0 for v in emb[:20]):
            continue
        vector_store.add_embeddings(
            [emb],
            [{
                "image_path": row["file_path"],
                "image_id": row["id"],
                "bbox": [0, 0, 0, 0],
                "event_id": "",
                "source": "selfie",
                "child_name": row["child_name"],
            }]
        )
        indexed += 1
    return indexed

def main():
    print("=" * 60)
    print("[SmartRebuild] Refreshing system index...")
    print("=" * 60)
    db.init_db()
    vector_store.index.reset()
    vector_store.metadata = []

    conn = db.get_connection()
    try:
        selfie_count = build_from_selfies(conn)
        event_count = build_smart(conn)
    finally:
        conn.close()

    os.makedirs(INDEX_PATH, exist_ok=True)
    vector_store.save(INDEX_PATH)
    print(f"\n[SmartRebuild] Done: {selfie_count} selfies, {event_count} event face vectors")
    print(f"[SmartRebuild] FAISS total: {vector_store.index.ntotal}")

if __name__ == "__main__":
    main()
