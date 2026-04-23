# Deploy to Google Cloud Run (Always Free)

## Why Google Cloud Run?
- ✅ Always free (first 2M requests/month)
- ✅ No credit card needed after free trial
- ✅ Auto-scales from 0 to 1000 instances
- ✅ No sleep/wake delays
- ✅ Uses your Dockerfile (already created)

## Prerequisites
1. Google Cloud account (https://cloud.google.com)
2. Gcloud CLI installed (https://cloud.google.com/sdk/docs/install)
3. Docker installed (for local testing)

## Step 1: Install Google Cloud SDK

### macOS
```bash
brew install --cask google-cloud-sdk
gcloud init
```

### Windows
Download: https://dl.google.com/dl/cloudsdk/channels/rapid/GoogleCloudSDKInstaller.exe

### Linux
```bash
curl https://sdk.cloud.google.com | bash
exec -l $SHELL
gcloud init
```

## Step 2: Configure gcloud

```bash
gcloud auth login
gcloud config set project YOUR-PROJECT-NAME
gcloud services enable run.googleapis.com
gcloud services enable cloudbuild.googleapis.com
```

## Step 3: Build and Deploy

### Option A: Direct Deploy (Easiest)
```bash
gcloud run deploy road-pavement \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --port 10000 \
  --memory 512Mi \
  --cpu 1 \
  --set-env-vars FLASK_SECRET_KEY=zdy-lLxBQDoxK1of8eKWx6MOD1sinD3xFL_zhW3gPis,SESSION_COOKIE_SECURE=1,DATA_DIR=/tmp/data
```

### Option B: Using Docker Artifact Registry

```bash
# Enable Artifact Registry
gcloud services enable artifactregistry.googleapis.com

# Build image
gcloud builds submit --tag us-central1-docker.pkg.dev/YOUR-PROJECT/road-pavement/app

# Deploy
gcloud run deploy road-pavement \
  --image us-central1-docker.pkg.dev/YOUR-PROJECT/road-pavement/app \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

## Step 4: Add Environment Variables

After deployment, update variables:

```bash
gcloud run deploy road-pavement \
  --update-env-vars \
    FLASK_SECRET_KEY=zdy-lLxBQDoxK1of8eKWx6MOD1sinD3xFL_zhW3gPis,\
    SESSION_COOKIE_SECURE=1,\
    DATA_DIR=/tmp/data,\
    GOOGLE_CLIENT_ID=your-id,\
    GOOGLE_CLIENT_SECRET=your-secret
```

## Step 5: Verify Deployment

```bash
# Get service URL
gcloud run services list

# View logs
gcloud run logs read road-pavement --limit 100

# Test endpoint
curl https://road-pavement-xxxx.run.app/healthz
```

## Cost Breakdown

| Item | Free/Month | Cost/Extra |
|------|-----------|-----------|
| Requests | 2,000,000 | $0.40 per 1M requests |
| vCPU time | 180,000 vCPU-seconds | $0.00002288 per second |
| Memory | 360,000 GB-seconds | $0.0000025 per GB-second |
| Network ingress | Unlimited | Free |
| Network egress | 1GB | $0.12 per GB after |

**For typical hobby use: $0/month**

## GitHub Actions Auto-Deploy (Optional)

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to Cloud Run

on:
  push:
    branches: [ master ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v2
    
    - name: Deploy to Cloud Run
      uses: google-github-actions/deploy-cloudrun@v0
      with:
        service: road-pavement
        image: gcr.io/${{ secrets.GCP_PROJECT }}/road-pavement
        region: us-central1
        credentials: ${{ secrets.GCP_SA_KEY }}
```

Then set GitHub secrets:
- `GCP_PROJECT`: your-project-id
- `GCP_SA_KEY`: service account JSON key

## Troubleshooting

**Memory error?**
```bash
# Increase memory
gcloud run deploy road-pavement \
  --memory 1024Mi \
  --cpu 2
```

**Port error?**
```bash
# Ensure port matches your app
gcloud run deploy road-pavement \
  --port 10000
```

**Dockerfile not found?**
```bash
# Specify custom Dockerfile
gcloud run deploy road-pavement \
  --source . \
  --dockerfile ./road_pavement_project/Dockerfile
```

**Cold start too slow?**
- Cloud Run cold starts are ~3-5 seconds (acceptable for hobby projects)
- Use Traffic Splitting to keep min instances warm (not free)

## Resources

- Dashboard: https://console.cloud.google.com/run
- Logs: https://console.cloud.google.com/logs
- Pricing: https://cloud.google.com/run/pricing
- Docs: https://cloud.google.com/run/docs

## Quick Comparison: Railway vs Cloud Run

| Feature | Railway | Cloud Run |
|---------|---------|-----------|
| Setup time | 5 min | 15 min |
| Free credits | $5/mo | Always free |
| Procfile | Yes | No (Docker) |
| Sleep | No | No |
| Cold starts | Instant | 3-5s |
| Best for | Quick deploys | Long-term free |

**Use Railway first, switch to Cloud Run after credits end.**
