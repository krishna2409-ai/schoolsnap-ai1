import os
import shutil

BASE_DIR = r"D:\Projects\SNAP!\backend"
FAISS_PATH = os.path.join(BASE_DIR, "faiss_store")

def reset():
    print("Stopping current indexing data...")
    if os.path.exists(f"{FAISS_PATH}.index"):
        os.remove(f"{FAISS_PATH}.index")
    if os.path.exists(f"{FAISS_PATH}.meta"):
        os.remove(f"{FAISS_PATH}.meta")
    
    # Optional: Clear processed image database records if you want a full fresh start
    # But for now, just clearing the vector store is enough to re-index correctly
    print("AI Vector index cleared. Please restart the backend and reload your folders.")

if __name__ == "__main__":
    reset()
