# Tamagoshi Outdoor — MVP
An open-model companion that nudges screen-bound adults into short, safe outdoor adventures.

## Quick start
1. Install Python 3.10+ and Node 20+.
2. `cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload`
3. In another terminal: `cd frontend && npm install && npm run dev`
4. Open http://localhost:5173

Optional local AI:
- Install Ollama and pull a compatible Gemma model: `ollama pull gemma3:4b`
- Copy `backend/.env.example` to `backend/.env` and set `OLLAMA_MODEL=gemma3:4b`
- Without Ollama, the app explicitly returns curated demo missions.

### How mission generation works
- The backend asks Gemma for exactly three missions as JSON and validates them with a strict Pydantic schema:
  exactly 3 items, string `title` (3–90 chars) and `description` (12–240 chars), distinct titles, no markup,
  control characters or leaked JSON, and no unsafe terms (private property, roofs, traffic, spending money, GPS…).
- Invalid output is retried once (`AI_ATTEMPTS`, default 2). If Gemma is still invalid or unreachable,
  curated demo missions are returned and labeled: `source: "demo"` plus
  `fallback_reason: "ai_unavailable"` or `"ai_invalid_output"`. The UI shows a DEMO badge and an explanation.
- On CPU-only machines a generation takes roughly 40–70 s, and the first call also loads the model,
  so `OLLAMA_TIMEOUT` defaults to 120 s.
- Manual check against a running backend: `python scripts/smoke_api.py`.

## Features
- Adult-focused, Spanish/English UI
- 5/10/15 minute outdoor missions
- Ollama/Gemma mission suggestions with JSON validation
- Safe fallback demo missions
- Manual completion, points, journal and persistent SQLite storage
- No GPS, no accounts, no claims of verified outdoor activity

## API
- GET /health
- POST /missions/generate
- GET /missions
- POST /missions/{id}/complete
- GET /journal

## Competition
Confirm current official rules, submission template, eligibility, and deadline before publishing. This is a new scaffold; don't claim unimplemented features or guaranteed prize eligibility.
