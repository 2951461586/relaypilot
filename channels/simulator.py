"""Simulation adapter: virtual channels and scriptable traffic.

Used for demos and tests. Touches no real service. The scenario driver
(sim/scenario.py) uses emit_window() to generate per-key usage windows,
including a scripted "key leak" (traffic spike, odd hour, new region).
"""
from __future__ import annotations

import random
import time

from relaypilot.channels.base import ChannelAdapter, ChannelInfo, ProbeResult


class SimChannelAdapter(ChannelAdapter):
    name = "sim"

    def __init__(self, seed: int = 7):
        self.rng = random.Random(seed)
        self._channels = [
            ChannelInfo("ch-deepseek", "DeepSeek-V3", "openai"),
            ChannelInfo("ch-gpt", "GPT-4o-mini", "openai"),
            ChannelInfo("ch-claude", "Claude-Haiku", "anthropic"),
        ]
        # key_id -> {"channel_id": ..., "status": "active"|"disabled"}
        self._keys: dict[str, dict] = {
            "sk-alice": {"channel_id": "ch-deepseek", "status": "active"},
            "sk-bob": {"channel_id": "ch-gpt", "status": "active"},
            "sk-carol": {"channel_id": "ch-claude", "status": "active"},
            "sk-dave": {"channel_id": "ch-deepseek", "status": "active"},
        }

    # -- ChannelAdapter interface ------------------------------------------

    def list_channels(self) -> list[ChannelInfo]:
        return list(self._channels)

    def probe(self, channel: ChannelInfo) -> ProbeResult:
        latency = self.rng.uniform(80, 320)
        return ProbeResult(channel.channel_id, channel.name, latency, True)

    def list_keys(self) -> list[str]:
        return list(self._keys)

    def quarantine_key(self, key_id: str, reason: str) -> bool:
        if key_id in self._keys:
            self._keys[key_id]["status"] = "disabled"
            return True
        return False

    # -- Scripted traffic ----------------------------------------------------

    def emit_window(self, key_id: str, profile: str = "normal") -> dict:
        """Return one usage window for a key.

        profile="normal": modest traffic, home region, daytime hour.
        profile="leak":   stolen-key traffic — huge spike, 3 AM, new region.
        """
        key = self._keys[key_id]
        if profile == "leak":
            return {
                "key_id": key_id,
                "channel_id": key["channel_id"],
                "requests": self.rng.randint(380, 520),
                "tokens_in": self.rng.randint(180_000, 260_000),
                "tokens_out": self.rng.randint(60_000, 90_000),
                "top_region": "PH-Manila",
                "hour": 3,
            }
        return {
            "key_id": key_id,
            "channel_id": key["channel_id"],
            "requests": self.rng.randint(8, 30),
            "tokens_in": self.rng.randint(2_000, 9_000),
            "tokens_out": self.rng.randint(800, 3_500),
            "top_region": "CN-Hangzhou",
            "hour": 14,
        }

    def key_status(self, key_id: str) -> str:
        return self._keys.get(key_id, {}).get("status", "unknown")

    def key_channel(self, key_id: str) -> str:
        return self._keys.get(key_id, {}).get("channel_id", "unknown")


def build_sim_adapter() -> SimChannelAdapter:
    return SimChannelAdapter()
