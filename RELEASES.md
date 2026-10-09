# Incremental release plan

## R01 — Foundation (0.1.0)
- Independent repository, FastAPI + React/Vite, SQLite, health endpoint
- Acceptance: backend starts, frontend builds, health returns ok

## R02 — Mission engine (0.2.0)
- Interests, duration, Gemma via Ollama, strict JSON validation, explicit demo fallback
- Acceptance: three safe missions generated even when Ollama is offline

## R03 — Adventure loop (0.3.0)
- Mission completion, points, journal, persistence
- Acceptance: completing a mission once adds points; duplicate completion rejected
- Status: completion is a single conditional `UPDATE … WHERE completed_at IS NULL`, so concurrent
  requests award points once (others get 409). `tests/test_adventure_loop.py` covers the full loop,
  concurrency and persistence across a real uvicorn restart.

## R04 — Adult-friendly UX (0.4.0)
- Responsive visual design, ES/EN, clear offline experience
- Acceptance: usable on mobile without GPS, signup or payment
- Status: WCAG AA text contrast (≥4.5:1) and ≥3:1 control borders, visible `:focus-visible` ring,
  labeled controls, logical tab order, live region for progress/fallback notices, localized errors,
  language from browser or `?lang=`, only the latest 3 pending missions shown by default.
  Screenshots in `docs/screenshots/`.

## R05 — QA & hardening (0.5.0)
- Test API, failure handling, security review, optional accessibility audit
- Acceptance: tests pass; fallback identified; no personal data required
- Status: see `docs/QA_REPORT.md` (64 tests, audits clean, CORS/prompt-injection review, limitations).

## R06 — Submission pack (1.0.0)
- README, screenshots, 90-second demo, DEV article in English, license, competition checklist
- Acceptance: links work and claims reflect tested implementation

Scaffold included: R01–R04 baseline + minimal R05 tests + R06 templates.
Not included: real-world GPS verification, production auth, hosting, automated narrative memory.
