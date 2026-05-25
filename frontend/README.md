# Frontend static apps

## Apps
- `public-site` — public entrance page (`/e/:publicCode`)
- `admin-panel` — admin UI with JWT login

## Env files
Copy `.env.example` in each app to `.env` and set API base URL.
No secrets must be stored in frontend env.

## Build
```bash
cd frontend/public-site && npm install && npm run build
cd ../admin-panel && npm install && npm run build
```

Build artifacts are in each app `dist/` directory.

## Static deployment (Yandex Object Storage)
1. Create two buckets for static websites.
2. Upload contents of `dist/` from each app.
3. Configure static hosting and optional CDN.
4. Configure backend API URLs in `.env` before build.
