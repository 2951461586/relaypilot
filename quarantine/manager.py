"""Quarantine manager — deterministic policy, no LLM involved.

Rule: a key is quarantined only when
  1. the detector scores a window >= QUARANTINE_SCORE_THRESHOLD, AND
  2. that happens for QUARANTINE_CONSECUTIVE_WINDOWS windows in a row.

The model only classifies; every money-adjacent decision is this plain code.
"""
from __future__ import annotations

from dataclasses import dataclass

from relaypilot import db as dbmod
from relaypilot.detector.heuristic import Classification


@dataclass
class QuarantineDecision:
    key_id: str
    action: str  # "quarantined" | "watching" | "cleared"
    score: float
    consecutive: int
    reason: str


class QuarantineManager:
    def __init__(self, db_path: str, adapter, alerter,
                 score_threshold: float = 0.75, consecutive_windows: int = 2):
        self.db_path = db_path
        self.adapter = adapter
        self.alerter = alerter
        self.score_threshold = score_threshold
        self.consecutive_windows = consecutive_windows

    def process(self, key_id: str, classification: Classification) -> QuarantineDecision:
        key = dbmod.get_key(self.db_path, key_id)
        if key and key["status"] == "quarantined":
            return QuarantineDecision(key_id, "quarantined",
                                      classification.score, 0, "already quarantined")

        if classification.score >= self.score_threshold:
            consecutive = dbmod.bump_suspicious(self.db_path, key_id)
            if consecutive >= self.consecutive_windows:
                reason = "; ".join(classification.reasons) or \
                    f"score {classification.score} >= {self.score_threshold}"
                ok = self.adapter.quarantine_key(key_id, reason)
                dbmod.mark_quarantined(self.db_path, key_id, reason)
                title = f"🔴 Key quarantined: {key_id}"
                body = (f"Score {classification.score} over {consecutive} consecutive "
                        f"windows.\nReasons: {reason}\n"
                        f"Upstream disable: {'OK' if ok else 'FAILED (check relay API)'}")
                self.alerter.send("CRITICAL", title, body)
                return QuarantineDecision(key_id, "quarantined",
                                          classification.score, consecutive, reason)
            title = f"🟡 Suspicious key: {key_id}"
            body = (f"Score {classification.score} "
                    f"({consecutive}/{self.consecutive_windows} windows).\n"
                    f"Reasons: {'; '.join(classification.reasons)}")
            self.alerter.send("WARNING", title, body)
            return QuarantineDecision(key_id, "watching",
                                      classification.score, consecutive,
                                      "; ".join(classification.reasons))
        dbmod.reset_suspicious(self.db_path, key_id)
        return QuarantineDecision(key_id, "cleared", classification.score, 0, "")
