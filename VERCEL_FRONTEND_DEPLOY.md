# Vercel Frontend Deployment

This project currently uses Flask/Jinja templates in `road_pavement_project/templates`.
There is no separate React or Vite frontend in this repository yet, so there are no
`fetch()` API calls to update with `REACT_APP_API_URL` or `VITE_API_URL`.

## If You Add A React Frontend

Create the frontend in its own folder, for example:

```text
frontend/
  package.json
  src/
  public/
```

Use this API base in React:

```javascript
const API_URL = process.env.REACT_APP_API_URL || "http://localhost:5000";

fetch(`${API_URL}/predict`, {
  method: "POST",
  body: formData,
  credentials: "include",
});
```

Use this API base in Vite:

```javascript
const API_URL = import.meta.env.VITE_API_URL || "http://localhost:5000";

fetch(`${API_URL}/predict`, {
  method: "POST",
  body: formData,
  credentials: "include",
});
```

## Vercel Settings

- Framework Preset: React, Vite, or the framework used by `frontend/package.json`
- Root Directory: `frontend`
- Build Command: `npm run build`
- Output Directory: `build` for Create React App, `dist` for Vite

Add one environment variable:

```text
REACT_APP_API_URL=https://your-render-service.onrender.com
```

For Vite:

```text
VITE_API_URL=https://your-render-service.onrender.com
```

## Render Backend Settings

Add this on Render after Vercel gives you the frontend URL:

```text
FRONTEND_ORIGINS=https://your-vercel-app.vercel.app
SESSION_COOKIE_SECURE=1
SESSION_COOKIE_SAMESITE=None
DATABASE_URL=<your Render PostgreSQL URL>
```

If you use a custom Vercel domain, add both origins separated by a comma:

```text
FRONTEND_ORIGINS=https://your-vercel-app.vercel.app,https://your-domain.com
```
