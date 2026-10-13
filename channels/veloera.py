"""Veloera / New-API compatible channel adapter.

Talks to the relay station's admin API (same conventions as the open-source
Veloera / New-API gateway):
  - GET  {base}/api/channel/list            -> channel inventory
  - GET  {base}/v1/models                   -> lightweight liveness probe
  - GET  {base}/api/token/?p=0&size=100      -> API key inventory
  - PUT  {base}/api/token/  {id, status:2}  -> disable (quarantine) a key

Every call is wrapped in try/except: a failing upstream is a probe result,
never a crash.
"""
from __future__ import annotations

import time

import requests

from relaypilot.channels.base import ChannelAdapter, ChannelInfo, ProbeResult


class VeloeraAdapter(ChannelAdapter):
    name = "veloera"

    def __init__(self, api_base: str, admin_key: str, timeout_s: int = 10):
        self.api_base = api_base.rstrip("/")
        self.admin_key = admin_key
        self.timeout_s = timeout_s

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.admin_key}"}

    def list_channels(self) -> list[ChannelInfo]:
        try:
            r = requests.get(f"{self.api_base}/api/channel/list",
                             headers=self._headers(), timeout=self.timeout_s)
            r.raise_for_status()
            data = r.json().get("data", [])
            return [ChannelInfo(channel_id=str(c.get("id")),
                                name=c.get("name", f"channel-{c.get('id')}"),
                                kind=str(c.get("type", "unknown")),
                                status="active" if c.get("status") == 1 else "disabled")
                    for c in data]
        except Exception:
            return []

    def probe(self, channel: ChannelInfo) -> ProbeResult:
        # Liveness probe via the public models endpoint; latency is what we track.
        started = time.monotonic()
        try:
            r = requests.get(f"{self.api_base}/v1/models",
                             headers=self._headers(), timeout=self.timeout_s)
            latency = (time.monotonic() - started) * 1000
            if r.status_code == 200:
                return ProbeResult(channel.channel_id, channel.name, latency, True)
            return ProbeResult(channel.channel_id, channel.name, latency, False,
                               f"HTTP {r.status_code}")
        except Exception as e:  # noqa: BLE001 - upstream failure is a probe result
            return ProbeResult(channel.channel_id, channel.name, None, False,
                               f"{type(e).__name__}: {e}")

    def list_keys(self) -> list[str]:
        try:
            r = requests.get(f"{self.api_base}/api/token/",
                             params={"p": 0, "size": 100},
                             headers=self._headers(), timeout=self.timeout_s)
            r.raise_for_status()
            items = r.json().get("data", {}).get("items", r.json().get("data", []))
            return [str(t.get("id")) for t in items if isinstance(t, dict)]
        except Exception:
            return []

    def quarantine_key(self, key_id: str, reason: str) -> bool:
        try:
            r = requests.put(f"{self.api_base}/api/token/", json={"id": key_id, "status": 2},
                             headers=self._headers(), timeout=self.timeout_s)
            return r.status_code == 200
        except Exception:
            return False
