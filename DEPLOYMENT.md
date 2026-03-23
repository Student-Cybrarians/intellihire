# 🚀 IntelliHire — Full Microsoft Azure Deployment Guide

Every service is Microsoft:

| Layer | Microsoft Service | Free Tier |
|---|---|---|
| 🌐 Frontend | Azure Static Web Apps | Free plan (100GB bandwidth) |
| ⚡ Backend | Azure App Service | F1 Free (60 CPU min/day) |
| 🗄️ Database | Azure Cosmos DB | Free tier (1000 RU/s, 25GB) |
| 🤖 LLM | Azure OpenAI | Pay-per-use (GPT-4o) |
| 📁 Storage | Azure Blob Storage | 5GB free 12 months |
| 🔄 CI/CD | GitHub Actions | Free (Microsoft owns GitHub) |

---

## Step 1 — Create Azure Account (Free)

1. Go to → **https://azure.microsoft.com/free**
2. Sign up with Microsoft account — get **$200 free credit for 30 days**
3. Free services continue after 30 days (App Service F1, Cosmos DB free tier, Static Web Apps)

---

## Step 2 — Azure Cosmos DB (MongoDB API) — Free Tier

This replaces MongoDB Atlas with Microsoft's database.

1. Azure Portal → **Create a resource** → search **"Azure Cosmos DB"**
2. Select **"Azure Cosmos DB for MongoDB"** → Create
3. Fill in:
   - **Resource Group**: Create new → `intellihire-rg`
   - **Account Name**: `intellihire-cosmos`
   - **API**: `Azure Cosmos DB for MongoDB`
   - **Capacity Mode**: `Serverless` (cheapest for low traffic)
   - ✅ Check **"Apply Free Tier Discount"** → Get 1000 RU/s + 25GB free forever
4. Region: **Central India** or **South India** (closest to you)
5. Click **Review + Create** → **Create** (takes ~5 min)

### Get the Connection String:
1. Cosmos DB account → **Settings** → **Connection strings**
2. Copy **PRIMARY CONNECTION STRING** — looks like:
```
mongodb://intellihire-cosmos:XXXXXXXXXX==@intellihire-cosmos.mongo.cosmos.azure.com:10255/?ssl=true&replicaSet=globaldb&retrywrites=false&maxIdleTimeMS=120000&appName=@intellihire-cosmos@
```
3. Save this — needed for App Service

---

## Step 3 — Azure App Service (Backend) — Free Tier

1. Azure Portal → **Create a resource** → **Web App**
2. Fill in:
   - **Resource Group**: `intellihire-rg` (same as above)
   - **Name**: `intellihire-api` (URL: `intellihire-api.azurewebsites.net`)
   - **Runtime stack**: `Python 3.11`
   - **OS**: `Linux`
   - **Plan**: **Free F1** (click "Change size" → Dev/Test → F1)
3. Click **Review + Create** → **Create**

### Configure App Service:
1. App Service → **Configuration** → **Application settings** → **New application setting**

Add ALL these settings:

| Name | Value |
|---|---|
| `MONGODB_URL` | your Cosmos DB connection string |
| `MONGODB_DB_NAME` | `intellihire` |
| `LLM_PROVIDER` | `azure_openai` |
| `AZURE_OPENAI_API_KEY` | (from Step 4) |
| `AZURE_OPENAI_ENDPOINT` | (from Step 4) |
| `AZURE_OPENAI_DEPLOYMENT` | `gpt-4o` |
| `ENVIRONMENT` | `production` |
| `ALLOWED_ORIGINS` | `https://YOUR-APP.azurestaticapps.net,https://student-cybrarians.github.io` |
| `SCM_DO_BUILD_DURING_DEPLOYMENT` | `true` |
| `WEBSITE_RUN_FROM_PACKAGE` | `0` |

4. App Service → **Configuration** → **General settings**:
   - **Startup Command**: `uvicorn app.main:app --host 0.0.0.0 --port 8000`

### Get Publish Profile (for GitHub Actions):
1. App Service → **Overview** → **Download publish profile**
2. Open the downloaded `.PublishSettings` file → copy all its content
3. Save for GitHub Secrets

---

## Step 4 — Azure OpenAI (GPT-4o)

> Note: Azure OpenAI requires approval (usually 1-2 business days for students)

1. Azure Portal → **Create a resource** → search **"Azure OpenAI"**
2. Create resource in `intellihire-rg`
3. After approval → **Azure OpenAI Studio** → **Deployments** → **Create**
4. Model: **gpt-4o** | Deployment name: `gpt-4o`
5. **Keys and Endpoint** → copy KEY 1 and Endpoint URL

**While waiting for Azure OpenAI approval**, use standard OpenAI:
- Set `LLM_PROVIDER` = `openai`
- Set `OPENAI_API_KEY` = your key from platform.openai.com

---

## Step 5 — Azure Static Web Apps (Frontend)

This is better than GitHub Pages — faster CDN, free SSL, custom domains.

1. Azure Portal → **Create a resource** → **Static Web App**
2. Fill in:
   - **Resource Group**: `intellihire-rg`
   - **Name**: `intellihire-frontend`
   - **Plan**: **Free**
   - **Source**: GitHub
   - **Organization**: `Student-Cybrarians`
   - **Repository**: `intellihire`
   - **Branch**: `main`
   - **Build Presets**: `Custom`
   - **App location**: `/`
   - **Output location**: (leave empty)
3. Click **Review + Create** → **Create**
4. Azure auto-adds a deployment token to your GitHub repo secrets ✅

Your frontend URL: `https://RANDOM-NAME.azurestaticapps.net`

---

## Step 6 — GitHub Secrets (ties everything together)

GitHub → Student-Cybrarians/intellihire → Settings → Secrets → Actions

| Secret Name | Value |
|---|---|
| `AZURE_BACKEND_URL` | `https://intellihire-api.azurewebsites.net` |
| `AZURE_WEBAPP_NAME` | `intellihire-api` |
| `AZURE_WEBAPP_PUBLISH_PROFILE` | contents of the .PublishSettings file |
| `AZURE_STATIC_WEB_APPS_API_TOKEN` | auto-added by Azure SWA step above |

---

## Step 7 — Push to Deploy

```bash
git push origin main
```

GitHub Actions automatically:
1. ✅ Deploys frontend to Azure Static Web Apps
2. ✅ Deploys backend to Azure App Service
3. ✅ Injects real backend URL into frontend

---

## Final URLs

| Service | URL |
|---|---|
| 🌐 Frontend | `https://YOUR-NAME.azurestaticapps.net` |
| ⚡ Backend | `https://intellihire-api.azurewebsites.net` |
| 📖 API Docs | `https://intellihire-api.azurewebsites.net/docs` |
| 💚 Health | `https://intellihire-api.azurewebsites.net/health` |

---

## Complete Microsoft Technology Stack

```
User Browser
    │
    ▼
Azure Static Web Apps (CDN — 116 PoPs worldwide)
    │  HTTPS REST API
    ▼
Azure App Service F1 (Python 3.11 / FastAPI / Uvicorn)
    │  Motor async driver
    ▼
Azure Cosmos DB for MongoDB (Serverless, Free tier)
    
    + Azure OpenAI GPT-4o (LLM suggestions)
    + Azure Blob Storage (resume files)
    + GitHub Actions (CI/CD — Microsoft)
    + GitHub Pages (backup frontend — Microsoft)
```
