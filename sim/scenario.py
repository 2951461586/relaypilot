"""Simulated key-leak scenario — the 90-second demo.

Runs entirely in SIMULATION_MODE: virtual channels, scripted traffic, no real
service touched. Flow:
  1. probe all channels (health monitoring)
  2. normal traffic for every key (baseline)
  3. TRIGGER: sk-dave's key starts leaking (spike, 3 AM, new region)
  4. detector flags it -> WARNING alert -> second window -> auto-quarantine + CRITICAL
  5. natural-language ops query + daily digest

Run:  SIMULATION_MODE=1 python -m sim.scenario   (or scripts/demo.sh)
"""
from __future__ import annotations

import logging
import os

logging.basicConfig(level=logging.WARNING, format="%(message)s")

from relaypilot import db as dbmod  # noqa: E402
from relaypilot.config import settings  # noqa: E402
from relaypilot.monitor import build_stack, probe_cycle, process_window  # noqa: E402
from relaypilot.nlq import answer as nlq_answer  # noqa: E402


def banner(text: str) -> None:
    print("\n" + "=" * 64)
    print(text)
    print("=" * 64)


def main() -> int:
    settings.simulation_mode = True
    if os.path.exists(settings.db_path):
        os.remove(settings.db_path)
    dbmod.init_db(settings.db_path)

    adapter, alerter, qm = build_stack(settings)

    banner("[1/5] Channel health monitoring — probing 3 virtual channels")
    for p in probe_cycle(settings, adapter):
        status = "OK " if p["ok"] else "FAIL"
        print(f"  [{status}] {p['channel']:15s} latency {p['latency_ms']:.0f}ms")

    # Register keys and feed normal traffic (builds the baseline).
    for key_id in adapter.list_keys():
        dbmod.upsert_key(settings.db_path, key_id, adapter.key_channel(key_id))

    banner("[2/5] Normal traffic — 3 windows per key (baseline learning)")
    for round_ in range(1, 4):
        for key_id in ("sk-alice", "sk-bob", "sk-carol", "sk-dave"):
            w = adapter.emit_window(key_id, "normal")
            res = process_window(settings, adapter, alerter, qm, w)
            print(f"  round {round_} {key_id:10s} -> {res['label']:10s} "
                  f"score {res['score']:.2f} [{res['engine']}]")

    banner("[3/5] 🚨 TRIGGER: sk-dave's key starts leaking "
           "(request spike x15, 03:00, new region PH-Manila)")
    for i in range(1, 4):
        w = adapter.emit_window("sk-dave", "leak")
        res = process_window(settings, adapter, alerter, qm, w)
        print(f"  leak window {i} sk-dave -> {res['label']:10s} "
              f"score {res['score']:.2f} decision={res['decision']}")
        for r in res["reasons"]:
            print(f"      - {r}")

    banner("[4/5] Natural-language ops query")
    q = "今天哪个渠道烧了最多 token？"
    print(f"  Q: {q}")
    print(f"  A: {nlq_answer(settings.db_path, q)}")
    q2 = "sk-dave 的状态？"
    print(f"  Q: {q2}")
    print(f"  A: {nlq_answer(settings.db_path, q2)}")

    banner("[5/5] Daily digest")
    print("  " + alerter.daily_digest().replace("\n", "\n  "))

    banner("Demo complete — key states")
    for k in dbmod.list_keys(settings.db_path):
        print(f"  {k['key_id']:10s} channel={k['channel_id']:12s} status={k['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
