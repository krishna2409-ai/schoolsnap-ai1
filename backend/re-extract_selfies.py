import os
import json
import sqlite3
from ai_service import ai_service

DB_PATH = r"backend/schoolsnap.db"

def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    rows = conn.execute("SELECT id, file_path FROM selfies").fetchall()
    print(f"Re-extracting {len(rows)} selfies...")
    
    count = 0
    errors = 0
    for row in rows:
        selfie_id = row["id"]
        file_path = row["file_path"]
        
        # Ensure path is absolute for script
        abs_path = file_path
        if not os.path.isabs(abs_path):
            abs_path = os.path.join("backend", file_path)
            
        if not os.path.exists(abs_path):
            print(f"  [Error] File not found: {abs_path}")
            errors += 1
            continue
            
        try:
            faces = ai_service.extract_faces(abs_path)
            if faces:
                # Use the largest face
                main_face = max(faces, key=lambda x: (x['bbox'][2] - x['bbox'][0]) * (x['bbox'][3] - x['bbox'][1]))
                embedding_json = json.dumps(main_face['embedding'])
                
                conn.execute(
                    "UPDATE selfies SET embedding_json = ? WHERE id = ?",
                    (embedding_json, selfie_id)
                )
                count += 1
                if count % 5 == 0:
                    print(f"  Processed {count}/{len(rows)}...")
            else:
                print(f"  [Warn] No face found in {os.path.basename(abs_path)}")
                # Reset embedding to NULL if no face found, to avoid stale mismatches
                conn.execute("UPDATE selfies SET embedding_json = NULL WHERE id = ?", (selfie_id,))
                errors += 1
        except Exception as e:
            print(f"  [Error] Failed to process {os.path.basename(abs_path)}: {e}")
            errors += 1
            
    conn.commit()
    conn.close()
    print(f"\nDone! Re-extracted {count} selfies correctly. Errors/No-faces: {errors}")

if __name__ == "__main__":
    main()
