# 90-second demo storyboard

Goal: show Gemma running locally and doing real work, the honest fallback, and a real trip outside.
Everything on screen must be the actual app; mark any time-lapse on screen.

Before recording:
- `ollama run gemma3:4b "hi"` once so the model is loaded (the first call also loads ~3 GB into RAM).
- Start backend and frontend (README). Use a fresh DB: set `DB_PATH` to a new file.
- Turn on airplane mode / disconnect Wi-Fi for shots 2–4 to prove it runs offline.

| Time | Shot | On screen | Voice-over / caption |
| --- | --- | --- | --- |
| 0:00–0:08 | Desk, laptop, many tabs open | Real screen clutter | "Long day at the desk. I wanted an app whose best feature is closing it." |
| 0:08–0:15 | App home (ES or EN) | Hero "Less screen. More world." | "Tamagoshi Outdoor suggests three tiny outdoor missions. No account, no GPS." |
| 0:15–0:22 | Wi-Fi off icon, then type interests, pick 10 min | Interests field, time select | "Everything runs on this laptop. Gemma 3 4B via Ollama. I'm offline right now." |
| 0:22–0:35 | Click **Suggest three adventures** | "Gemma is thinking…" notice → 3 cards with GEMMA badge | Caption: "Sped up — real time ~50 s on CPU". "The backend validates Gemma's JSON before anything is shown." |
| 0:35–0:43 | Terminal: `ollama stop gemma3:4b` + stop Ollama, generate again | DEMO badges + notice "Gemma is not available…" | "If the model is down or answers badly, you get clearly labeled demo missions. Never a fake 'AI' label." |
| 0:43–0:50 | Pick one mission, close the laptop lid | Lid closing | "Then the screen goes away." |
| 0:50–1:12 | **Real outdoor footage** of you doing the mission | Park / street / sky | Natural sound. One line about what you actually noticed. |
| 1:12–1:22 | Back at the laptop: write the reflection, click **I am back from my adventure** | Journal entry appears, points go up | "Points are self-reported. No streaks, no guilt." |
| 1:22–1:30 | Repo page + README screenshots | GitHub URL, MIT license | "Open model, open code, data stays in a local SQLite file. Link below." |

Do not include:
- Screenshots or clips from the scripted test runs presented as real outings.
- Claims of verified activity, live hosting, or awards.
