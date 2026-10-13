"""Alerting: Telegram with severity levels, quiet hours, and daily digest.

Severity: INFO < WARNING < CRITICAL.
Quiet hours (default 23:00–07:00): WARNING/INFO are held until morning;
CRITICAL always goes through immediately.
Without TELEGRAM_BOT_TOKEN/CHAT_ID, everything goes to the local log
(and the DB), so the pipeline works out of the box.
"""
from __future__ import annotations

import datetime as dt
import logging

log = logging.getLogger("relaypilot.alerts")

SEVERITY_RANK = {"INFO": 0, "WARNING": 1, "CRITICAL": 2}


class Alerter:
    def __init__(self, db_path: str, bot_token: str = "", chat_id: str = "",
                 quiet_start: int = 23, quiet_end: int = 7):
        self.db_path = db_path
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.quiet_start = quiet_start
        self.quiet_end = quiet_end
        self._bot = None
        if bot_token and chat_id:
            try:
                from telegram import Bot
                self._bot = Bot(token=bot_token)
            except Exception as e:  # noqa: BLE001
                log.warning("telegram init failed (%s) — using local log", e)

    def _in_quiet_hours(self, now: dt.datetime | None = None) -> bool:
        h = (now or dt.datetime.now()).hour
        if self.quiet_start <= self.quiet_end:
            return self.quiet_start <= h < self.quiet_end
        return h >= self.quiet_start or h < self.quiet_end

    def send(self, severity: str, title: str, body: str) -> bool:
        """Send an alert. Returns True if it reached Telegram."""
        from relaypilot import db as dbmod

        severity = severity.upper()
        held = severity != "CRITICAL" and self._in_quiet_hours()
        text = f"[{severity}] {title}\n{body}"
        if held:
            text += "\n(held: quiet hours — will be included in the morning digest)"

        delivered = False
        if self._bot and not held:
            try:
                import asyncio
                asyncio.run(self._bot.send_message(chat_id=self.chat_id, text=text))
                delivered = True
            except Exception as e:  # noqa: BLE001
                log.warning("telegram send failed (%s) — falling back to log", e)

        if not delivered:
            log.warning("ALERT %s", text.replace("\n", " | "))
        dbmod.record_alert(self.db_path, severity, title, body, delivered)
        return delivered

    def daily_digest(self) -> str:
        """Build a digest of the last 24h of alerts. Returns the text."""
        from relaypilot import db as dbmod

        since = int(dt.datetime.now().timestamp()) - 86400
        items = dbmod.alerts_since(self.db_path, since)
        if not items:
            return "📋 Daily digest: no alerts in the last 24h. All quiet."
        lines = [f"📋 Daily digest ({len(items)} alerts, last 24h):"]
        for a in items:
            ts = dt.datetime.fromtimestamp(a["ts"]).strftime("%H:%M")
            lines.append(f"  {ts} [{a['severity']}] {a['title']}")
        digest = "\n".join(lines)
        self.send("INFO", "Daily digest", digest)
        return digest
