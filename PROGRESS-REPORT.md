# 📊 SchoolSnap AI — Comprehensive Progress & Engineering Report

## 🎯 Project Vision
**SchoolSnap AI** is a secure, high-performance web and mobile platform designed to bridge the gap between school events and parents. By leveraging state-of-the-art **deep learning facial recognition** and **vector similarity search**, the application automates the indexing of school photographs, allowing parents to securely and instantaneously retrieve high-resolution photos of their children with a simple camera face scan.

---

## 🏗️ 1. Core Architecture Overview
The application is built on a decoupled, production-grade microservices architecture designed to operate locally via Docker Compose or scale dynamically in the cloud (Railway / GCP / Firebase).

```
                      ┌─────────────────────────────────┐
                      │    GATEWAY REVERSE PROXY        │
                      │         (Nginx :80)             │
                      └──────────────┬──────────────────┘
                                     │
         ┌───────────────────────────┼───────────────────────────┐
         ▼                           ▼                           ▼
┌──────────────────┐       ┌──────────────────┐       ┌──────────────────┐
│   V1 FRONTEND    │       │   V2 FRONTEND    │       │   FASTAPI API    │
│  Parent Portal   │       │  Investor Portal │       │  Python Backend  │
│    (Port 80)     │       │    (Port 80)     │       │   (Port 8000)    │
└──────────────────┘       └──────────────────┘       └──────────┬───────┘
                                                                 │
                                                      ┌──────────▼───────┐
                                                      │   DATA VOLUMES   │
                                                      │  SQLite + FAISS  │
                                                      │  + Image Storage │
                                                      └──────────────────┘
```

### Technical Stack:
*   **Frontend**: React (v18) + Vite + TypeScript (fully responsive for mobile, tablet, and desktop).
*   **Backend**: Python FastAPI (high-performance ASGI framework) with Pydantic schemas.
*   **AI/ML Pipeline**: OpenCV (image processing), DeepFace (high-accuracy facial recognition), and ONNX Runtime.
*   **Vector Database**: FAISS (Facebook AI Similarity Search) for sub-millisecond embedding index lookups.
*   **Data & Storage**: SQLite (relational database for parent profiles) and a structured local file-system volume for media storage.
*   **Gateway**: Nginx reverse proxy routing traffic, managing TLS termination, and handling rate-limiting zones.

---

## 🚀 2. Engineering Milestones & Key Features Built

### 📸 A. The AI Face-Recognition Pipeline (Core Engine)
The facial recognition engine is engineered to process massive batches of school photographs and match faces with extreme precision.
1.  **Face Detection (YuNet & RetinaFace)**:
    *   Integrates ultra-lightweight, high-speed **YuNet** (0.22MB) for instantaneous localized face boundaries.
    *   Uses **RetinaFace** as a high-accuracy alternative for complex group photos, detecting orientation, lighting shifts, and expressions.
2.  **Feature Extraction & Embedding (ArcFace / GhostFaceNet)**:
    *   Extracts normalized **512-dimensional feature vectors** (embeddings) from detected faces using deep neural networks.
    *   Applies **L2 normalization** to ensure matching is based purely on spatial vector distance (cosine similarity).
3.  **FAISS Vector Indexing**:
    *   Rather than running costly nested database queries, all student face embeddings are indexed inside a **FAISS vector database**.
    *   This enables **sub-millisecond nearest-neighbor searches** ($O(1)$ complexity) to scale matches to millions of photos seamlessly.

---

### 🖥️ B. Dual Frontend Interfaces (React + Vite + TS)
We implemented two beautiful, modern, and fully responsive user interfaces:
1.  **V1: Parent & School Portal**:
    *   **Link 1 (School Enrollment)**: A school portal where administrators can input registration numbers, name children, and upload reference photos of children.
    *   **Link 2 (Parent Access)**: A parent portal that validates credentials (Registration Number + Date of Birth). Upon successful authentication, it **automatically invokes the user's front-facing camera** (on mobile or desktop) to scan their child's face and displays their matched school photos instantly.
2.  **V2: Investor & Aether Suite**:
    *   A high-end administrative portal showcasing system logs, performance metrics, vector distribution maps, and operational efficiency dashboards for presentation purposes.

---

### 🔒 C. Enterprise-Grade Security Hardening
The codebase was transformed from a developer prototype to a robust production system:
*   **Secrets Management**: Eliminated all hardcoded passwords, JWT keys, and credentials, centralizing them in `.env` and `.env.production` templates.
*   **Input Validation & Sanitization (`validation.py`)**:
    *   Enforced regex patterns for registration codes (`REG\d{4}`) and date formats.
    *   Implemented strict upload validation (verifying MIME types, maximum image size of 100MB, and sanitizing filenames to block Directory Traversal attacks).
*   **Rate Limiting (`rate_limiter.py`)**:
    *   Integrated **SlowAPI** to throttle potential brute-force attempts on parent logins and prevent Denial-of-Service (DoS) vectors on heavy upload routes.
*   **Response Security Headers (`security.py`)**:
    *   Added standard headers: `X-Frame-Options` (Clickjacking protection), `X-Content-Type-Options` (MIME-sniffing protection), `Strict-Transport-Security` (HSTS), and configured rigorous CORS policies.

---

## ☁️ 3. DevOps, Containerization & Production Cloud Deployment

### 🐳 Docker & Orchestration
*   **Multi-Stage Dockerfiles**: Written for all containers (`backend`, `v1`, `v2`, `gateway`) to minimize production footprint by stripping Node/Python build tools in the final layer.
*   **Non-Root User Execution**: Configured all containers to run as low-privilege users (`nginx:nginx` and `nobody`) for system-level security.
*   **Health Checks**: Embedded automated container health checks inside Docker Compose to verify that frontend servers and API services are online.

---

### 🚆 Railway Cloud Deployment Breakthroughs
To resolve deployment problems (such as CORS errors, browser mixed-content blocks, and startup crashes) when launching the monorepo on Railway, we introduced three technical breakthroughs:

1.  **Dynamic Runtime Nginx Templates**:
    *   **The Issue**: Vite compiles environment variables (like `VITE_API_BASE_URL`) at build time. Defaulting to `/api` or `http://localhost:8000` causes browser requests to fail when served standalone in the cloud.
    *   **The Solution**: We created `nginx.conf.template` configurations. The frontend calls `/api/` relative to its own domain. In the Nginx container, we used `envsubst` to dynamically hot-swap the backend URL on startup using the **`BACKEND_URL`** environment variable!
2.  **Deferred Startup Resolution**:
    *   **The Issue**: Nginx ordinarily crashes on startup if a proxy host is not yet resolvable or is offline.
    *   **The Solution**: Implemented **variable-based proxying** (`set $backend "${BACKEND_URL}"`) with public DNS resolvers (`8.8.8.8`/`1.1.1.1`) inside the template. This makes the containers start successfully every single time.
3.  **Resource Limits Optimization**:
    *   Documented that the Python backend requires **at least 2GB of RAM** on Railway. This prevents immediate silent **Exit Code 137 (OOM)** container crashes when loading deep learning models.

---

## 📋 4. Pre-Seeded Demo Credentials
To allow frictionless user and investor testing, the system boots up with the following parent-student credentials seeded inside the SQLite database:

| 🆔 Registration Number | 📅 Date of Birth (Password) | 👤 Parent Name | 👶 Child Name |
| :--- | :--- | :--- | :--- |
| **`REG1001`** | `2014-05-12` | Ravi Kumar | Aarav Kumar |
| **`REG1002`** | `2013-09-22` | Sneha Reddy | Isha Reddy |
| **`REG1003`** | `2015-01-18` | Vikram Rao | Vihaan Rao |

---

## 📈 5. Project Development Timeline & Progress Status

| Phase | Milestone | Focus | Status |
| :--- | :--- | :--- | :--- |
| **Phase 1** | **Prototype Core** | SQLite Database, Face Extraction & Local Matching | **Completed** |
| **Phase 2** | **V1 & V2 Frontends** | Parent Web App, Admin Dashboard, Auto Camera Scanning | **Completed** |
| **Phase 3** | **Security Hardening** | Inputs Validation, Throttling, Headers, Secrets Isolation | **Completed** |
| **Phase 4** | **DevOps & Containers** | Dockerizing Microservices, Port Mapping, Volume Persistence | **Completed** |
| **Phase 5** | **Cloud Deployment** | Dynamic Nginx Proxying Templates, DNS Resolver Fixes, Git Push | **Completed & Live** |

---

## 🏁 How to Build and Run Locally (Development)

```bash
# 1. Start the FastAPI Python Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# 2. Start the Vite Frontend (In a separate terminal)
cd frontend   # or cd v1
npm install
npm run dev -- --port 3000
```
