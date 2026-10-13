"""RelayPilot configuration — everything comes from environment variables.

Copy .env.example to .env and fill in your own values. Never commit real
secrets to the repository.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, str(default)))
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "y", "on")


@dataclass
class Settings:
    # --- Relay station (Veloera / New-API compatible) ---
    relay_api_base: str = field(default_factory=lambda: _env("RELAY_API_BASE", ""))
    relay_admin_key: str = field(default_factory=lambda: _env("RELAY_ADMIN_KEY", ""))
    relay_probe_timeout_s: int = field(default_factory=lambda: _env_int("RELAY_PROBE_TIMEOUT_S", 10))

    # --- Simulation mode: virtual channels, no real services touched ---
    simulation_mode: bool = field(default_factory=lambda: _env_bool("SIMULATION_MODE", True))

    # --- Anomaly detector ---
    ollama_host: str = field(default_factory=lambda: _env("OLLAMA_HOST", "http://localhost:11434"))
    ollama_model: str = field(default_factory=lambda: _env("OLLAMA_MODEL", "qwen3:4b"))
    detector_force_heuristic: bool = field(default_factory=lambda: _env_bool("DETECTOR_FORCE_HEURISTIC", False))

    # --- Quarantine policy (all deterministic — the model never decides money) ---
    quarantine_score_threshold: float = field(default_factory=lambda: _env_float("QUARANTINE_SCORE_THRESHOLD", 0.75))
    quarantine_consecutive_windows: int = field(default_factory=lambda: _env_int("QUARANTINE_CONSECUTIVE_WINDOWS", 2))
    window_seconds: int = field(default_factory=lambda: _env_int("WINDOW_SECONDS", 300))

    # --- Telegram alerts ---
    telegram_bot_token: str = field(default_factory=lambda: _env("TELEGRAM_BOT_TOKEN", ""))
    telegram_chat_id: str = field(default_factory=lambda: _env("TELEGRAM_CHAT_ID", ""))
    quiet_hours_start: int = field(default_factory=lambda: _env_int("QUIET_HOURS_START", 23))
    quiet_hours_end: int = field(default_factory=lambda: _env_int("QUIET_HOURS_END", 7))

    # --- Storage / server ---
    db_path: str = field(default_factory=lambda: _env("DB_PATH", "relaypilot.db"))
    host: str = field(default_factory=lambda: _env("HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: _env_int("PORT", 8099))

    def validate(self) -> list[str]:
        """Return a list of human-readable warnings for a real (non-sim) run."""
        warnings: list[str] = []
        if self.simulation_mode:
            return warnings
        if not self.relay_api_base:
            warnings.append("RELAY_API_BASE is empty — set your relay station base URL.")
        if not self.relay_admin_key:
            warnings.append("RELAY_ADMIN_KEY is empty — channel management needs an admin key.")
        if not self.telegram_bot_token or not self.telegram_chat_id:
            warnings.append("Telegram not configured — alerts will go to the local log instead.")
        return warnings


settings = Settings()
