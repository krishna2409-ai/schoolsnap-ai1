# SchoolSnap AI Web MVP (Two-Link School Access Demo)

This build follows the exact simple business flow:

1. Link 1: school uploads a few student reference photos.
2. Link 2: school shares parent login credentials.
3. Username = registration number.
4. Password = date of birth.
5. Login opens camera automatically.
6. Scan child face and instantly show matched photos.

The UI is responsive for mobile, tablet, and laptop.

## 1) Architecture Overview

### Frontend (React + Vite)

- `/` shows both links.
- `/school-enrollment` uploads student reference photos.
- `/parent-access` handles login, auto camera, and scan results.

### Backend (FastAPI)

- Seeds fake school credential data in SQLite at startup.
- Maps registration number to parent account and primary child.
- School onboarding endpoint stores enrollment photos and face embeddings.
- Parent endpoint validates child face and returns matches.

### AI Pipeline

1. School uploads child photos.
2. Backend extracts embeddings with DeepFace (GhostFaceNet + retinaface).
3. Parent logs in and scans child face.
4. Backend validates scan against enrolled child embeddings.
5. Returns red or green status and matched images.

## 2) Tech Stack Justification

- Frontend: React + Vite for fast route-based demo pages.
- Backend: FastAPI for clean local APIs and quick integration.
- Face Recognition: DeepFace pipeline already present in codebase.
- Storage: SQLite + local image folders for zero-infra MVP demo.

## 3) Implementation Steps

1. Seed fake parent accounts with registration number + DOB.
2. Build school enrollment link page.
3. Build parent access link page.
4. Auto-open camera after successful login.
5. Scan child face and immediately return red/green + matches.

## 4) API Endpoints

### `GET /demo/credentials`

Returns seeded fake demo credentials.

### `POST /school/upload-enrollment`

Multipart form fields:

- `registration_number`
- optional `child_name`
- `files[]`

### `POST /parent/access-login`

Form fields:

- `registration_number`
- `dob`

### `POST /parent/scan-and-match`

Multipart form fields:

- `token`
- `file`

Returns:

- `status`: `green` or `red`
- `message`
- `matches`: photo list for display

## 5) Key Files

```text
src/App.tsx            # Two-link flow pages and parent scan UI
src/index.css          # Responsive styles
backend/main.py        # Seeded credentials + school/parent endpoints
backend/database.py    # SQLite helpers
```

## 6) Local Setup

### Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend

```bash
cd ..
npm install
npm run dev
```

Links:

- Home: `http://localhost:3000`
- Link 1: `http://localhost:3000/school-enrollment`
- Link 2: `http://localhost:3000/parent-access`

Optional frontend env:

- `VITE_API_BASE_URL=http://localhost:8000`

## 7) Seeded Fake Credentials

- `REG1001` / `2014-05-12`
- `REG1002` / `2013-09-22`
- `REG1003` / `2015-01-18`

## 8) Demo Script (2 Minutes)

1. Open link 1 and upload a few child photos for `REG1001`.
2. Open link 2 and login with `REG1001` + `2014-05-12`.
3. Camera opens automatically.
4. Scan child face.
5. Show green status and matched photos.
