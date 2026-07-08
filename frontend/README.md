# Frontend Guide

## Scope
The frontend is a React + Vite dashboard for:
- upload and analyze
- recent calls
- org overview
- team/advisor analytics
- call detail, transcript review, contestation, and review resolution

## Routes
- `/` — org dashboard
- `/calls` — call list
- `/calls/:callId` — call detail, transcript, flags, and reviews
- `/upload` — upload and analyze a call
- `/team` — team and advisor analytics

## Run Locally
From `frontend/`:

```bash
npm install
npm run dev
```

## Backend Dependency
Set the backend API base URL with a Vite env var:

```env
VITE_API_BASE_URL=http://localhost:8000
```

If `VITE_API_BASE_URL` is omitted, the frontend falls back to same-origin relative requests.

Make sure the backend and database are already running before using the dashboard.

## Review Workflow Note
This submission does not implement auth. For review actions, the call detail page uses a manual “Acting As” selector populated with seeded advisor/team-leader/director identities so the backend can receive `X-Advisor-ID`.

## Current Focus
The frontend is optimized for demonstrating the end-to-end call workflow and the review loop rather than for final production polish.
