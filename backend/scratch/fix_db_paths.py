import sqlite3
import os

# Configuration
DB_PATH = os.path.join("backend", "schoolsnap.db")
# The absolute prefix to remove
ABS_PREFIX = "D:\\Projects\\SNAP!\\" 

def fix_paths():
    if not os.path.exists(DB_PATH):
        print(f"Error: Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print(f"--- Fixing paths in {DB_PATH} ---")

    # 1. Fix event_images (preview_path and original_path)
    print("Updating event_images...")
    cursor.execute("SELECT id, preview_path, original_path FROM event_images")
    rows = cursor.fetchall()
    updated_count = 0
    for row in rows:
        p_path = row['preview_path']
        o_path = row['original_path']
        
        new_p = p_path.replace(ABS_PREFIX, "") if p_path and p_path.startswith(ABS_PREFIX) else p_path
        new_o = o_path.replace(ABS_PREFIX, "") if o_path and o_path.startswith(ABS_PREFIX) else o_path
        
        if new_p != p_path or new_o != o_path:
            cursor.execute(
                "UPDATE event_images SET preview_path = ?, original_path = ? WHERE id = ?",
                (new_p, new_o, row['id'])
            )
            updated_count += 1
    print(f"Fixed {updated_count} event_images paths.")

    # 2. Fix selfies (file_path)
    print("Updating selfies...")
    cursor.execute("SELECT id, file_path FROM selfies")
    rows = cursor.fetchall()
    updated_count = 0
    for row in rows:
        f_path = row['file_path']
        new_f = f_path.replace(ABS_PREFIX, "") if f_path and f_path.startswith(ABS_PREFIX) else f_path
        
        if new_f != f_path:
            cursor.execute(
                "UPDATE selfies SET file_path = ? WHERE id = ?",
                (new_f, row['id'])
            )
            updated_count += 1
    print(f"Fixed {updated_count} selfie paths.")

    # 3. Fix events (folder_path)
    print("Updating events...")
    cursor.execute("SELECT id, folder_path FROM events")
    rows = cursor.fetchall()
    updated_count = 0
    for row in rows:
        f_path = row['folder_path']
        new_f = f_path.replace(ABS_PREFIX, "") if f_path and f_path.startswith(ABS_PREFIX) else f_path
        
        if new_f != f_path:
            cursor.execute(
                "UPDATE events SET folder_path = ? WHERE id = ?",
                (new_f, row['id'])
            )
            updated_count += 1
    print(f"Fixed {updated_count} event folder paths.")

    conn.commit()
    conn.close()
    print("--- Migration Complete ---")

if __name__ == "__main__":
    fix_paths()
