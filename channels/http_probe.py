"""Generic HTTP probe adapter for arbitrary upstream URLs."""
from __future__ import annotations

import time

import requests

from relaypilot.channels.base import ChannelAdapter, ChannelInfo, ProbeResult


class HttpProbeAdapter(ChannelAdapter):
    name = "http"

    def __init__(self, urls: dict[str, str], timeout_s: int = 10):
        # urls: {channel_id: url}
        self.urls = urls
        self.timeout_s = timeout_s

    def list_channels(self) -> list[ChannelInfo]:
        return [ChannelInfo(channel_id=cid, name=cid, kind="http")
                for cid in self.urls]

    def probe(self, channel: ChannelInfo) -> ProbeResult:
        url = self.urls[channel.channel_id]
        started = time.monotonic()
        try:
            r = requests.get(url, timeout=self.timeout_s)
            latency = (time.monotonic() - started) * 1000
            ok = r.status_code < 500
            return ProbeResult(channel.channel_id, channel.name, latency, ok,
                               None if ok else f"HTTP {r.status_code}")
        except Exception as e:  # noqa: BLE001
            return ProbeResult(channel.channel_id, channel.name, None, False,
                               f"{type(e).__name__}: {e}")

    def list_keys(self) -> list[str]:
        return []

    def quarantine_key(self, key_id: str, reason: str) -> bool:
        return False
