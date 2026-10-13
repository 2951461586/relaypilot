"""Channel adapters: how RelayPilot talks to upstream relay channels.

All adapters implement ChannelAdapter. In SIMULATION_MODE the SimChannelAdapter
is used; otherwise VeloeraAdapter (Veloera / New-API admin API) is used.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ProbeResult:
    channel_id: str
    channel_name: str
    latency_ms: float | None
    ok: bool
    error: str | None = None


@dataclass
class ChannelInfo:
    channel_id: str
    name: str
    kind: str  # e.g. "openai", "anthropic", "sim"
    status: str = "active"
    extra: dict = field(default_factory=dict)


class ChannelAdapter:
    name = "base"

    def list_channels(self) -> list[ChannelInfo]:  # pragma: no cover
        raise NotImplementedError

    def probe(self, channel: ChannelInfo) -> ProbeResult:  # pragma: no cover
        raise NotImplementedError

    def list_keys(self) -> list[str]:  # pragma: no cover
        raise NotImplementedError

    def key_channel(self, key_id: str) -> str:
        """Channel a key belongs to (for registry bookkeeping)."""
        return "unknown"

    def quarantine_key(self, key_id: str, reason: str) -> bool:  # pragma: no cover
        """Disable a key upstream. Returns True on success."""
        raise NotImplementedError
