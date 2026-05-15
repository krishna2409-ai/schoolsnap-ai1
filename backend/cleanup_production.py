import sqlite3
import os
import shutil

BASE_DIR = r"D:\Projects\SNAP!\backend"
DB_PATH = os.path.join(BASE_DIR, "schoolsnap.db")
FAISS_PATH = os.path.join(BASE_DIR, "faiss_store")
IMAGES_DIR = os.path.join(BASE_DIR, "images", "previews")

def cleanup():
    print("--- STARTING PRODUCTION CLEANUP ---")
    
    # 1. Stop processing current index
    if os.path.exists(f"{FAISS_PATH}.index"):
        os.remove(f"{FAISS_PATH}.index")
    if os.path.exists(f"{FAISS_PATH}.meta"):
        os.remove(f"{FAISS_PATH}.meta")
    
    # 2. Delete Preview images to save space/clear cache
    if os.path.exists(IMAGES_DIR):
        print(f"Clearing previews from {IMAGES_DIR}...")
        shutil.rmtree(IMAGES_DIR)
        os.makedirs(IMAGES_DIR)

    # 3. Clean up database
    conn = sqlite3.connect(DB_PATH)
    try:
        # Delete Wedding event and its images
        WEDDING_EVENT_ID = "ac6c2215-ae8c-430a-99d7-f22b906e6ee4"
        print(f"Deleting event {WEDDING_EVENT_ID}...")
        conn.execute("DELETE FROM event_images WHERE event_id = ?", (WEDDING_EVENT_ID,))
        conn.execute("DELETE FROM events WHERE id = ?", (WEDDING_EVENT_ID,))
        
        # Reset Highlights event so it can be re-indexed
        HIGHLIGHTS_EVENT_ID = "bfc99c0a-824d-4642-bbf0-06dc05eb4f87"
        print(f"Resetting Highlights event {HIGHLIGHTS_EVENT_ID} for re-indexing...")
        conn.execute("DELETE FROM event_images WHERE event_id = ?", (HIGHLIGHTS_EVENT_ID,))
        conn.execute("DELETE FROM events WHERE id = ?", (HIGHLIGHTS_EVENT_ID,))
        
        conn.commit()
        print("Database cleaned.")
    finally:
        conn.close()

    print("--- CLEANUP COMPLETE ---")

if __name__ == "__main__":
    cleanup()
