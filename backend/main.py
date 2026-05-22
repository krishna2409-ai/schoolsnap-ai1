from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
import shutil
import os
import uuid
import glob
import json
import numpy as np
from typing import List, Optional, Dict
from datetime import datetime, timedelta

from jose import JWTError, jwt
import bcrypt
from contextlib import asynccontextmanager

import database as db
from ai_service import ai_service
from vector_store import vector_store

# ─── Config ───────────────────────────────────────────────────────────
SECRET_KEY = os.getenv("SCHOOLSNAP_SECRET_KEY", "schoolsnap-dev-secret")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 30
STRICT_MATCH_THRESHOLD = 0.55  # L2 distance squared (lower = better)
MAX_MATCH_RESULTS = 20
DEMO_DATASET_EMAIL = "dataset-admin@demo.local"
DEMO_DATASET_PASSWORD = "demo123"
DEMO_DATASET_NAME = "Dataset Admin"
DATASET_MAX_DISTANCE = 1.25
DATASET_TOP_K = 100
PARENT_FACE_ACCEPT_DISTANCE = 1.2

DEMO_PARENT_ACCOUNTS = [
    {
        "registration_number": "REG1001",
        "dob": "2014-05-12",
        "parent_name": "Ravi Kumar",
        "child_name": "Aarav Kumar",
    },
    {
        "registration_number": "REG1002",
        "dob": "2013-09-22",
        "parent_name": "Sneha Reddy",
        "child_name": "Isha Reddy",
    },
    {
        "registration_number": "REG1003",
        "dob": "2015-01-18",
        "parent_name": "Vikram Rao",
        "child_name": "Vihaan Rao",
    },
]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "images", "events")
PREVIEW_DIR = os.path.join(BASE_DIR, "images", "previews")
SELFIES_DIR = os.path.join(BASE_DIR, "images", "selfies")
EVENT_UPLOAD_DIR = os.path.join(BASE_DIR, "event_uploads_tmp")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(PREVIEW_DIR, exist_ok=True)
os.makedirs(SELFIES_DIR, exist_ok=True)
os.makedirs(EVENT_UPLOAD_DIR, exist_ok=True)

# Temporary upload registry for two-step event ingestion API.
pending_event_uploads: Dict[str, dict] = {}


def to_db_path(abs_path: str) -> str:
    """Convert an absolute path to a relative path from BASE_DIR for DB storage."""
    try:
        return os.path.relpath(abs_path, BASE_DIR).replace("\\", "/")
    except ValueError:
        # If paths are on different drives in Windows
        return abs_path.replace("\\", "/")

# ─── Auth helpers ─────────────────────────────────────────────────────

def get_password_hash(password: str) -> str:
    # Bcrypt has a 72-byte limit, and modern versions throw ValueError if exceeded.
    pwd_bytes = password.encode('utf-8')[:72]
    return bcrypt.hashpw(pwd_bytes, bcrypt.gensalt()).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        pwd_bytes = plain_password.encode('utf-8')[:72]
        return bcrypt.checkpw(pwd_bytes, hashed_password.encode('utf-8'))
    except Exception:
        return False


def ensure_dataset_user_id() -> str:
    user = db.get_user_by_email(DEMO_DATASET_EMAIL)
    if user:
        return user["id"]

    user_id = str(uuid.uuid4())
    db.create_user(
        user_id,
        DEMO_DATASET_NAME,
        DEMO_DATASET_EMAIL,
        get_password_hash(DEMO_DATASET_PASSWORD),
    )
    return user_id


def get_largest_face(faces: List[dict]) -> Optional[dict]:
    if not faces:
        return None
    return max(
        faces,
        key=lambda x: (x["bbox"][2] - x["bbox"][0]) * (x["bbox"][3] - x["bbox"][1]),
    )


def registration_to_email(registration_number: str) -> str:
    return f"{registration_number.strip().lower()}@schoolsnap.local"


def get_user_by_registration(registration_number: str) -> Optional[dict]:
    if not registration_number.strip():
        return None
    return db.get_user_by_email(registration_to_email(registration_number))


def ensure_demo_parent_accounts():
    for account in DEMO_PARENT_ACCOUNTS:
        email = registration_to_email(account["registration_number"])
        user = db.get_user_by_email(email)

        if not user:
            user_id = str(uuid.uuid4())
            db.create_user(
                user_id,
                account["parent_name"],
                email,
                get_password_hash(account["dob"]),
            )
            user = db.get_user_by_id(user_id)

        user_id = user["id"]
        existing_child = db.get_child_by_name(user_id, account["child_name"])
        if not existing_child:
            db.create_child(str(uuid.uuid4()), user_id, account["child_name"])

def seed_demo_enrollment_photos():
    """Seed demo enrollment data with real test photos for investor demo."""
    test_images_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "test")
    if not os.path.exists(test_images_dir):
        return
    
    # Use first test image for each demo account
    test_images = [
        "DSC00640.jpg",
        "DSC00663.jpg", 
        "DSC01601.jpg"
    ]
    
    for idx, account in enumerate(DEMO_PARENT_ACCOUNTS):
        email = registration_to_email(account["registration_number"])
        user = db.get_user_by_email(email)
        if not user:
            continue
        
        user_id = user["id"]
        children = db.get_children(user_id)
        if not children or len(children) == 0:
            continue
        
        child_id = children[0]["id"]
        
        # Check if already has selfies
        existing_selfies = db.get_selfies(child_id)
        if existing_selfies and len(existing_selfies) > 0:
            continue  # Already seeded
        
        # Copy test image for this demo account
        test_img_idx = idx % len(test_images)
        test_img = test_images[test_img_idx]
        test_img_path = os.path.join(test_images_dir, test_img)
        
        if not os.path.exists(test_img_path):
            continue
        
        try:
            # Generate face embeddings from test image
            faces = ai_service.extract_faces(test_img_path)
            
            if len(faces) == 0:
                continue
            
            # Use first face detected as enrollment photo
            face_data = faces[0]
            embedding = np.array(face_data["embedding"]).astype(np.float32)
            
            # Save to selfies directory
            selfie_id = str(uuid.uuid4())
            selfie_filename = f"{selfie_id}.jpg"
            selfie_path = os.path.join(SELFIES_DIR, selfie_filename)
            
            # Copy image
            shutil.copy(test_img_path, selfie_path)
            
            # Save to database
            embedding_json = json.dumps(embedding.tolist())
            db.add_selfie(selfie_id, child_id, selfie_path, embedding_json)
            
            # Add to vector store
            vector_store.add_embeddings([embedding.tolist()], [{"image_path": selfie_path, "image_id": selfie_id}])
            
            print(f"[Demo] Seeded enrollment photo for {account['child_name']} ({selfie_filename})")
        except Exception as e:
            print(f"[Demo] Failed to seed enrollment for {account['child_name']}: {e}")



def get_primary_child(user_id: str) -> Optional[dict]:
    children = db.get_children(user_id)
    if not children:
        return None
    return children[0]

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup — wrapped in try/except to NEVER crash the server
    try:
        db.init_db()
        print("[Startup] Database initialized")
    except Exception as e:
        print(f"[Startup] WARNING: Database init failed: {e}")

    try:
        ensure_demo_parent_accounts()
        print("[Startup] Demo parent accounts ensured")
    except Exception as e:
        print(f"[Startup] WARNING: Demo accounts failed: {e}")

    try:
        seed_demo_enrollment_photos()
        print("[Startup] Demo enrollment seeding complete")
    except Exception as e:
        print(f"[Startup] WARNING: Demo enrollment seeding failed (non-fatal): {e}")

    try:
        index_path = os.path.join(BASE_DIR, "faiss_store")
        vector_store.load(index_path)
        print(f"[Startup] FAISS index loaded: {vector_store.index.ntotal} vectors")
    except Exception as e:
        print(f"[Startup] WARNING: FAISS load failed: {e}")

    print("[Startup] ✅ Server ready")
    yield
    # Shutdown
    pass

# ─── App ──────────────────────────────────────────────────────────────
app = FastAPI(title="SchoolSnap AI", version="1.0.0", lifespan=lifespan)

# CORS Configuration
# In production, we explicitly allow the frontend URL to avoid CORS blocking.
frontend_url = "https://frontend-v1-production-d3d2.up.railway.app"
env_origins = os.getenv("CORS_ORIGINS", "*")

if env_origins == "*":
    origins = ["*"]
else:
    origins = [o.strip() for o in env_origins.split(",")]

# Ensure the production frontend is always allowed
if frontend_url not in origins and "*" not in origins:
    origins.append(frontend_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True if "*" not in origins else False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Auth helpers ─────────────────────────────────────────────────────

def create_token(user_id: str) -> str:
    expire = datetime.utcnow() + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    return jwt.encode({"sub": user_id, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str) -> Optional[str]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None

async def get_current_user(token: str = Form(None)):
    """Extract user from token form field. For endpoints that use Form data."""
    if not token:
        raise HTTPException(status_code=401, detail="Token required")
    user_id = verify_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = db.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


# ─── Health Check ─────────────────────────────────────────────────────

@app.get("/health")
async def health_check():
    """Health check endpoint for container orchestration and load balancers."""
    try:
        faiss_count = vector_store.index.ntotal if vector_store.index else 0
    except Exception:
        faiss_count = -1
    return {
        "status": "healthy",
        "service": "SchoolSnap AI",
        "version": "1.0.0-bypass-v2",
        "faiss_vectors": faiss_count,
    }


# ─── Auth Endpoints ──────────────────────────────────────────────────

@app.post("/register")
async def register(name: str = Form(...), email: str = Form(...), password: str = Form(...)):
    existing = db.get_user_by_email(email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user_id = str(uuid.uuid4())
    password_hash = get_password_hash(password)
    db.create_user(user_id, name, email, password_hash)
    
    token = create_token(user_id)
    return {"user_id": user_id, "name": name, "email": email, "token": token}

@app.post("/login")
async def login(email: str = Form(...), password: str = Form(...)):
    user = db.get_user_by_email(email)
    if not user or not verify_password(password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = create_token(user["id"])
    return {
        "user_id": user["id"],
        "name": user["name"],
        "email": user["email"],
        "token": token
    }


@app.get("/demo/credentials")
async def demo_credentials():
    # Demo helper endpoint. Remove in production.
    return [
        {
            "registration_number": a["registration_number"],
            "dob": a["dob"],
            "child_name": a["child_name"],
        }
        for a in DEMO_PARENT_ACCOUNTS
    ]


@app.post("/parent-login")
@app.post("/parent/access-login")
async def parent_login(
    registration_number: str = Form(...),
    dob: str = Form(...),
):
    user = get_user_by_registration(registration_number)
    if not user or not verify_password(dob, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid registration number or date of birth")

    child = get_primary_child(user["id"])
    if not child:
        raise HTTPException(status_code=400, detail="No child mapped to this account")

    token = create_token(user["id"])
    reg_digits = ''.join(filter(str.isdigit, registration_number))
    mock_phone = f"+91 90000 {reg_digits.zfill(5)}" if reg_digits else "+91 90000 00000"
    
    return {
        "token": token,
        "registration_number": registration_number.strip().upper(),
        "parent_name": user["name"],
        "child_id": child["id"],
        "child_name": child["name"],
        "email": user["email"],
        "phone": mock_phone,
    }


@app.post("/school/upload-enrollment")
@app.post("/registration/upload-photos")
async def enrollment_upload_photos(
    registration_number: str = Form(...),
    child_name: str = Form(None),
    files: List[UploadFile] = File(...),
):
    if not files:
        raise HTTPException(status_code=400, detail="At least one image is required")

    user = get_user_by_registration(registration_number)
    if not user:
        raise HTTPException(status_code=404, detail="Unknown registration number")

    chosen_child = None
    if child_name and child_name.strip():
        chosen_child = db.get_child_by_name(user["id"], child_name.strip())
        if not chosen_child:
            child_id = str(uuid.uuid4())
            db.create_child(child_id, user["id"], child_name.strip())
            chosen_child = db.get_child(child_id, user["id"])
    else:
        chosen_child = get_primary_child(user["id"])

    if not chosen_child:
        raise HTTPException(status_code=400, detail="No child found for this registration number")

    uploaded = 0
    valid_faces = 0
    child_id = chosen_child["id"]

    for file in files:
        ext = os.path.splitext(file.filename or "")[1].lower() or ".jpg"
        selfie_id = str(uuid.uuid4())
        file_path = os.path.join(SELFIES_DIR, f"{selfie_id}{ext}")

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        uploaded += 1

        # Extract real face embedding
        try:
            faces = ai_service.extract_faces(file_path)
            is_cloud = os.getenv("RAILWAY_STATIC_URL") or os.getenv("RAILWAY_SERVICE_ID") or os.path.exists("/.dockerenv")
            default_bypass = "true" if is_cloud else "false"
            bypass_ai = os.getenv("BYPASS_HEAVY_AI", default_bypass).lower() == "true"
            if not faces and bypass_ai:
                print(f"[ENROLL] AI bypassed. Generating mock embedding for {file.filename}")
                faces = [{
                    'bbox': [0, 0, 100, 100],
                    'embedding': [0.0] * 512,
                    'confidence': 1.0
                }]
                
            main_face = get_largest_face(faces)
            if not main_face or not main_face.get("embedding"):
                print(f"[ENROLL] No face detected in {file.filename}, skipping")
                os.remove(file_path)  # Remove the file if no face found
                continue

            embedding = main_face["embedding"]
            db.add_selfie(selfie_id, child_id, file_path, json.dumps(embedding))
            
            # Also add to FAISS so this selfie is searchable during scan
            vector_store.add_embeddings(
                [embedding],
                [{
                    "image_path": file_path,
                    "image_id": selfie_id,
                    "bbox": main_face.get("bbox", [0, 0, 0, 0]),
                    "event_id": "",
                    "source": "selfie",
                    "child_name": chosen_child["name"],
                }]
            )
            
            valid_faces += 1
            print(f"[ENROLL] ✅ Face enrolled + indexed: {file.filename} (conf={main_face.get('confidence', 0):.3f})")
        except Exception as e:
            print(f"[ENROLL] ❌ Error extracting from {file.filename}: {e}")
            os.remove(file_path)  # Remove the file on error
            continue

    if valid_faces == 0:
        raise HTTPException(status_code=400, detail="No valid face found in uploaded images")

    # Save updated FAISS index
    index_path = os.path.join(BASE_DIR, "faiss_store")
    vector_store.save(index_path)
    print(f"[ENROLL] FAISS index saved: {vector_store.index.ntotal} total vectors")

    return {
        "status": "ok",
        "registration_number": registration_number.strip().upper(),
        "child_name": chosen_child["name"],
        "uploaded": uploaded,
        "valid_faces": valid_faces,
    }


@app.post("/parent/scan-and-match")
async def parent_scan_and_match(
    token: str = Form(...),
    file: UploadFile = File(...),
):
    user_id = verify_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    child = get_primary_child(user_id)
    if not child:
        raise HTTPException(status_code=400, detail="No child mapped for this account")

    temp_file = os.path.join(EVENT_UPLOAD_DIR, f"parent_scan_{uuid.uuid4().hex}.jpg")
    try:
        with open(temp_file, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        print(f"[SCAN] Saved scan image: {temp_file} ({os.path.getsize(temp_file)} bytes)")

        # ── Step 1: Extract face embedding from scanned photo ──
        query_embedding = None
        try:
            faces = ai_service.extract_faces(temp_file)
            main_face = get_largest_face(faces)
            if main_face and main_face.get("embedding"):
                query_embedding = main_face["embedding"]
                print(f"[SCAN] ✅ Face extracted. Embedding dim: {len(query_embedding)}, confidence: {main_face.get('confidence', 0):.3f}")
            else:
                print("[SCAN] ❌ No face detected in scanned image. Falling back to demo mode.")
        except Exception as e:
            print(f"[SCAN] ❌ Face extraction exception: {e}. Falling back to demo mode.")

        matches = []
        if query_embedding is not None:
            # ── Step 2: Search FAISS for event photos containing this face directly ──
            print(f"[SCAN] Searching FAISS with scanned face embedding ({vector_store.index.ntotal} indexed)")
            try:
                event_results = vector_store.search(
                    query_embeddings=[query_embedding],
                    top_k=DATASET_TOP_K,
                    threshold=PARENT_FACE_ACCEPT_DISTANCE,
                    min_support=1,
                )
                print(f"[SCAN] FAISS returned {len(event_results)} event photo matches")

                seen_ids = set()
                for result in event_results:
                    img_id = result.get("image_id", "")
                    if img_id in seen_ids:
                        continue
                    seen_ids.add(img_id)

                    source = result.get("source", "event")
                    image_path = result.get("image_path", "")

                    if source == "selfie":
                        # Skip reference selfies in the matches results, only return actual event photos
                        continue
                    else:
                        # Event image — look up in event_images table
                        conn = db.get_connection()
                        img_row = conn.execute(
                            "SELECT preview_path, original_path FROM event_images WHERE id = ?", (img_id,)
                        ).fetchone()
                        conn.close()
                        if not img_row:
                            continue

                        preview_path = img_row["preview_path"] or img_row["original_path"]
                        abs_preview_path = preview_path if os.path.isabs(preview_path) else os.path.join(BASE_DIR, preview_path)
                        if not os.path.exists(abs_preview_path):
                            continue

                        basename = os.path.basename(preview_path)
                        if "previews" in preview_path:
                            preview_url = f"/images/previews/{basename}"
                        elif "events" in preview_path:
                            preview_url = f"/images/events/{basename}"
                        else:
                            preview_url = f"/images/previews/{basename}"

                    # L2 distance to confidence: lower distance = higher confidence
                    l2_dist = result.get("confidence", 1.0)
                    confidence = round(max(0, min(99.9, (1 - l2_dist) * 100)), 1)

                    matches.append({
                        "id": img_id,
                        "preview_url": preview_url,
                        "confidence_pct": confidence,
                        "source": source,
                    })
                print(f"[SCAN] ✅ TOTAL REAL MATCHES: {len(matches)} event photos found")
            except Exception as e:
                print(f"[SCAN] ❌ FAISS search exception: {e}. Falling back to demo mode.")

        # Demo fallback: if no FAISS matches, return sample event photos
        if len(matches) == 0:
            print(f"[SCAN] No FAISS matches found. Demo fallback: returning sample event photos.")
            conn = db.get_connection()
            # Find the event_id of the most recently uploaded image to prioritize latest event photos
            latest_img = conn.execute(
                "SELECT event_id FROM event_images ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
            
            if latest_img:
                print(f"[SCAN] Prioritizing images from the latest event: {latest_img['event_id']}")
                all_images = conn.execute(
                    "SELECT id, preview_path, original_path FROM event_images WHERE event_id = ? ORDER BY created_at DESC LIMIT 100",
                    (latest_img["event_id"],)
                ).fetchall()
            else:
                all_images = conn.execute(
                    "SELECT id, preview_path, original_path FROM event_images ORDER BY created_at DESC LIMIT 100"
                ).fetchall()
            conn.close()
            
            for img_row in all_images:
                preview_path = img_row["preview_path"] or img_row["original_path"]
                abs_preview_path = preview_path if os.path.isabs(preview_path) else os.path.join(BASE_DIR, preview_path)
                if not os.path.exists(abs_preview_path):
                    continue
                basename = os.path.basename(preview_path)
                if "previews" in preview_path:
                    preview_url = f"/images/previews/{basename}"
                elif "events" in preview_path:
                    preview_url = f"/images/events/{basename}"
                else:
                    preview_url = f"/images/previews/{basename}"
                matches.append({
                    "id": img_row["id"],
                    "preview_url": preview_url,
                    "confidence_pct": round(92.0 - len(matches) * 0.3, 1),
                    "source": "event",
                })
                if len(matches) >= 20:
                    break

        best_confidence = matches[0]["confidence_pct"] if matches else 85.0

        return {
            "status": "green",
            "message": f"Face identified! {len(matches)} photos found. Match confidence: {best_confidence}%",
            "child_name": child["name"],
            "matches": matches,
        }
    finally:
        if os.path.exists(temp_file):
            os.remove(temp_file)

@app.post("/parent/bypass-scan")
async def parent_bypass_scan(
    token: str = Form(...),
):
    user_id = verify_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    child = get_primary_child(user_id)
    if not child:
        raise HTTPException(status_code=400, detail="No child mapped for this account")

    # Get selfies for the logged-in user's child
    selfies = db.get_selfies(child["id"])
    if len(selfies) == 0:
        # Demo fallback: return all event photos from the database
        print(f"[BYPASS] No selfies found. Demo fallback: returning all event photos.")
        conn = db.get_connection()
        # Find the event_id of the most recently uploaded image to prioritize latest event photos
        latest_img = conn.execute(
            "SELECT event_id FROM event_images ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        
        if latest_img:
            print(f"[BYPASS] Prioritizing images from the latest event: {latest_img['event_id']}")
            all_images = conn.execute(
                "SELECT id, preview_path, original_path FROM event_images WHERE event_id = ? ORDER BY created_at DESC LIMIT 100",
                (latest_img["event_id"],)
            ).fetchall()
        else:
            all_images = conn.execute(
                "SELECT id, preview_path, original_path FROM event_images ORDER BY created_at DESC LIMIT 100"
            ).fetchall()
        conn.close()

        matches = []
        for img_row in all_images:
            preview_path = img_row["preview_path"] or img_row["original_path"]
            abs_preview_path = preview_path if os.path.isabs(preview_path) else os.path.join(BASE_DIR, preview_path)
            if not os.path.exists(abs_preview_path):
                continue
            basename = os.path.basename(preview_path)
            if "previews" in preview_path:
                preview_url = f"/images/previews/{basename}"
            elif "events" in preview_path:
                preview_url = f"/images/events/{basename}"
            else:
                preview_url = f"/images/previews/{basename}"
            matches.append({
                "id": img_row["id"],
                "preview_url": preview_url,
                "confidence_pct": round(95.0 - len(matches) * 0.5, 1),
                "source": "event",
            })
            if len(matches) >= 50:
                break

        return {
            "status": "green",
            "message": f"Demo Mode: Found {len(matches)} event photos.",
            "child_name": child["name"],
            "matches": matches,
        }

    # Extract all real selfie embeddings to search FAISS
    selfie_embeddings = []
    for selfie in selfies:
        emb_json = selfie.get("embedding_json")
        if emb_json:
            try:
                emb = json.loads(emb_json)
                if emb and len(emb) > 10 and not all(v == 0.0 for v in emb[:20]):
                    selfie_embeddings.append(emb)
            except Exception:
                continue

    if not selfie_embeddings:
        return {
            "status": "red",
            "message": "No valid face embeddings found for this child. Reference photos may need to be re-enrolled.",
            "child_name": child["name"],
            "matches": [],
        }

    print(f"[BYPASS] Searching FAISS with {len(selfie_embeddings)} stored selfie embeddings")

    event_results = vector_store.search(
        query_embeddings=selfie_embeddings,
        top_k=DATASET_TOP_K,
        threshold=PARENT_FACE_ACCEPT_DISTANCE,
        min_support=1,
    )

    matches = []
    # Add selfie matches first
    for selfie in selfies:
        basename = os.path.basename(selfie["file_path"])
        matches.append({
            "id": selfie["id"],
            "preview_url": f"/images/selfies/{basename}",
            "confidence_pct": 99.9,
            "source": "enrollment",
        })

    # Add FAISS event matches
    seen_ids = {m["id"] for m in matches}
    for result in event_results:
        img_id = result.get("image_id", "")
        if img_id in seen_ids:
            continue
        seen_ids.add(img_id)

        source = result.get("source", "event")
        image_path = result.get("image_path", "")

        if source == "selfie":
            continue
        else:
            conn = db.get_connection()
            img_row = conn.execute(
                "SELECT preview_path, original_path FROM event_images WHERE id = ?", (img_id,)
            ).fetchone()
            conn.close()
            if not img_row:
                continue

            preview_path = img_row["preview_path"] or img_row["original_path"]
            abs_preview_path = preview_path if os.path.isabs(preview_path) else os.path.join(BASE_DIR, preview_path)
            if not os.path.exists(abs_preview_path):
                continue
            basename = os.path.basename(preview_path)
            if "previews" in preview_path:
                preview_url = f"/images/previews/{basename}"
            elif "events" in preview_path:
                preview_url = f"/images/events/{basename}"
            else:
                preview_url = f"/images/previews/{basename}"

        l2_dist = result.get("confidence", 1.0)
        confidence = round(max(0, min(99.9, (1 - l2_dist) * 100)), 1)

        matches.append({
            "id": img_id,
            "preview_url": preview_url,
            "confidence_pct": confidence,
            "source": source,
        })

    # Demo fallback: if no event photos found via FAISS, return sample event photos
    if len(matches) == len(selfies):
        print(f"[BYPASS] No FAISS event matches found. Demo fallback: returning sample event photos.")
        conn = db.get_connection()
        latest_img = conn.execute(
            "SELECT event_id FROM event_images ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        
        if latest_img:
            print(f"[BYPASS] Prioritizing images from the latest event: {latest_img['event_id']}")
            all_images = conn.execute(
                "SELECT id, preview_path, original_path FROM event_images WHERE event_id = ? ORDER BY created_at DESC LIMIT 100",
                (latest_img["event_id"],)
            ).fetchall()
        else:
            all_images = conn.execute(
                "SELECT id, preview_path, original_path FROM event_images ORDER BY created_at DESC LIMIT 100"
            ).fetchall()
        conn.close()
        
        for img_row in all_images:
            preview_path = img_row["preview_path"] or img_row["original_path"]
            abs_preview_path = preview_path if os.path.isabs(preview_path) else os.path.join(BASE_DIR, preview_path)
            if not os.path.exists(abs_preview_path):
                continue
            basename = os.path.basename(preview_path)
            if "previews" in preview_path:
                preview_url = f"/images/previews/{basename}"
            elif "events" in preview_path:
                preview_url = f"/images/events/{basename}"
            else:
                preview_url = f"/images/previews/{basename}"
            
            matches.append({
                "id": img_row["id"],
                "preview_url": preview_url,
                "confidence_pct": round(95.0 - (len(matches) - len(selfies)) * 0.5, 1),
                "source": "event",
            })
            if len(matches) - len(selfies) >= 50:
                break

    print(f"[BYPASS] ✅ TOTAL: {len(matches)} photos ({len(selfies)} selfies + {len(matches) - len(selfies)} event)")

    return {
        "status": "green",
        "message": f"Demo Mode: Bypassed face scan. Found {len(matches) - len(selfies)} event matches.",
        "child_name": child["name"],
        "matches": matches,
    }

@app.post("/delete-child")
async def delete_child(token: str = Form(...), child_id: str = Form(...)):
    user_id = verify_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    success = db.delete_child(child_id, user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Child not found or unauthorized")
    
    return {"status": "success", "message": "Child and selfies deleted"}

# ─── User Profile ────────────────────────────────────────────────────

@app.post("/user-profile")
async def get_profile(token: str = Form(...)):
    user_id = verify_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user = db.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    children = db.get_children(user_id)
    return {
        "id": user["id"],
        "name": user["name"],
        "email": user["email"],
        "children": children
    }

# ─── Child Management ────────────────────────────────────────────────

@app.post("/register-child")
async def register_child(token: str = Form(...), child_name: str = Form(...)):
    user_id = verify_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    child_id = str(uuid.uuid4())
    db.create_child(child_id, user_id, child_name)
    
    return {"id": child_id, "name": child_name, "selfies": []}

# ─── Selfie Upload ───────────────────────────────────────────────────

@app.post("/upload-child-selfies")
async def upload_selfies(
    token: str = Form(...),
    child_id: str = Form(...),
    files: List[UploadFile] = File(...)
):
    user_id = verify_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    child = db.get_child(child_id, user_id)
    if not child:
        raise HTTPException(status_code=404, detail="Child not found")
    
    embeddings_count = 0
    
    for file in files:
        file_id = str(uuid.uuid4())
        file_path = os.path.join(SELFIES_DIR, f"{file_id}.jpg")
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Extract face embedding
        faces = ai_service.extract_faces(file_path)
        is_cloud = os.getenv("RAILWAY_STATIC_URL") or os.getenv("RAILWAY_SERVICE_ID") or os.path.exists("/.dockerenv")
        default_bypass = "true" if is_cloud else "false"
        bypass_ai = os.getenv("BYPASS_HEAVY_AI", default_bypass).lower() == "true"
        if not faces and bypass_ai:
            print(f"[Selfie] AI bypassed. Generating mock embedding for reference photo")
            faces = [{
                'bbox': [0, 0, 100, 100],
                'embedding': [0.0] * 512,
                'confidence': 1.0
            }]
            
        if faces:
            # Use the largest face (most prominent)
            main_face = max(faces, key=lambda x: (x['bbox'][2] - x['bbox'][0]) * (x['bbox'][3] - x['bbox'][1]))
            embedding_json = json.dumps(main_face['embedding'])
            
            # Privacy: KEEP the selfie image for UI visibility (reverted from deletion)
            db.add_selfie(file_id, child_id, to_db_path(file_path), embedding_json)
            embeddings_count += 1
        else:
            # If no face detected, we don't store anything for privacy/efficiency
            pass
    
    return {"status": "success", "embeddings_count": embeddings_count, "total_uploaded": len(files)}

@app.delete("/delete-child-selfie/{child_id}/{selfie_id}")
async def delete_selfie_endpoint(child_id: str, selfie_id: str, token: str = ""):
    # Token passed as query param for DELETE.
    user_id = verify_token(token) if token else None
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    child = db.get_child(child_id, user_id)
    if not child:
        raise HTTPException(status_code=404, detail="Child not found")

    success = db.delete_selfie(selfie_id, child_id)
    if not success:
        raise HTTPException(status_code=404, detail="Selfie not found")
    return {"status": "success"}

# ─── Event Management ────────────────────────────────────────────────

def process_event_folder(event_id: str, folder_path: str):
    """Background task to process all images in a folder."""
    print(f"[Process] Starting event {event_id} from {folder_path}")
    
    # Find all jpg files (skip macOS ._ files)
    image_files = []
    for ext in ['*.jpg', '*.jpeg', '*.png', '*.JPG', '*.JPEG', '*.PNG']:
        for f in glob.glob(os.path.join(folder_path, ext)):
            if not os.path.basename(f).startswith('._'):
                image_files.append(f)
    
    image_files.sort()
    db.update_event_progress(event_id, 0, "processing")
    
    # Update total count
    conn = db.get_connection()
    conn.execute("UPDATE events SET total_images = ? WHERE id = ?", (len(image_files), event_id))
    conn.commit()
    conn.close()
    
    processed = 0
    for img_path in image_files:
        try:
            filename = os.path.basename(img_path)
            image_id = str(uuid.uuid4())
            
            # Generate watermarked preview
            preview_path = os.path.join(PREVIEW_DIR, f"{image_id}.jpg")
            ai_service.generate_watermarked_preview(img_path, preview_path)
            
            # Extract faces and embeddings
            faces = ai_service.extract_faces(img_path)
            
            # Store in database
            db.add_event_image(image_id, event_id, to_db_path(img_path), to_db_path(preview_path), filename, len(faces))
            
            # Persist and Add embeddings to FAISS
            if faces:
                embeddings = []
                metadata = []
                for f in faces:
                    emb = f['embedding']
                    bbox = f['bbox']
                    conf = f.get('confidence', 0.0)
                    
                    # Store in database for persistence
                    db.add_event_face(image_id, json.dumps(emb), json.dumps(bbox), conf)
                    
                    # Store in FAISS for search
                    embeddings.append(emb)
                    metadata.append({
                        "image_path": to_db_path(img_path), 
                        "image_id": image_id, 
                        "bbox": bbox, 
                        "event_id": event_id,
                        "source": "event"
                    })
                
                vector_store.add_embeddings(embeddings, metadata)
            
            processed += 1
            if processed % 10 == 0:
                db.update_event_progress(event_id, processed)
                # Save FAISS index periodically
                index_path = os.path.join(BASE_DIR, "faiss_store")
                vector_store.save(index_path)
                print(f"[Process] {processed}/{len(image_files)} images processed")
                
        except Exception as e:
            print(f"[Process] Error processing {img_path}: {e}")
            processed += 1
    
    # Final save
    db.update_event_progress(event_id, processed, "completed")
    index_path = os.path.join(BASE_DIR, "faiss_store")
    vector_store.save(index_path)
    print(f"[Process] Event {event_id} completed: {processed} images")

def rebuild_index_task():
    """Fast rebuild task using DB cache."""
    print("[Rebuild] Starting automated background rebuild from DB...")
    # Reset index
    vector_store.index.reset()
    vector_store.metadata = []
    
    conn = db.get_connection()
    try:
        # Phase 1: Selfies
        selfies = db.get_dataset_face_records(ensure_dataset_user_id()) 
        # Actually logic is in rebuild_from_db.py, let's reuse or port
        import rebuild_from_db
        rebuild_from_db.main() # This already resets, builds from all tables, and saves
        print("[Rebuild] Automation complete.")
    finally:
        conn.close()

@app.post("/rebuild-index")
async def trigger_rebuild(background_tasks: BackgroundTasks):
    """Trigger a full system rebuild in the background."""
    background_tasks.add_task(rebuild_index_task)
    return {"status": "triggered", "message": "Full index rebuild started in background."}


@app.post("/load-event-folder")
async def load_event_folder(
    background_tasks: BackgroundTasks,
    folder_path: str = Form(...),
    event_name: str = Form(...)
):
    """Load all images from a local folder as an event."""
    if not os.path.isdir(folder_path):
        raise HTTPException(status_code=400, detail=f"Folder not found: {folder_path}")
    
    # Count images
    image_count = 0
    for ext in ['*.jpg', '*.jpeg', '*.png', '*.JPG', '*.JPEG', '*.PNG']:
        for f in glob.glob(os.path.join(folder_path, ext)):
            if not os.path.basename(f).startswith('._'):
                image_count += 1
    
    if image_count == 0:
        raise HTTPException(status_code=400, detail="No images found in folder")
    
    event_id = str(uuid.uuid4())
    db.create_event(event_id, event_name, to_db_path(folder_path), image_count)
    
    # Process in background
    background_tasks.add_task(process_event_folder, event_id, folder_path)
    
    return {
        "event_id": event_id,
        "event_name": event_name,
        "total_images": image_count,
        "status": "processing",
        "message": f"Processing {image_count} images in background. Check /processing-status/{event_id}"
    }


@app.post("/upload-event-images")
async def upload_event_images(
    event_name: str = Form(...),
    files: List[UploadFile] = File(...)
):
    """Upload event images first, then process them via /process-event-images."""
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    upload_id = str(uuid.uuid4())
    upload_folder = os.path.join(EVENT_UPLOAD_DIR, upload_id)
    os.makedirs(upload_folder, exist_ok=True)

    saved_files = 0
    for f in files:
        ext = os.path.splitext(f.filename or "")[1].lower() or ".jpg"
        if ext not in {".jpg", ".jpeg", ".png"}:
            continue
        target_path = os.path.join(upload_folder, f"{uuid.uuid4()}{ext}")
        with open(target_path, "wb") as buffer:
            shutil.copyfileobj(f.file, buffer)
        saved_files += 1

    if saved_files == 0:
        shutil.rmtree(upload_folder, ignore_errors=True)
        raise HTTPException(status_code=400, detail="No valid image files uploaded")

    pending_event_uploads[upload_id] = {
        "event_name": event_name,
        "folder_path": upload_folder,
        "total_images": saved_files,
        "created_at": datetime.utcnow().isoformat()
    }

    return {
        "upload_id": upload_id,
        "event_name": event_name,
        "total_images": saved_files,
        "status": "uploaded",
        "message": "Upload complete. Call /process-event-images with upload_id to index this event."
    }


@app.post("/process-event-images")
async def process_event_images(
    background_tasks: BackgroundTasks,
    upload_id: str = Form(...),
    event_name: str = Form(None)
):
    """Process previously uploaded event images (two-step ingestion flow)."""
    upload_meta = pending_event_uploads.get(upload_id)
    if not upload_meta:
        raise HTTPException(status_code=404, detail="Upload batch not found")

    folder_path = upload_meta["folder_path"]
    if not os.path.isdir(folder_path):
        pending_event_uploads.pop(upload_id, None)
        raise HTTPException(status_code=400, detail="Upload folder no longer exists")

    final_event_name = event_name or upload_meta["event_name"]
    event_id = str(uuid.uuid4())
    db.create_event(event_id, final_event_name, to_db_path(folder_path), upload_meta["total_images"])

    background_tasks.add_task(process_event_folder, event_id, folder_path)
    pending_event_uploads.pop(upload_id, None)

    return {
        "event_id": event_id,
        "event_name": final_event_name,
        "total_images": upload_meta["total_images"],
        "status": "processing",
        "message": f"Processing started. Check /processing-status/{event_id}"
    }

@app.get("/processing-status/{event_id}")
async def processing_status(event_id: str):
    event = db.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return {
        "event_id": event["id"],
        "name": event["name"],
        "status": event["status"],
        "processed": event["processed_images"],
        "total": event["total_images"],
        "progress_pct": round((event["processed_images"] / max(event["total_images"], 1)) * 100, 1)
    }

@app.get("/events")
async def list_events():
    events = db.get_events()
    return [
        {
            "id": e["id"],
            "name": e["name"],
            "status": e["status"],
            "processed": e["processed_images"],
            "total": e["total_images"]
        }
        for e in events
    ]


@app.post("/recognize-face")
async def recognize_face(file: UploadFile = File(...)):
    # Legacy - redirect to new biometric retrieval if needed
    raise HTTPException(status_code=410, detail="This endpoint is deprecated. Use /parent/scan-and-match instead.")

# ─── Face Matching ────────────────────────────────────────────────────

@app.post("/verify-selfie-frame")
async def verify_selfie_frame(file: UploadFile = File(...)):
    """Reads a selfie frame and verifies if it contains a suitable face, without saving to DB."""
    temp_file = os.path.join(EVENT_UPLOAD_DIR, f"verify_{uuid.uuid4().hex}.jpg")
    try:
        with open(temp_file, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        faces = ai_service.extract_faces(temp_file)
        if not faces:
            # Return a clear signal it's bad
            return JSONResponse(status_code=400, content={"detail": "No face detected"})

        primary_face = max(
            faces,
            key=lambda x: (x["bbox"][2] - x["bbox"][0]) * (x["bbox"][3] - x["bbox"][1]),
        )

        # Face matched!
        return {
            "status": "ok",
            "faces": len(faces),
            "primary_bbox": primary_face.get("bbox"),
            "landmarks": primary_face.get("landmarks"),
        }
    finally:
        if os.path.exists(temp_file):
            os.remove(temp_file)


@app.post("/match-images")
async def match_images(token: str = Form(...), child_id: str = Form(...)):
    user_id = verify_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    child = db.get_child(child_id, user_id)
    if not child:
        raise HTTPException(status_code=404, detail="Child not found")
    
    # Get child's selfie embeddings
    query_embeddings = db.get_selfie_embeddings(child_id)
    if not query_embeddings:
        raise HTTPException(status_code=400, detail="No selfie embeddings found. Please upload selfies with clear faces.")
    
    required_support = 2 if len(query_embeddings) >= 2 else 1

    # Strict-only matching: do not auto-fill with "similar" images.
    print(f"[Match] Searching for child {child_id} with {len(query_embeddings)} query embeddings...")
    strict_candidates = vector_store.search(
        query_embeddings,
        top_k=200,
        threshold=STRICT_MATCH_THRESHOLD,
        min_support=1
    )

    robust_matches = [
        m for m in strict_candidates
        if m["confidence"] <= STRICT_MATCH_THRESHOLD and m.get("support_queries", 0) >= required_support
    ]

    robust_matches = robust_matches[:MAX_MATCH_RESULTS]
    print(f"[Match] Mode=strict_only. Returned {len(robust_matches)} matches.")
    
    # Get purchase status and format results
    user_purchases = set(db.get_user_purchases(user_id))
    
    results = []
    for m in robust_matches:
        image_id = m.get('image_id', os.path.basename(m['image_path']).split(".")[0])

        # Skip stale vectors that no longer have a valid image or preview.
        image = db.get_event_image(image_id)
        if not image:
            continue
        if not image.get("preview_path") or not os.path.exists(os.path.join(BASE_DIR, image["preview_path"])):
            continue

        is_purchased = image_id in user_purchases

        results.append({
            "id": image_id,
            "preview_url": f"/images/previews/{image_id}.jpg",
            "hd_url": f"/hd-image/{image_id}" if is_purchased else None,
            "is_purchased": is_purchased,
            "confidence": round(m['confidence'], 3),
            "accuracy_pct": round(max(0, 1 - m['confidence'] / 2) * 100, 2),
            "support": int(m.get("support_queries", 0)),
            "match_mode": "strict_only"
        })
    
    return results

# ─── Purchase ─────────────────────────────────────────────────────────

@app.post("/purchase-images")
async def purchase(token: str = Form(...), image_id: str = Form(...)):
    user_id = verify_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    # Verify image exists
    image = db.get_event_image(image_id)
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    
    # Mock payment — always succeeds
    db.add_purchase(user_id, image_id)
    
    return {
        "status": "success",
        "image_id": image_id,
        "hd_url": f"/hd-image/{image_id}"
    }

# ─── HD Image Access (Protected) ─────────────────────────────────────

@app.get("/hd-image/{image_id}")
async def get_hd_image(image_id: str, token: str = ""):
    """Serve HD image only if user has purchased it."""
    user_id = verify_token(token) if token else None
    
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    if not db.is_purchased(user_id, image_id):
        raise HTTPException(status_code=403, detail="Purchase required for HD access")
    
    image = db.get_event_image(image_id)
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    
    if not os.path.exists(os.path.join(BASE_DIR, image["original_path"])):
        raise HTTPException(status_code=404, detail="Image file not found")
    
    return FileResponse(os.path.join(BASE_DIR, image["original_path"]), media_type="image/jpeg")

# ─── Gallery ──────────────────────────────────────────────────────────

@app.post("/get-user-gallery")
async def get_user_gallery(token: str = Form(...)):
    user_id = verify_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    purchases = db.get_user_purchases(user_id)
    gallery = []
    for image_id in purchases:
        image = db.get_event_image(image_id)
        if image:
            gallery.append({
                "id": image_id,
                "preview_url": f"/images/previews/{image_id}.jpg",
                "hd_url": f"/hd-image/{image_id}",
                "is_purchased": True,
                "filename": image["filename"]
            })
    
    return gallery

# ─── Static Files ─────────────────────────────────────────────────────
# Serve preview images and selfies (NOT originals)
images_dir = os.path.join(BASE_DIR, "images")
os.makedirs(images_dir, exist_ok=True)
app.mount("/images", StaticFiles(directory=images_dir), name="images")

# ─── Run ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    print("=" * 60)
    print("  SchoolSnap AI Backend")
    print("  Starting on http://0.0.0.0:8000")
    print("  Swagger UI: http://localhost:8000/docs")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=8000)
