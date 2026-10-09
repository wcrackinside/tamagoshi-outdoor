# Cursor agent prompts by release

## R01 — Foundation
Review the existing scaffold. Install dependencies, run backend and frontend, fix issues, commit `feat: foundation R01`. Do not change contest requirements.

## R02 — Open AI
Run Ollama with Gemma locally, test mission generation in Spanish and English. Add robust JSON schema validation and safe fallback labeling. Add tests for invalid AI responses. Commit `feat: mission engine R02`.

## R03 — Adventure loop
Test generating, completing and journaling a mission. Prevent double points, ensure SQLite persists across restarts. Add integration tests. Commit `feat: adventure loop R03`.

## R04 — Adult UX
Review responsive UI and accessibility (keyboard, focus, contrast). Keep experience simple, non-infantile, non-punitive. Add screenshots. Commit `feat: adult UX R04`.

## R05 — QA
Run pytest, npm build, API checks, inspect CORS and prompt injection risks. Document any limitations. Commit `test: QA R05`.

## R06 — Submission
Prepare 90-second demo storyboard, README and DEV English article matching official template. Verify eligibility and submission deadline independently. Do not invent tests, live URLs, screenshots or awards. Commit `docs: submission R06`.
