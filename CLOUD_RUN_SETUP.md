# Google Cloud Run Deployment Guide

## Overview
Google Cloud Run provides **always-free hosting** for your Flask app:
- 2 million requests/month free
- Auto-scales from 0 to 1000 instances
- No sleep/wake delays
- Uses your existing Dockerfile

## Prerequisites

1. **Google Cloud Account** (free): https://console.cloud.google.com
2. **Google Cloud SDK** installed locally
3. **Docker** installed (for local testing)

## Installation

### macOS
```bash
brew install --cask google-cloud-sdk
gcloud init
gcloud auth login
```

### Windows
1. Download: https://dl.google.com/dl/cloudsdk/channels/rapid/GoogleCloudSDKInstaller.exe
2. Run installer
3. Open PowerShell and run:
```powershell
gcloud init
gcloud auth login
```

### Linux
```bash
curl https://sdk.cloud.google.com | bash
exec -l $SHELL
gcloud init
gcloud auth login
```

## Quick Deploy (Recommended)

Run this single command to deploy:

```bash
gcloud run deploy road-pavement \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --port 10000 \
  --memory 512Mi \
  --set-env-vars FLASK_SECRET_KEY=your-secret-key,SESSION_COOKIE_SECURE=1,DATA_DIR=/tmp/data
```

**Replace `your-secret-key` with:**
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

## Step-by-Step Setup

### 1. Initialize gcloud
```bash
gcloud init
gcloud auth login
```

### 2. Enable Required APIs
```bash
gcloud services enable run.googleapis.com
gcloud services enable cloudbuild.googleapis.com
```

### 3. Deploy Your App
```bash
gcloud run deploy road-pavement \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --port 10000 \
  --memory 512Mi \
  --cpu 1
```

### 4. Set Environment Variables
```bash
gcloud run deploy road-pavement \
  --update-env-vars \
    FLASK_SECRET_KEY=zdy-lLxBQDoxK1of8eKWx6MOD1sinD3xFL_zhW3gPis,\
    SESSION_COOKIE_SECURE=1,\
    DATA_DIR=/tmp/data
```

### 5. Get Your Service URL
```bash
gcloud run services describe road-pavement \
  --platform managed \
  --region us-central1 \
  --format 'value(status.url)'
```

## Verify Deployment

### Check Service Status
```bash
gcloud run services list
```

### View Logs
```bash
gcloud run logs read road-pavement --limit 50
```

### Test the App
```bash
# Replace with your actual URL
curl https://road-pavement-xxxx.run.app/healthz
```

## Add Optional Features

### Google OAuth (Optional)
1. Get credentials from: https://console.cloud.google.com/apis/credentials
2. Update environment variables:
```bash
gcloud run deploy road-pavement \
  --update-env-vars \
    GOOGLE_CLIENT_ID=your-id,\
    GOOGLE_CLIENT_SECRET=your-secret,\
    GOOGLE_REDIRECT_URI=https://road-pavement-xxxx.run.app/login/google/authorized
```

### Email Configuration (Optional)
```bash
gcloud run deploy road-pavement \
  --update-env-vars \
    EMAIL_HOST=smtp.gmail.com,\
    EMAIL_PORT=587,\
    EMAIL_USER=your@gmail.com,\
    EMAIL_PASS=your-app-password
```

## Increase Resources (If Needed)

```bash
# More memory
gcloud run deploy road-pavement \
  --memory 1024Mi \
  --cpu 2
```

## Monitor & Debug

### Real-time Logs
```bash
gcloud run logs read road-pavement --follow
```

### Check Metrics
```bash
# View in console
open https://console.cloud.google.com/run/detail/us-central1/road-pavement
```

### Common Issues

**App crashes on start?**
```bash
# Check full logs
gcloud run logs read road-pavement --limit 100
```

**Port error?**
- Ensure `app.py` listens on `0.0.0.0:$PORT`
- Current setup: ✅ Uses PORT env variable

**Cold start slow?**
- First request takes 3-5 seconds
- Subsequent requests are instant
- Normal for serverless

## Cost

| Item | Free/Month | Cost/Extra |
|------|-----------|-----------|
| Requests | 2,000,000 | $0.40 per 1M |
| vCPU time | 180,000 seconds | $0.00002288/sec |
| Memory | 360,000 GB-seconds | $0.0000025/GB-sec |
| Network out | 1 GB | $0.12 per GB |

**For hobby use: $0/month**

## Update Deployment

After code changes:

```bash
# Push to GitHub
git push origin master

# Redeploy (will use new code)
gcloud run deploy road-pavement --source .
```

## Dashboard & Management

- **View services**: https://console.cloud.google.com/run
- **View logs**: https://console.cloud.google.com/logs
- **View metrics**: https://console.cloud.google.com/monitoring

## Delete Service (If Needed)

```bash
gcloud run services delete road-pavement --region us-central1
```

## Summary

✅ Your app is ready to deploy to Google Cloud Run
✅ Uses Docker for containerization
✅ Always-free tier ($0/month for hobby projects)
✅ Auto-scales, no sleep delays
✅ Environment variables configured

**Next step:** Run the quick deploy command above!
