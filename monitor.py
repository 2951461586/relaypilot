"""Monitoring cycle: probe channels, classify key windows, enforce quarantine.

In SIMULATION_MODE the sim driver (sim/scenario.py) feeds usage windows.
In real mode, window ingestion from relay logs is wired per deployment
(see README "Real mode"); monitor_cycle() always probes channel health.
"""
from __future__ import annotations

import logging

from relaypilot import db as dbmod
from relaypilot.alerts.telegram import Alerter
from relaypilot.config import Settings
from relaypilot.detector import classify as classify_window
from relaypilot.quarantine import QuarantineManager

log = logging.getLogger("relaypilot.monitor")


def build_baseline(db_path: str, key_id: str) -> dict:
    windows = dbmod.recent_windows(db_path, key_id, limit=12)
    normal = [w for w in windows if not w["suspicious"]]
    pool = normal or windows
    if not pool:
        return {}
    avg_req = sum(w["requests"] for w in pool) / len(pool)
    avg_tok = sum(w["tokens_in"] + w["tokens_out"] for w in pool) / len(pool)
    regions = sorted({w["top_region"] for w in pool if w["top_region"]})
    return {"avg_requests": avg_req, "avg_tokens": avg_tok, "regions": regions}


def process_window(settings: Settings, adapter, alerter: Alerter,
                   qm: QuarantineManager, window: dict) -> dict:
    """Classify one usage window and enforce the quarantine policy."""
    dbmod.upsert_key(settings.db_path, window["key_id"], window["channel_id"])
    baseline = build_baseline(settings.db_path, window["key_id"])
    classification = classify_window(
        window, baseline,
        host=settings.ollama_host, model=settings.ollama_model,
        force_heuristic=settings.detector_force_heuristic,
    )
    dbmod.record_window(
        settings.db_path, key_id=window["key_id"], channel_id=window["channel_id"],
        window_start=window.get("window_start", dbmod.now_s()),
        window_seconds=settings.window_seconds,
        requests=window["requests"], tokens_in=window["tokens_in"],
        tokens_out=window["tokens_out"], top_region=window.get("top_region"),
        suspicious=classification.label == "suspicious", score=classification.score,
    )
    decision = qm.process(window["key_id"], classification)
    return {
        "key_id": window["key_id"],
        "label": classification.label,
        "score": classification.score,
        "reasons": classification.reasons,
        "engine": classification.engine,
        "decision": decision.action,
        "consecutive": decision.consecutive,
    }


def probe_cycle(settings: Settings, adapter) -> list[dict]:
    """Probe every channel once and record results. Returns probe summaries."""
    results = []
    for ch in adapter.list_channels():
        r = adapter.probe(ch)
        dbmod.record_probe(settings.db_path, r.channel_id, r.channel_name,
                           r.latency_ms, r.ok, r.error)
        results.append({"channel": r.channel_name, "ok": r.ok,
                        "latency_ms": r.latency_ms, "error": r.error})
    for key_id in adapter.list_keys():
        dbmod.upsert_key(settings.db_path, key_id, adapter.key_channel(key_id))
    return results


def build_stack(settings: Settings):
    """Build (adapter, alerter, quarantine_manager) for the current settings."""
    from relaypilot.channels import SimChannelAdapter, VeloeraAdapter

    if settings.simulation_mode:
        adapter: object = SimChannelAdapter()
    else:
        adapter = VeloeraAdapter(settings.relay_api_base, settings.relay_admin_key,
                                 settings.relay_probe_timeout_s)
    alerter = Alerter(settings.db_path, settings.telegram_bot_token,
                      settings.telegram_chat_id, settings.quiet_hours_start,
                      settings.quiet_hours_end)
    qm = QuarantineManager(settings.db_path, adapter, alerter,
                           settings.quarantine_score_threshold,
                           settings.quarantine_consecutive_windows)
    return adapter, alerter, qm
