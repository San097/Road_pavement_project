# Environment Variables Setup Guide

## 1. Flask Secret Key (Already Generated)
```
FLASK_SECRET_KEY=zdy-lLxBQDoxK1of8eKWx6MOD1sinD3xFL_zhW3gPis
```
This is a cryptographically secure random key for session encryption. Use the value above or generate a new one:
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

## 2. Session Security
```
SESSION_COOKIE_SECURE=1
```
This forces HTTPS-only cookies on Render (production). Set to `0` for local development.

## 3. Data Directory
```
DATA_DIR=/var/data
```
Persistent storage location on Render for user uploads and auth data.

---

## 4. Google OAuth Setup (Optional but Recommended)

### Step 1: Create Google Cloud Project
1. Go to https://console.cloud.google.com
2. Click **Select a Project** → **New Project**
3. Name it `Road Pavement App`
4. Click **Create**

### Step 2: Enable OAuth
1. Go to **APIs & Services** → **Library**
2. Search for `Google+ API` and click **Enable**
3. Go to **OAuth consent screen**
4. Select **External** → **Create**
5. Fill in:
   - **App name:** Road Pavement Project
   - **User support email:** Your email
   - **Developer contact:** Your email
6. Click **Save and Continue**
7. Skip optional scopes, click **Save and Continue**
8. Click **Back to Dashboard**

### Step 3: Create OAuth Credentials
1. Go to **Credentials** → **Create Credentials** → **OAuth client ID**
2. Select **Web application**
3. Add **Authorized JavaScript origins:**
   - `https://your-service-name.onrender.com`
4. Add **Authorized redirect URIs:**
   - `https://your-service-name.onrender.com/login/google/authorized`
   - `https://your-service-name.onrender.com/auth/google/callback`
5. Click **Create**
6. Copy the **Client ID** and **Client Secret**

### Set in Render:
```
GOOGLE_CLIENT_ID=your-copied-client-id
GOOGLE_CLIENT_SECRET=your-copied-client-secret
GOOGLE_REDIRECT_URI=https://your-service-name.onrender.com/login/google/authorized
```

---

## 5. Email Configuration (Optional - for password reset emails)

### Using Gmail with App Password:

#### Step 1: Enable 2-Step Verification
1. Go to https://myaccount.google.com
2. Click **Security** (left sidebar)
3. Enable **2-Step Verification**

#### Step 2: Create App Password
1. Go back to **Security**
2. Find **App passwords** (only visible after 2FA is enabled)
3. Select **Mail** and **Windows Computer** (or your setup)
4. Click **Generate**
5. Copy the 16-character password

### Set in Render:
```
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USER=your_email@gmail.com
EMAIL_PASS=your-16-char-app-password
EMAIL_USE_SSL=0
EMAIL_TIMEOUT=30
```

**DO NOT use your regular Gmail password** — Gmail requires App Passwords for third-party apps.

---

## 6. Server Port (Auto-set by Render)
```
PORT=10000
HOST=0.0.0.0
```
Render automatically sets `PORT`. These are defaults if running locally.

---

## How to Add Environment Variables to Render

1. Deploy your service first (see README)
2. Go to your service dashboard on Render
3. Click **Environment** (left sidebar)
4. Click **Add Environment Variable**
5. Paste each variable and its value:
   - Key: `FLASK_SECRET_KEY`
   - Value: `zdy-lLxBQDoxK1of8eKWx6MOD1sinD3xFL_zhW3gPis`
6. Click **Save**
7. Repeat for each variable
8. Your service will auto-restart with new variables

---

## Local Development (.env file)

For local testing, create `road_pavement_project/.env`:
```
FLASK_SECRET_KEY=dev-secret-key-for-local-testing
SESSION_COOKIE_SECURE=0
DATA_DIR=./data
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
EMAIL_HOST=
EMAIL_USER=
EMAIL_PASS=
PORT=5000
HOST=127.0.0.1
```

Then run locally:
```bash
cd road_pavement_project
python3 app.py
```
or with Docker:
```bash
docker-compose up
```

---

## Summary of Required vs Optional Variables

| Variable | Required? | Purpose |
|----------|-----------|---------|
| `FLASK_SECRET_KEY` | ✅ Yes | Session encryption |
| `SESSION_COOKIE_SECURE` | ✅ Yes | HTTPS enforcement (set to `1` for production) |
| `DATA_DIR` | ✅ Yes | File storage location |
| `GOOGLE_CLIENT_ID` | ❌ Optional | Google sign-in (app works without it) |
| `GOOGLE_CLIENT_SECRET` | ❌ Optional | Google sign-in |
| `GOOGLE_REDIRECT_URI` | ❌ Optional | Google OAuth callback |
| `EMAIL_HOST` | ❌ Optional | Password reset emails (app works without it) |
| `EMAIL_USER` | ❌ Optional | Gmail sender address |
| `EMAIL_PASS` | ❌ Optional | Gmail App Password |
| `PORT` | ✅ Auto-set | Render sets this automatically |

**Minimum to deploy:** `FLASK_SECRET_KEY`, `SESSION_COOKIE_SECURE`, `DATA_DIR`

All other variables are optional — the app runs fine without them, but features like Google OAuth and password reset emails won't work.
