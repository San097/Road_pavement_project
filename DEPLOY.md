# Road Pavement Project - Google Cloud Run Deployment

## Docker Build And Run

Build the image from the repository root:

```bash
docker build -t road-pavement-project .
```

Run the container locally on port `8080` and keep uploads/auth data in a mounted folder:

```bash
docker run --rm -p 8080:8080 \
  -e FLASK_SECRET_KEY=replace-with-a-long-random-secret \
  -e SESSION_COOKIE_SECURE=0 \
  -v "$(pwd)/docker-data:/app/data" \
  road-pavement-project
```

Windows PowerShell:

```powershell
docker run --rm -p 8080:8080 `
  -e FLASK_SECRET_KEY=replace-with-a-long-random-secret `
  -e SESSION_COOKIE_SECURE=0 `
  -v "${PWD}\\docker-data:/app/data" `
  road-pavement-project
```

The app will be available at `http://localhost:8080`.

## Quick Start (30 seconds)

1. **Install Google Cloud SDK**
   - macOS: `brew install --cask google-cloud-sdk`
   - Windows: Download from https://dl.google.com/dl/cloudsdk/channels/rapid/GoogleCloudSDKInstaller.exe
   - Linux: `curl https://sdk.cloud.google.com | bash`

2. **Login to Google Cloud**
   ```bash
   gcloud init
   gcloud auth login
   ```

3. **Enable required APIs**
   ```bash
   gcloud services enable run.googleapis.com cloudbuild.googleapis.com
   ```

4. **Deploy your app**
   ```bash
   gcloud run deploy road-pavement \
     --source . \
     --platform managed \
     --region us-central1 \
     --allow-unauthenticated \
     --port 10000 \
     --memory 512Mi \
     --set-env-vars FLASK_SECRET_KEY=your-secret,SESSION_COOKIE_SECURE=1,DATA_DIR=/tmp/data
   ```

5. **Get your URL**
   ```bash
   gcloud run services describe road-pavement \
     --platform managed \
     --region us-central1 \
     --format 'value(status.url)'
   ```

✅ Done! Your app is live.

## For Detailed Setup Instructions

See `CLOUD_RUN_SETUP.md` for:
- Step-by-step installation guide
- Environment variable configuration
- Optional features (Google OAuth, email)
- Monitoring and debugging
- Cost breakdown

## Key Features

- ✅ Always free ($0/month)
- ✅ Auto-scales from 0 to 1000 instances
- ✅ No sleep or inactivity delays
- ✅ First request: 3-5 seconds, then instant
- ✅ Uses your existing Dockerfile

## Costs

2 million free requests/month. For hobby projects: **$0/month**

## Support

- Dashboard: https://console.cloud.google.com/run
- Logs: https://console.cloud.google.com/logs
- Documentation: https://cloud.google.com/run/docs
