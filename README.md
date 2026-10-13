# 🤖 RelayPilot

The AI night-shift engineer for your LLM relay station. Built for the
Hacktoberfest 2026 Open-Source AI Challenge — **Week 2: Side Hustle**.

RelayPilot watches a Veloera / New-API compatible relay station while you sleep:

- 📡 **Channel health monitoring** — scheduled probes: latency, availability, error rate
- 🚨 **Automatic key quarantine** — an open-weight model (Ollama) classifies key usage
  locally; stolen keys get quarantined in minutes. Falls back to built-in heuristic
  rules when Ollama is unreachable. The model only *classifies* — every
  money-adjacent decision (thresholds, quota math) is deterministic code.
- 💬 **Telegram alerts** — three severity levels, quiet hours, daily digest.
  Without a bot token, alerts go to the local log.
- 🔍 **Natural-language ops** — *"昨天哪个渠道烧了最多 token？"* answered from SQLite.

## Quick start (simulation — zero risk)

```bash
cp .env.example .env
pip install -r requirements.txt
chmod +x scripts/demo.sh
./scripts/demo.sh
```

This runs the scripted **key-leak scenario**: normal traffic, then `sk-dave`'s key
starts leaking (traffic spike ×15, 03:00, new region) → WARNING → auto-quarantine +
CRITICAL alert. No real service is touched.

## Run the API

```bash
PYTHONPATH=.. uvicorn relaypilot.api:app --host 127.0.0.1 --port 8099
```

- `GET /` — landing page (same as `site/index.html`)
- `GET /health` — mode + DB status
- `GET /channels` — latest probe per channel
- `GET /keys` — key registry + quarantine status
- `GET /query?q=昨天哪个渠道烧了最多 token？` — natural-language ops
- `POST /monitor/run` — trigger one probe cycle

## Real mode (your own relay station)

```bash
SIMULATION_MODE=0 \
RELAY_API_BASE=https://your-relay.example \
RELAY_ADMIN_KEY=sk-admin-... \
TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=... \
PYTHONPATH=.. uvicorn relaypilot.api:app --host 0.0.0.0 --port 8099
```

Required env for real mode: `RELAY_API_BASE`, `RELAY_ADMIN_KEY`.
Optional: `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` (else log-only alerts),
`OLLAMA_HOST` / `OLLAMA_MODEL` (else heuristic classifier).

The Veloera adapter speaks the New-API/Veloera admin API conventions
(`/api/channel/list`, `/api/token/`). Per-key usage windows in real mode are
ingested from your relay's logs — wire your exporter to `monitor.process_window()`
(see `sim/scenario.py` for the call shape).

## Recording the 90-second demo

1. `./scripts/demo.sh` — terminal shows probe → baseline → leak → quarantine → alert.
2. For the video: run it once clean, then narrate the [1/5]…[5/5] sections.
3. `PYTHONPATH=.. uvicorn relaypilot.api:app` + `curl localhost:8099/query?q=...` for the NLQ shot.
4. Commits after the challenge deadline must be noted in the README (challenge rule).

## Project layout

```
config.py        env-driven settings        db.py            SQLite layer
monitor.py       probe + classify + quarantine pipeline
api.py           FastAPI: /health /channels /keys /query + landing page
channels/        base, veloera (admin API), http_probe, simulator
detector/        ollama_classifier (auto-fallback) + heuristic rules
quarantine/      deterministic quarantine policy
alerts/          telegram (severity, quiet hours, digest) / log fallback
nlq/             template-based natural-language ops queries
sim/             scenario.py — scripted key-leak demo driver
site/            index.html — landing page (for the .tech domain)
scripts/demo.sh  one-click end-to-end demo
```

## License

MIT — see [LICENSE](LICENSE).
