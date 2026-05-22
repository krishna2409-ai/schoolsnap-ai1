import sqlite3
import os

# Configuration
# Since we are in backend/scratch/, we go up one level to find the db
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "schoolsnap.db")

def finalize_paths():
    if not os.path.exists(DB_PATH):
        print(f"Error: Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print(f"--- Finalizing paths in {DB_PATH} ---")

    # Tables and columns to fix
    targets = [
        ("event_images", ["preview_path", "original_path"]),
        ("selfies", ["file_path"]),
        ("events", ["folder_path"])
    ]

    for table, columns in targets:
        print(f"Processing table: {table}")
        cursor.execute(f"SELECT id, {', '.join(columns)} FROM {table}")
        rows = cursor.fetchall()
        updated_count = 0
        
        for row in rows:
            updates = {}
            for col in columns:
                old_path = row[col]
                if not old_path:
                    continue
                
                # 1. Remove 'backend/' or 'backend\' prefix if present
                new_path = old_path
                if new_path.lower().startswith("backend\\"):
                    new_path = new_path[8:]
                elif new_path.lower().startswith("backend/"):
                    new_path = new_path[8:]
                
                # 2. Normalize slashes to forward slashes for cross-platform compatibility
                new_path = new_path.replace("\\", "/")
                
                if new_path != old_path:
                    updates[col] = new_path
            
            if updates:
                set_clause = ", ".join([f"{col} = ?" for col in updates.keys()])
                params = list(updates.values()) + [row['id']]
                cursor.execute(f"UPDATE {table} SET {set_clause} WHERE id = ?", params)
                updated_count += 1
        
        print(f"  Updated {updated_count} rows in {table}.")

    conn.commit()
    conn.close()
    print("--- Final Migration Complete ---")

if __name__ == "__main__":
    finalize_paths()
