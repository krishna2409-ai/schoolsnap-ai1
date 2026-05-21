import sqlite3
import os
import json
from typing import Optional, List, Dict

DB_PATH = os.path.join(os.path.dirname(__file__), "schoolsnap.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE TABLE IF NOT EXISTS children (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        
        CREATE TABLE IF NOT EXISTS selfies (
            id TEXT PRIMARY KEY,
            child_id TEXT NOT NULL,
            file_path TEXT NOT NULL,
            embedding_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (child_id) REFERENCES children(id)
        );
        
        CREATE TABLE IF NOT EXISTS events (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            folder_path TEXT,
            status TEXT DEFAULT 'pending',
            total_images INTEGER DEFAULT 0,
            processed_images INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE TABLE IF NOT EXISTS event_images (
            id TEXT PRIMARY KEY,
            event_id TEXT NOT NULL,
            original_path TEXT NOT NULL,
            preview_path TEXT,
            filename TEXT NOT NULL,
            faces_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (event_id) REFERENCES events(id)
        );

        CREATE TABLE IF NOT EXISTS event_faces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            image_id TEXT NOT NULL,
            embedding_json TEXT NOT NULL,
            bbox TEXT, -- store as json [x, y, w, h] or similar
            confidence REAL,
            FOREIGN KEY (image_id) REFERENCES event_images(id)
        );
        
        CREATE TABLE IF NOT EXISTS purchases (
            user_id TEXT NOT NULL,
            image_id TEXT NOT NULL,
            purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, image_id),
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (image_id) REFERENCES event_images(id)
        );
    """)
    
    conn.commit()
    conn.close()

# --- User operations ---

def create_user(user_id: str, name: str, email: str, password_hash: str):
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO users (id, name, email, password_hash) VALUES (?, ?, ?, ?)",
            (user_id, name, email, password_hash)
        )
        conn.commit()
    finally:
        conn.close()

def get_user_by_email(email: str) -> Optional[dict]:
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def get_user_by_id(user_id: str) -> Optional[dict]:
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

# --- Children operations ---

def create_child(child_id: str, user_id: str, name: str):
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO children (id, user_id, name) VALUES (?, ?, ?)",
            (child_id, user_id, name)
        )
        conn.commit()
    finally:
        conn.close()

def get_children(user_id: str) -> List[dict]:
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM children WHERE user_id = ?", (user_id,)).fetchall()
        children = []
        for row in rows:
            child = dict(row)
            selfies = conn.execute(
                "SELECT id, file_path FROM selfies WHERE child_id = ?", (child["id"],)
            ).fetchall()
            child["selfies"] = []
            for s in selfies:
                # If file exists, return URL, else return indicator
                file_basename = os.path.basename(s['file_path'])
                has_file = os.path.exists(os.path.join(os.path.dirname(__file__), s['file_path']))
                child["selfies"].append({
                    "id": s["id"], 
                    "url": f"/images/selfies/{file_basename}" if has_file else None,
                    "has_image": has_file
                })
            children.append(child)
        return children
    finally:
        conn.close()

def get_child(child_id: str, user_id: str) -> Optional[dict]:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM children WHERE id = ? AND user_id = ?", (child_id, user_id)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_child_by_name(user_id: str, name: str) -> Optional[dict]:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM children WHERE user_id = ? AND name = ?",
            (user_id, name),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_dataset_people(user_id: str) -> List[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT c.id, c.name, COUNT(s.id) AS image_count
            FROM children c
            LEFT JOIN selfies s ON s.child_id = c.id
            WHERE c.user_id = ?
            GROUP BY c.id, c.name
            ORDER BY c.created_at ASC
            """,
            (user_id,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_dataset_face_records(user_id: str) -> List[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT
                s.id AS selfie_id,
                s.file_path,
                s.embedding_json,
                c.id AS person_id,
                c.name AS person_name
            FROM selfies s
            INNER JOIN children c ON c.id = s.child_id
            WHERE c.user_id = ? AND s.embedding_json IS NOT NULL
            ORDER BY s.created_at ASC
            """,
            (user_id,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()

def delete_child(child_id: str, user_id: str) -> bool:
    """Deletes a child, their record, and all their selfie files."""
    conn = get_connection()
    try:
        # 1. Verify ownership
        row = conn.execute(
            "SELECT id FROM children WHERE id = ? AND user_id = ?", (child_id, user_id)
        ).fetchone()
        if not row:
            return False
            
        # 2. Get and delete physical selfie files
        selfies = conn.execute(
            "SELECT file_path FROM selfies WHERE child_id = ?", (child_id,)
        ).fetchall()
        for s in selfies:
            try:
                if os.path.exists(s["file_path"]):
                    os.remove(s["file_path"])
            except Exception as e:
                print(f"[DB] Error deleting selfie file: {e}")
        
        # 3. Clean up records
        conn.execute("DELETE FROM selfies WHERE child_id = ?", (child_id,))
        conn.execute("DELETE FROM children WHERE id = ? AND user_id = ?", (child_id, user_id))
        conn.commit()
        return True
    finally:
        conn.close()

# --- Selfie operations ---

def add_selfie(selfie_id: str, child_id: str, file_path: str, embedding_json: str = None):
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO selfies (id, child_id, file_path, embedding_json) VALUES (?, ?, ?, ?)",
            (selfie_id, child_id, file_path, embedding_json)
        )
        conn.commit()
    finally:
        conn.close()

def get_selfies(child_id: str) -> List[dict]:
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM selfies WHERE child_id = ?", (child_id,)).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()

def get_selfie_embeddings(child_id: str) -> List[List[float]]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT embedding_json FROM selfies WHERE child_id = ? AND embedding_json IS NOT NULL",
            (child_id,)
        ).fetchall()
        embeddings = []
        for row in rows:
            if row["embedding_json"]:
                embeddings.append(json.loads(row["embedding_json"]))
        return embeddings
    finally:
        conn.close()

def delete_selfie(selfie_id: str, child_id: str) -> bool:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT file_path FROM selfies WHERE id = ? AND child_id = ?", (selfie_id, child_id)
        ).fetchone()
        if row:
            # Delete file
            if os.path.exists(row["file_path"]):
                os.remove(row["file_path"])
            conn.execute("DELETE FROM selfies WHERE id = ? AND child_id = ?", (selfie_id, child_id))
            conn.commit()
            return True
        return False
    finally:
        conn.close()

# --- Event operations ---

def create_event(event_id: str, name: str, folder_path: str, total_images: int):
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO events (id, name, folder_path, status, total_images) VALUES (?, ?, ?, 'processing', ?)",
            (event_id, name, folder_path, total_images)
        )
        conn.commit()
    finally:
        conn.close()

def update_event_progress(event_id: str, processed: int, status: str = None):
    conn = get_connection()
    try:
        if status:
            conn.execute(
                "UPDATE events SET processed_images = ?, status = ? WHERE id = ?",
                (processed, status, event_id)
            )
        else:
            conn.execute(
                "UPDATE events SET processed_images = ? WHERE id = ?",
                (processed, event_id)
            )
        conn.commit()
    finally:
        conn.close()

def get_event(event_id: str) -> Optional[dict]:
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def get_events() -> List[dict]:
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM events ORDER BY created_at DESC").fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()

# --- Event Image operations ---

def add_event_image(image_id: str, event_id: str, original_path: str, preview_path: str, filename: str, faces_count: int):
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO event_images (id, event_id, original_path, preview_path, filename, faces_count) VALUES (?, ?, ?, ?, ?, ?)",
            (image_id, event_id, original_path, preview_path, filename, faces_count)
        )
        conn.commit()
    finally:
        conn.close()

def add_event_face(image_id: str, embedding_json: str, bbox_json: str, confidence: float):
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO event_faces (image_id, embedding_json, bbox, confidence) VALUES (?, ?, ?, ?)",
            (image_id, embedding_json, bbox_json, confidence)
        )
        conn.commit()
    finally:
        conn.close()

def get_event_image(image_id: str) -> Optional[dict]:
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM event_images WHERE id = ?", (image_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

# --- Purchase operations ---

def add_purchase(user_id: str, image_id: str):
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO purchases (user_id, image_id) VALUES (?, ?)",
            (user_id, image_id)
        )
        conn.commit()
    finally:
        conn.close()

def is_purchased(user_id: str, image_id: str) -> bool:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT 1 FROM purchases WHERE user_id = ? AND image_id = ?",
            (user_id, image_id)
        ).fetchone()
        return row is not None
    finally:
        conn.close()

def get_user_purchases(user_id: str) -> List[str]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT image_id FROM purchases WHERE user_id = ?", (user_id,)
        ).fetchall()
        return [row["image_id"] for row in rows]
    finally:
        conn.close()
