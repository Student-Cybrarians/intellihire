# 🚀 IntelliHire — Complete Deployment Guide

Deploy frontend to **GitHub Pages** + backend to **Render.com** + database to **MongoDB Atlas** (all free).

---

## Architecture

```
GitHub Repo (intellihire)
├── frontend/          → GitHub Pages  (YOUR_USERNAME.github.io/intellihire)
│   └── index.html
├── backend/           → Render.com    (intellihire-api.onrender.com)
│   └── app/...
└── .github/workflows/ → GitHub Actions (auto-deploy on push)
```

```
User Browser
     │  HTTPS
     ▼
GitHub Pages (frontend/index.html)
     │  REST API calls (CORS-enabled)
     ▼
Render.com (FastAPI backend)
     │  Async MongoDB driver
     ▼
MongoDB Atlas (free cluster)
```

---

## Step 1 — Create GitHub Repository

```bash
# 1. Go to github.com → New Repository
#    Name: intellihire
#    Visibility: Public (required for free GitHub Pages)
#    ✅ Add README

# 2. Clone it locally
git clone https://github.com/YOUR_USERNAME/intellihire.git
cd intellihire

# 3. Copy all files from this ZIP into the repo
cp -r /path/to/intellihire-deploy/* .
git add .
git commit -m "feat: initial IntelliHire platform"
git push origin main
```

---

## Step 2 — Set Up MongoDB Atlas (Free Cloud DB)

1. Go to **https://cloud.mongodb.com** → Sign up free
2. Create Organisation → Create Project → **Build a Cluster**
3. Select **M0 Free tier** → Choose region (closest to you)
4. Wait ~3 minutes for cluster to provision
5. Click **Connect** → **Connect your application**
6. Copy the connection string (looks like):
   ```
   mongodb+srv://username:password@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority
   ```
7. Replace `<password>` with your actual password
8. **Save this string** — you'll need it for Render

### Configure Atlas Network Access
- Go to **Network Access** → **Add IP Address**
- Click **Allow Access from Anywhere** (`0.0.0.0/0`)
- This allows Render's dynamic IPs to connect

---

## Step 3 — Deploy Backend to Render.com

### 3a. Create Render Account
- Go to **https://render.com** → Sign up with GitHub

### 3b. Create New Web Service
1. Dashboard → **New +** → **Web Service**
2. Connect your GitHub repo: `YOUR_USERNAME/intellihire`
3. Fill in settings:

| Field | Value |
|---|---|
| **Name** | `intellihire-api` |
| **Root Directory** | `backend` |
| **Runtime** | `Python 3` |
| **Build Command** | `pip install -r requirements.txt && python -m spacy download en_core_web_sm` |
| **Start Command** | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| **Plan** | Free |

### 3c. Add Environment Variables
In Render → Your Service → **Environment** tab, add:

| Key | Value |
|---|---|
| `MONGODB_URL` | `mongodb+srv://user:pass@cluster.mongodb.net/intellihire` |
| `MONGODB_DB_NAME` | `intellihire` |
| `LLM_PROVIDER` | `openai` |
| `OPENAI_API_KEY` | `sk-...` (your OpenAI key) |
| `ENVIRONMENT` | `production` |
| `DEBUG` | `false` |
| `ALLOWED_ORIGINS` | `https://YOUR_USERNAME.github.io` |
| `SPACY_MODEL` | `en_core_web_sm` |
| `UPLOAD_DIR` | `/tmp/intellihire/uploads` |
| `REPORTS_DIR` | `/tmp/intellihire/reports` |

4. Click **Create Web Service**
5. Wait for first deploy (~5 min)
6. Your backend URL will be: `https://intellihire-api.onrender.com`
7. Test: `https://intellihire-api.onrender.com/health`

### 3d. Get Deploy Hook URL
- Render → Your Service → **Settings** → **Deploy Hook**
- Copy the URL — save for GitHub Secrets

---

## Step 4 — Configure GitHub Pages

1. GitHub → Your Repo → **Settings** → **Pages**
2. Under **Source**: Select **GitHub Actions**
3. Click **Save**

---

## Step 5 — Add GitHub Secrets

GitHub → Your Repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

| Secret Name | Value |
|---|---|
| `RENDER_BACKEND_URL` | `https://intellihire-api.onrender.com` |
| `RENDER_DEPLOY_HOOK_URL` | Your Render deploy hook URL |

---

## Step 6 — Push to Trigger Deployment

```bash
# Trigger GitHub Actions
git add .
git commit -m "deploy: configure production URLs"
git push origin main
```

**GitHub Actions will automatically:**
1. ✅ Run backend tests
2. ✅ Inject your Render URL into `frontend/index.html`
3. ✅ Deploy frontend to GitHub Pages
4. ✅ Trigger Render backend redeploy

---

## Step 7 — Verify Deployment

| Check | URL |
|---|---|
| Frontend | `https://YOUR_USERNAME.github.io/intellihire` |
| Backend Health | `https://intellihire-api.onrender.com/health` |
| API Docs | `https://intellihire-api.onrender.com/docs` |
| Mongo Express | N/A (Atlas UI at cloud.mongodb.com) |

---

## Free Tier Limitations

| Service | Free Tier Limits |
|---|---|
| **GitHub Pages** | Unlimited static hosting |
| **Render** | 512MB RAM, spins down after 15min inactivity (first request ~30s cold start) |
| **MongoDB Atlas** | 512MB storage, shared cluster |
| **OpenAI** | Pay-as-you-go (~$0.01 per analysis) |

> 💡 **Tip**: To avoid Render cold starts, set up a free uptime monitor at [uptimerobot.com](https://uptimerobot.com) pinging `/health` every 5 minutes.

---

## Local Development

```bash
cd backend
cp .env.example .env
# Edit .env with your keys

# Start MongoDB locally
docker compose up -d mongodb

# Run backend
source .venv/bin/activate
uvicorn app.main:app --reload

# Frontend: open frontend/index.html in browser
# OR serve it locally:
cd frontend && python -m http.server 3000
# Then open http://localhost:3000
```

---

## File Structure After Deployment

```
intellihire/                  ← GitHub repo root
├── frontend/
│   ├── index.html            → Deployed to GitHub Pages
│   ├── .nojekyll             → Tells GitHub: not a Jekyll site
│   └── _config.yml
├── backend/
│   ├── app/                  → Deployed to Render
│   ├── requirements.txt
│   └── ...
├── .github/
│   └── workflows/
│       └── deploy.yml        → GitHub Actions CI/CD
├── render.yaml               → Render config
└── README.md
```

---

## Updating the Application

```bash
# Make changes, then:
git add .
git commit -m "feat: your change"
git push origin main
# → GitHub Actions auto-deploys frontend + backend
```

---

## Common Issues

| Problem | Solution |
|---|---|
| CORS error in browser | Add frontend URL to `ALLOWED_ORIGINS` in Render env vars |
| Backend 503 on first request | Render free tier cold start — wait 30s and retry |
| MongoDB connection refused | Check Atlas Network Access allows `0.0.0.0/0` |
| spaCy model not found | BuildCommand must include `python -m spacy download en_core_web_sm` |
| PDF generation fails | WeasyPrint needs system libs — use ReportLab fallback (already coded) |

---

## Domain (Optional)

To use a custom domain (e.g. `intellihire.yourdomain.com`):
1. GitHub Pages → Custom Domain → enter your domain
2. Add CNAME DNS record pointing to `YOUR_USERNAME.github.io`
3. ✅ Enforce HTTPS (GitHub handles SSL automatically)
