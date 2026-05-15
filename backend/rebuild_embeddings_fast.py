import json
import os
import database as db
from ai_service import ai_service
from vector_store import vector_store

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INDEX_PATH = os.path.join(BASE_DIR, "faiss_store")

def process():
    db.init_db()
    vector_store.index.reset()
    vector_store.metadata = []
    
    conn = db.get_connection()
    try:
        print("[1] Selfies")
        rows = conn.execute(
            "SELECT s.id, s.file_path, s.embedding_json, c.name AS child_name "
            "FROM selfies s JOIN children c ON c.id = s.child_id "
            "WHERE s.embedding_json IS NOT NULL"
        ).fetchall()
        for row in rows:
            try:
                emb = json.loads(row["embedding_json"])
                if emb and len(emb) > 10 and not all(v == 0.0 for v in emb[:20]):
                    vector_store.add_embeddings(
                        [emb],
                        [{
                            "image_path": row["file_path"],
                            "image_id": row["id"],
                            "bbox": [0,0,0,0],
                            "event_id": "",
                            "source": "selfie",
                            "child_name": row["child_name"],
                        }]
                    )
            except Exception:
                pass
        
        print(f"[1] Added selfies. Total FAISS vectors: {vector_store.index.ntotal}")

        print("\n[2] Events")
        rows = conn.execute("SELECT id, event_id, original_path, preview_path FROM event_images").fetchall()
        
        # Group by origin path to avoid extracting same file multiple times
        grouped = {}
        for r in rows:
            grouped.setdefault(r["original_path"], []).append(r)
            
        print(f"Total event_images rows: {len(rows)}, Unique files: {len(grouped)}")
        
        processed_files = 0
        total_files = len(grouped)
        
        for path, instances in grouped.items():
            processed_files += 1
            if not os.path.exists(path):
                continue
                
            print(f"  [{processed_files}/{total_files}] Extracting {os.path.basename(path)}... ", end="", flush=True)
            faces = ai_service.extract_faces(path)
            print(f"{len(faces)} face(s)")
            
            if faces:
                embeddings = [f["embedding"] for f in faces]
                # Multiply for each instance
                for inst in instances:
                    meta = [
                        {
                            "image_path": inst["preview_path"] or path,
                            "image_id": inst["id"],
                            "bbox": f["bbox"],
                            "event_id": inst["event_id"],
                            "source": "event",
                        }
                        for f in faces
                    ]
                    vector_store.add_embeddings(embeddings, meta)
                    
                    conn.execute(
                        "UPDATE event_images SET faces_count = ? WHERE id = ?",
                        (len(faces), inst["id"])
                    )
        conn.commit()
    finally:
        conn.close()

    vector_store.save(INDEX_PATH)
    print(f"\n[DONE] FAISS index saved to {INDEX_PATH}. Total vectors: {vector_store.index.ntotal}")

if __name__ == "__main__":
    process()
