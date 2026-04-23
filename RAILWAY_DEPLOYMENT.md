# Railway Deployment Guide for Road Pavement Project

## Prerequisites
- GitHub account with your repo pushed
- Railway account (https://railway.app)

## Step 1: Create a New Project on Railway

1. Go to https://railway.app
2. Click **New Project**
3. Select **Deploy from GitHub**
4. Authorize Railway to access your GitHub
5. Select repository: `road_pavement`
6. Click **Create Project**

## Step 2: Configure the Service

Railway will automatically detect your `Procfile` and `requirements.txt`.

**If it doesn't auto-detect:**
1. Click **Settings** on your service
2. Set **Procfile path** to: `Procfile`
3. Set **Python version** to: `3.10`

## Step 3: Add Environment Variables

1. Go to your Railway project dashboard
2. Click the service → **Variables**
3. Add the following:

```
FLASK_SECRET_KEY=zdy-lLxBQDoxK1of8eKWx6MOD1sinD3xFL_zhW3gPis
SESSION_COOKIE_SECURE=1
DATA_DIR=/var/data
PYTHON_VERSION=3.10
PORT=8000
```

**Optional (for features):**
- `GOOGLE_CLIENT_ID` - Get from Google Cloud Console
- `GOOGLE_CLIENT_SECRET` - Get from Google Cloud Console
- `EMAIL_HOST=smtp.gmail.com`
- `EMAIL_USER=your_email@gmail.com`
- `EMAIL_PASS=your_app_password`

## Step 4: Deploy

1. Click **Deploy** on the Railway dashboard
2. Monitor the build logs
3. Once deployed, Railway will provide a public URL

## Troubleshooting

**If build fails:**
- Check logs in Railway dashboard
- Verify all dependencies in `requirements.txt` are compatible
- Ensure `Procfile` path is correct

**If app crashes after deploy:**
- Check Railway logs for errors
- Verify environment variables are set
- Ensure data directories exist

## Cost

Railway offers:
- **Free tier**: $5 credits/month (enough for hobby projects)
- **Pay as you go**: $0.50/GB RAM hour, $0.10/vCPU hour
- Much cheaper than Render's paid plans

## Pricing Calculator
https://railway.app/pricing

Your app should run for free or ~$1/month on Railway's free tier.
