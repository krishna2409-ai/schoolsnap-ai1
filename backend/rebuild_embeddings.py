"""
Fast FAISS rebuild — reads selfie embeddings from DB (already extracted)
and re-extracts event image embeddings (needed since they aren't stored in DB).

Run this when FAISS index is lost/outdated.
"""
import json
import os
import database as db
from ai_service import ai_service
from vector_store import vector_store

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INDEX_PATH = os.path.join(BASE_DIR, "faiss_store")  # saves as faiss_store.index + faiss_store.meta


def index_selfies_from_db(conn) -> int:
    """Read selfie embeddings already stored in the DB and add to FAISS."""
    rows = conn.execute(
        "SELECT s.id, s.file_path, s.embedding_json, c.name AS child_name "
        "FROM selfies s JOIN children c ON c.id = s.child_id "
        "WHERE s.embedding_json IS NOT NULL"
    ).fetchall()

    indexed = 0
    for row in rows:
        try:
            emb = json.loads(row["embedding_json"])
        except Exception:
            continue
        if not emb or len(emb) < 10 or all(v == 0.0 for v in emb[:20]):
            continue

        file_path = row["file_path"]
        if not os.path.exists(file_path):
            continue

        vector_store.add_embeddings(
            [emb],
            [{
                "image_path": file_path,
                "image_id": row["id"],
                "bbox": [0, 0, 0, 0],
                "event_id": "",
                "source": "selfie",
                "child_name": row["child_name"],
            }]
        )
        indexed += 1
        print(f"  [Selfie] ✅ {row['child_name']} -> {os.path.basename(file_path)}")

    return indexed


def index_events_via_extraction(conn) -> int:
    """Re-extract face embeddings from event images and add to FAISS."""
    rows = conn.execute(
        "SELECT id, event_id, original_path, preview_path FROM event_images ORDER BY created_at ASC"
    ).fetchall()

    indexed = 0
    total = len(rows)
    for i, row in enumerate(rows):
        image_id = row["id"]
        event_id = row["event_id"]
        image_path = row["original_path"]
        preview_path = row["preview_path"] or image_path

        if not os.path.exists(image_path):
            print(f"  [Event {i+1}/{total}] ⚠️  Missing: {image_path}")
            continue

        # Check if faces are already stored for this image ID
        existing_faces = conn.execute(
            "SELECT embedding_json, bbox, confidence FROM event_faces WHERE image_id = ?", (image_id,)
        ).fetchall()

        if existing_faces:
            print(f"  [Event {i+1}/{total}] ⚡ Using {len(existing_faces)} cached faces for {os.path.basename(image_path)}", flush=True)
            embeddings = [json.loads(f["embedding_json"]) for f in existing_faces]
            metadata = [
                {
                    "image_path": preview_path,
                    "image_id": image_id,
                    "bbox": json.loads(f["bbox"]) if f["bbox"] else [0,0,0,0],
                    "event_id": event_id,
                    "source": "event",
                }
                for f in existing_faces
            ]
            vector_store.add_embeddings(embeddings, metadata)
            indexed += len(existing_faces)
            continue

        print(f"  [Event {i+1}/{total}] 🔍 Extracting from {os.path.basename(image_path)}...", end=" ", flush=True)
        try:
            faces = ai_service.extract_faces(image_path)
            print(f"{len(faces)} face(s)")
            if faces:
                embeddings = []
                metadata = []
                for f in faces:
                    emb = f["embedding"]
                    bbox = f["bbox"]
                    conf = f.get("confidence", 0.0)
                    
                    # Persist to DB
                    conn.execute(
                        "INSERT INTO event_faces (image_id, embedding_json, bbox, confidence) VALUES (?, ?, ?, ?)",
                        (image_id, json.dumps(emb), json.dumps(bbox), conf)
                    )
                    
                    # Add to FAISS pool
                    embeddings.append(emb)
                    metadata.append({
                        "image_path": preview_path,
                        "image_id": image_id,
                        "bbox": bbox,
                        "event_id": event_id,
                        "source": "event",
                    })
                
                vector_store.add_embeddings(embeddings, metadata)
                conn.execute(
                    "UPDATE event_images SET faces_count = ? WHERE id = ?",
                    (len(faces), image_id)
                )
                conn.commit()
                indexed += len(faces)
        except Exception as e:
            print(f"ERROR: {e}")

    return indexed


def main():
    print("=" * 60)
    print("[Rebuild] Starting FAISS index rebuild...")
    print("=" * 60)

    db.init_db()

    # Reset
    vector_store.index.reset()
    vector_store.metadata = []

    conn = db.get_connection()
    try:
        print(f"\n[Phase 1] Indexing selfies from DB embeddings...")
        selfie_count = index_selfies_from_db(conn)
        print(f"  -> {selfie_count} selfies indexed\n")

        print(f"[Phase 2] Re-extracting event image embeddings...")
        event_count = index_events_via_extraction(conn)
        print(f"  -> {event_count} event face vectors indexed\n")
    finally:
        conn.close()

    # Save: creates faiss_store.index + faiss_store.meta
    vector_store.save(INDEX_PATH)

    print("=" * 60)
    print(f"[Rebuild] Selfie vectors:  {selfie_count}")
    print(f"[Rebuild] Event vectors:   {event_count}")
    print(f"[Rebuild] FAISS total:     {vector_store.index.ntotal}")
    print(f"[Rebuild] Saved to:        {INDEX_PATH}.index / .meta")
    print("=" * 60)


if __name__ == "__main__":
    main()
