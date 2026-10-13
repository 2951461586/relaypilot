"""Heuristic anomaly classifier — deterministic, no model required.

Scores a usage window 0.0–1.0 from four signals. This is the guaranteed
fallback when Ollama is unreachable, and the reference implementation the
Ollama classifier must agree with in shape.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Classification:
    label: str            # "normal" or "suspicious"
    score: float          # 0.0 - 1.0
    reasons: list[str] = field(default_factory=list)
    engine: str = "heuristic"


# Baselines for a "normal" key window (tunable via constructor).
NORMAL_MAX_REQUESTS = 60
NORMAL_MAX_TOKENS = 20_000
HOME_REGION = "CN-Hangzhou"
ODD_HOURS = set(range(0, 6))  # 00:00 - 05:59


def classify(window: dict, baseline: dict | None = None) -> Classification:
    """Classify one usage window.

    window:   {key_id, channel_id, requests, tokens_in, tokens_out, top_region, hour}
    baseline: optional per-key baseline {"avg_requests":..,"avg_tokens":..,"regions":[...]}
    """
    reasons: list[str] = []
    score = 0.0

    requests = int(window.get("requests", 0))
    tokens = int(window.get("tokens_in", 0)) + int(window.get("tokens_out", 0))
    region = str(window.get("top_region", ""))
    hour = int(window.get("hour", 12))

    # 1. Request-rate spike
    if baseline and baseline.get("avg_requests"):
        ratio = requests / max(1, baseline["avg_requests"])
        if ratio >= 10:
            score += 0.45
            reasons.append(f"request spike x{ratio:.0f} vs baseline")
        elif ratio >= 4:
            score += 0.25
            reasons.append(f"request spike x{ratio:.1f} vs baseline")
    elif requests > NORMAL_MAX_REQUESTS * 5:
        score += 0.45
        reasons.append(f"{requests} requests in one window (normal < {NORMAL_MAX_REQUESTS})")
    elif requests > NORMAL_MAX_REQUESTS:
        score += 0.2
        reasons.append(f"elevated request rate ({requests})")

    # 2. Token burn spike
    if baseline and baseline.get("avg_tokens"):
        ratio = tokens / max(1, baseline["avg_tokens"])
        if ratio >= 10:
            score += 0.3
            reasons.append(f"token burn x{ratio:.0f} vs baseline")
        elif ratio >= 4:
            score += 0.15
            reasons.append(f"token burn x{ratio:.1f} vs baseline")
    elif tokens > NORMAL_MAX_TOKENS * 5:
        score += 0.3
        reasons.append(f"{tokens:,} tokens in one window")

    # 3. New region
    known_regions = set((baseline or {}).get("regions", [HOME_REGION]))
    if region and region not in known_regions:
        score += 0.25
        reasons.append(f"new region {region} (usual: {', '.join(sorted(known_regions))})")

    # 4. Odd hour
    if hour in ODD_HOURS:
        score += 0.2
        reasons.append(f"activity at {hour:02d}:00 (odd hour)")

    score = min(1.0, round(score, 3))
    label = "suspicious" if score >= 0.5 else "normal"
    return Classification(label=label, score=score, reasons=reasons)
