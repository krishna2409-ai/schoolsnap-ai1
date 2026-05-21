# 🚀 SchoolSnap AI — Railway Deployment Cheat Sheet

This repository is optimized for **dynamic runtime environment proxying**. You no longer need to worry about build-time environment variable compilation! 

Follow this quick guide to deploy your stack on Railway:

---

## 🖥️ 1. Deploy the Backend Service (`backend`)
1. Create a **New Service** on Railway from your GitHub repository.
2. Under **Settings**:
   * Set **Root Directory** to `backend`.
   * Under **Build Command**, let Railway build it automatically using `backend/Dockerfile`.
3. Under **Variables**:
   * `ENVIRONMENT` = `production`
   * `DEBUG` = `False`
   * `CORS_ORIGINS` = `*` (or your exact frontend URL)
   * `SECRET_KEY` = `[Generate a secure 32+ character key]`
   * `PORT` = `8000`
4. Under **Settings** ➔ **Resources**:
   * **Crucial**: Allocate **at least 2GB of RAM** (preferably 3GB-4GB). The AI libraries (`onnxruntime`, `deepface`) will crash with **Exit Code 137** (OOM) if allocated only 512MB/1GB.
5. Generate a **Public Domain** (e.g., `https://schoolsnap-backend.up.railway.app`). Keep this URL handy.

---

## 🎨 2. Deploy the Parent Portal Frontend (`v1`)
1. Create a **New Service** from the same GitHub repository.
2. Under **Settings**:
   * Set **Root Directory** to `v1`.
   * Railway will build it automatically using `v1/Dockerfile`.
3. Under **Variables**:
   * Add a variable named: **`BACKEND_URL`** = `https://schoolsnap-backend.up.railway.app` *(Replace this with your actual backend URL from Step 1)*.
4. Generate a **Public Domain** (e.g., `https://frontend-v1-production-d3d2.up.railway.app`).

---

## 📊 3. Deploy the Investor Portal Frontend (`v2`)
1. Create a **New Service** from the same GitHub repository.
2. Under **Settings**:
   * Set **Root Directory** to `v2`.
   * Railway will build it automatically using `v2/Dockerfile`.
3. Under **Variables**:
   * Add a variable named: **`BACKEND_URL`** = `https://schoolsnap-backend.up.railway.app` *(Replace this with your actual backend URL from Step 1)*.
4. Generate a **Public Domain** (e.g., `https://investor-production.up.railway.app`).

---

## 💾 4. Add Database & Image Persistence
Since Railway containers are ephemeral, uploaded photos are lost on restarts.
1. Click **New** ➔ **Volume**.
2. Mount this volume to your **Backend Service** at `/app/images` (or `/app` to cover the database and vector files).
