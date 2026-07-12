# AI Job Agent — Frontend

Dark glassmorphism dashboard for the AI Job Application Agent backend.
Vite + React 18 + Tailwind CSS. Fully separate from the backend — all
communication goes through `/api/*`, which the Vite dev server proxies to
`http://127.0.0.1:8000` (see `vite.config.js`). No CORS setup needed.

## Run

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173  (backend must be running on :8000)
```

## What it does

- **Resume panel** — drag & drop a PDF/DOCX; the full pipeline (upload → extract → parse → embed) runs automatically with a live stepper, then shows the parsed candidate preview with skills.
- **Job sourcing panel** — search query + country + per-source toggles (Adzuna / Remotive / Arbeitnow), live per-source ingest stats, one-click vector indexing.
- **Matches panel** — AI-generated matches ranked by blended score, with semantic/skill/ATS bars, matched vs missing skill chips, fit explanations, save/dismiss workflow, and one-click **Tailor Resume** and **Cover Letter** modals.
- Backend health indicator in the header, toast notifications throughout.

## Build for production

```bash
npm run build      # outputs to dist/
```

When deploying, serve `dist/` behind the same origin as the API or set up a
reverse proxy for `/api` — the code never hardcodes a backend URL.
