# QA report — R05

Run on 2026-10-09, Windows 10 (19045), Python 3.10.7, Node 22.14.0, Ollama 0.33.3 with `gemma3:4b` on CPU only.

## Automated checks

| Check | Command | Result |
| --- | --- | --- |
| Backend tests | `cd backend && python -m pytest` | 64 passed |
| Frontend build | `cd frontend && npm run build` | OK (Vite 8.3.4) |
| JS dependencies | `npm audit` | 0 vulnerabilities |
| Python dependencies | `pip-audit -r requirements.txt` | No known vulnerabilities |
| Compose file | `docker compose config --quiet` | Valid |

Test suites: `test_api.py` (basics), `test_mission_engine.py` (AI schema validation, invalid outputs, retry, fallback
labeling), `test_adventure_loop.py` (full loop, double completion, 8 concurrent completions, persistence across a real
uvicorn restart), `test_security.py` (CORS, prompt-injection handling, SQL-injection text, no personal-data fields).

## Manual API checks (live backend)

- `GET /health` → `{"ok":true}`, also through the Vite proxy `/api/health`.
- `POST /missions/generate` with `language: "fr"` or malformed JSON → 422. Completing an unknown mission → 404.
- CORS preflight from `http://localhost:5173` → `access-control-allow-origin` echoed; from `https://evil.example` → no header.
- `python backend/scripts/smoke_api.py`: Spanish and English generation both returned `source: gemma`
  (4/4 requests after the R02 fixes), 38–84 s per request on this CPU.
- Raw Gemma validity without the retry, measured over 6 calls: 5/6 valid. The failure was a missing comma, which the
  validator rejected and the retry absorbs.

## Security review

- **CORS**: origins come from `CORS_ORIGINS` (default: the Vite dev origin), methods limited to GET/POST, header to
  `Content-Type`, no credentials. CORS is not authentication; see limitations.
- **Network exposure** (fixed): `npm run dev` used `--host 0.0.0.0`, publishing the dev server and its `/api` proxy on
  the LAN. It now binds to localhost; `npm run dev:lan` is the explicit opt-in. Docker Compose ports are bound to
  `127.0.0.1`.
- **Prompt injection**: user interests are stripped of control characters, quotes, brackets and backslashes, capped at
  200 chars and wrapped in `<interests>` tags the model is told to treat as themes only. Independently of what the model
  does, output must pass the schema, the markup/leaked-JSON check and the unsafe-term denylist, otherwise demo missions
  are served. Live test: two injection payloads (asking for roofs/private property, `<script>`, home address) both
  produced ordinary safe missions from Gemma.
- **XSS**: React escapes all model and user text; there is no `dangerouslySetInnerHTML`.
- **SQL injection**: all queries are parameterized; a `'); DROP TABLE missions; --` reflection is stored verbatim.
- **Personal data**: requests carry only interests, duration, language and an optional reflection. No accounts, GPS,
  or analytics. Data stays in the local SQLite file.
- **Container build** (fixed): added `.dockerignore` files so host `node_modules`/`.venv`/DB files are not copied
  into images; frontend image uses `npm ci` on Node 22.

## Known limitations

- **Not tested**: Docker images were not built or run because the Docker engine was not running on the test machine.
- **No authentication or rate limiting.** Designed as a single-user local app. Do not expose port 8000 publicly.
- **Latency**: on CPU, one generation takes ~40–85 s; with one retry, worst case is about 2 × `OLLAMA_TIMEOUT`.
  Concurrent generations queue inside Ollama.
- **Safety filter is a keyword denylist** (English/Spanish). It can miss paraphrased unsafe advice and the model can
  still suggest equipment (e.g. binoculars) or mildly odd wording. Missions are suggestions; users judge their own safety.
- **Language is requested, not verified**: the backend does not detect whether Gemma answered in the requested language.
- **Model quality**: `gemma3:4b` occasionally repeats titles across batches or produces typos.
- **Completion is self-reported**: points reflect what the user logs, not verified outdoor activity.
- **Journal is local and unencrypted** in SQLite; there is no export, edit or delete UI.
- Tested on Windows only; Python 3.10 locally (the Docker image uses 3.11).

## Updates after R05 (2026-10-11)

- `python -m pytest`: **65 passed** (new: a second generation while one is running gets HTTP 429 and stores nothing).
  `npm run build` OK.
- Browser notification when missions are ready (only if the tab is hidden; otherwise the tab title gets a ✓). Checked
  in the browser with a stubbed `Notification`: one notification with the three mission titles.
- Staging: the static frontend is on shared hosting; the backend runs on the developer machine behind a Cloudflare
  quick tunnel. Checked live: CORS allows only the staging origin (plus localhost), and a generation from that origin
  through the tunnel returned `source: gemma` in 120 s.
- **Staging risk**: this deliberately exposes the API publicly, against the single-user limitation above. Mitigations:
  one generation at a time (429 otherwise), a separate `staging.db`, no personal data fields. Still no authentication:
  anyone with the URL can read and write the shared mission list and journal, and can keep Gemma busy. Stop the tunnel
  when the demo is over.

## R07 staging validation (2026-10-11)

`python -m pytest`: **74 passed**. Browser validation of staging, defects fixed and remaining observations are in
[STAGING_VALIDATION.md](STAGING_VALIDATION.md). The "no analytics" statement above applies to the app; on staging the
Cloudflare proxy injects its Web Analytics beacon.
