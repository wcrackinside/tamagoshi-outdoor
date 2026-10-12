# Staging validation — R07

Run on 2026-10-11 against https://outdoor-staging.privantix.io/index.html (static frontend on shared hosting behind
Cloudflare; backend and `gemma3:4b` on the developer machine, CPU only, through a Cloudflare quick tunnel).
Production was not touched.

Browser checks use `frontend/scripts/validate_staging.mjs` (puppeteer-core + Edge):

```
node scripts/validate_staging.mjs <url> <outDir> load        # desktop 1366×900 and mobile 390×844
node scripts/validate_staging.mjs <url> <outDir> flow es|en  # generate → complete → reload, one language
```

## Results (final run, after fixes)

| # | Check | Result |
| --- | --- | --- |
| 1 | Loads on desktop and mobile: 200/304, heading rendered, no horizontal overflow | 12/12 PASS |
| 2 | Missions come from Gemma (`source: gemma`, no fallback) | PASS (ES 148 s, EN 141 s) |
| 3 | Generate, show 3 new missions first, 10 min → 40 pts, complete one | PASS |
| 4 | Points +40 exactly, journal entry with reflection, duplicate completion → 409 | PASS |
| 5 | After reload: points, journal entry and the other pending missions persist | PASS |
| 6 | ES and EN flows; live language toggle (texts, `lang`, date format, default interests) | 16/16 + 16/16 PASS |
| 7 | No JS errors, no failed or 4xx/5xx requests (except the deliberate 409), no missing resources | PASS |
| 8 | No credentials or sensitive data exposed | PASS (see below) |

Backend: `python -m pytest` → **74 passed**. Frontend: `npm run build` OK.

QA completions are tagged in the reflection ("Prueba QA de staging…" / "Staging QA test…") because the staging
journal is shared.

## Defects found and fixed

| Defect | Fix |
| --- | --- |
| Generations longer than ~100 s failed: Cloudflare cuts the request (524, no CORS headers) and the UI said "is the backend on?" | Async jobs: `POST /missions/jobs` returns 202, the UI polls `GET /missions/jobs/{id}` every 3 s for up to 10 min. Clear messages for network errors and timeouts. 7 new tests. |
| `/favicon.ico` 404 on every load | `favicon.svg` linked from `index.html` |
| Default interests stayed in Spanish after switching to English | The default follows the language unless the user edited it |
| Directory listing on `/assets/`, no HTTP→HTTPS redirect, no security headers | `.htaccess`: `Options -Indexes`, 301 to HTTPS, CSP, `nosniff`, `X-Frame-Options DENY`, `Referrer-Policy`, `Permissions-Policy` |
| API `/docs`, `/redoc`, `/openapi.json` public on staging | `EXPOSE_DOCS=0` hides them (default stays on for local dev); 2 new tests |
| Staging watchdog restarted the backend while Gemma saturated the CPU (`/health` > 20 s); the ES run then hit `OLLAMA_TIMEOUT=240` and fell back to demo missions | The watchdog only restarts when nothing listens on port 8000; `OLLAMA_TIMEOUT=420` (the UI waits up to 600 s). The ES re-run used Gemma in 148 s. |

## Security checks (live)

- Served files contain no FTP credentials, tokens or API keys (the word "password" in the bundle is React internals).
- `.env`, `.git/`, `config.env`, backups, the SQLite file and logs are not reachable (403/404).
- `/assets/` → 403. `http://` → 301 to `https://`. Headers present on HTML.
- API `/docs` and `/openapi.json` → 404. CORS answers only the staging origin and localhost.
- Error responses carry no stack traces.

## Remaining observations (not fixed)

- **Shared, unauthenticated staging data**: anyone with the URL can read and write the mission list and journal and
  keep Gemma busy (one generation at a time, others get 429). Acceptable for a demo; stop the tunnel afterwards.
- **Cloudflare Web Analytics (RUM)** is injected by the Cloudflare proxy (`static.cloudflareinsights.com`). The app
  itself has no analytics; the beacon is a zone setting and is allowed by the CSP.
- **Latency**: 2–4 minutes per generation on this CPU. Fallback missions are labeled when Gemma fails.
- **Missions keep their generation language**; switching language does not translate existing missions.
- The API URL is a quick tunnel and changes if `cloudflared` restarts; the watchdog redeploys `config.js` (about a
  minute of downtime).
