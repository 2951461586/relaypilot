"""Open-weight classifier via Ollama, with automatic heuristic fallback.

The model only *classifies* usage windows. It never decides anything
money-adjacent — quarantine thresholds live in quarantine/manager.py and are
plain deterministic code.
"""
from __future__ import annotations

import json

import requests

from relaypilot.detector import heuristic
from .heuristic import Classification


def classify_with_ollama(window: dict, baseline: dict | None,
                         host: str, model: str, timeout_s: int = 20) -> Classification:
    """Ask a local open-weight model to classify the window.

    Raises on any failure — callers should fall back to heuristic.classify.
    """
    prompt = (
        "You are a fraud detector for API key usage. Reply with ONLY a JSON object "
        '{"label": "normal"|"suspicious", "score": 0.0-1.0, "reasons": ["..."]}.\n\n'
        f"Window: requests={window.get('requests')}, "
        f"tokens_in={window.get('tokens_in')}, tokens_out={window.get('tokens_out')}, "
        f"top_region={window.get('top_region')}, hour={window.get('hour')}.\n"
        f"Key baseline: {json.dumps(baseline or {})}\n"
        "A stolen key typically shows: sudden request/token spikes vs baseline, "
        "new regions, and odd-hour activity."
    )
    r = requests.post(f"{host.rstrip('/')}/api/generate",
                      json={"model": model, "prompt": prompt,
                            "stream": False, "format": "json"},
                      timeout=timeout_s)
    r.raise_for_status()
    data = json.loads(r.json().get("response", "{}"))
    label = "suspicious" if data.get("label") == "suspicious" else "normal"
    score = min(1.0, max(0.0, float(data.get("score", 0.0))))
    reasons = [str(x) for x in data.get("reasons", [])][:5]
    return Classification(label=label, score=round(score, 3),
                          reasons=reasons, engine=f"ollama:{model}")


def classify(window: dict, baseline: dict | None = None, *,
             host: str = "http://localhost:11434", model: str = "qwen3:4b",
             force_heuristic: bool = False) -> Classification:
    """Classify with Ollama when available, else the heuristic fallback."""
    if force_heuristic:
        return heuristic.classify(window, baseline)
    try:
        return classify_with_ollama(window, baseline, host, model)
    except Exception:
        fallback = heuristic.classify(window, baseline)
        fallback.engine = f"heuristic (ollama {model} unreachable)"
        return fallback
