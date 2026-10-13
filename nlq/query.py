"""Natural-language ops queries — pure deterministic code over SQLite.

No LLM required. Matches a handful of Chinese/English templates and answers
from the usage_windows / keys / channel_probes tables.
"""
from __future__ import annotations

import datetime as dt
import re


def _day_bounds(days_ago: int) -> tuple[int, int]:
    today = dt.date.today()
    day = today - dt.timedelta(days=days_ago)
    start = int(dt.datetime.combine(day, dt.time.min).timestamp())
    end = int(dt.datetime.combine(day, dt.time.max).timestamp())
    return start, end


def _top_channel_by_tokens(db_path: str, days_ago: int) -> str:
    from relaypilot import db as dbmod

    start, end = _day_bounds(days_ago)
    label = "昨天" if days_ago == 1 else ("今天" if days_ago == 0 else f"{days_ago}天前")
    with dbmod.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT channel_id, SUM(tokens_in + tokens_out) AS tok, SUM(requests) AS req"
            " FROM usage_windows WHERE window_start BETWEEN ? AND ?"
            " GROUP BY channel_id ORDER BY tok DESC",
            (start, end)).fetchall()
    if not rows:
        return f"{label}没有用量记录。"
    top = rows[0]
    lines = [f"{label}烧 token 最多的是 {top['channel_id']}: "
             f"{top['tok']:,} tokens（{top['req']:,} 次请求）。"]
    for r in rows[1:3]:
        lines.append(f"  其次 {r['channel_id']}: {r['tok']:,} tokens")
    return "\n".join(lines)


def _key_status(db_path: str, key_id: str) -> str:
    from relaypilot import db as dbmod

    key = dbmod.get_key(db_path, key_id)
    if not key:
        return f"没有找到 key {key_id}。"
    if key["status"] == "quarantined":
        ts = dt.datetime.fromtimestamp(key["quarantined_at"]).strftime("%m-%d %H:%M")
        return (f"key {key_id} 已被熔断（{ts}）。"
                f"原因：{key['quarantine_reason'] or '—'}")
    return (f"key {key_id} 状态正常（channel {key['channel_id']}），"
            f"连续可疑窗口 {key['consecutive_suspicious']}。")


def _quarantined_keys(db_path: str) -> str:
    from relaypilot import db as dbmod

    keys = [k for k in dbmod.list_keys(db_path) if k["status"] == "quarantined"]
    if not keys:
        return "当前没有被熔断的 key。"
    return "被熔断的 key：\n" + "\n".join(
        f"  {k['key_id']}（{k['channel_id']}，原因：{k['quarantine_reason'] or '—'}）"
        for k in keys)


def _channel_health(db_path: str) -> str:
    from relaypilot import db as dbmod

    probes = dbmod.latest_probes(db_path)
    if not probes:
        return "还没有渠道探测记录。"
    lines = []
    for p in probes:
        ts = dt.datetime.fromtimestamp(p["ts"]).strftime("%H:%M")
        if p["ok"]:
            lines.append(f"  ✅ {p['channel_name']}: {p['latency_ms']:.0f}ms（{ts}）")
        else:
            lines.append(f"  ❌ {p['channel_name']}: {p['error']}（{ts}）")
    return "渠道健康：\n" + "\n".join(lines)


def answer(db_path: str, question: str) -> str:
    """Answer an ops question with deterministic SQL. Chinese or English."""
    q = question.strip().lower()

    m = re.search(r"sk-[a-z0-9_-]+", q)
    if ("状态" in q or "status" in q) and m:
        return _key_status(db_path, m.group(0))
    if "熔断" in q or "quarantin" in q:
        return _quarantined_keys(db_path)
    if ("token" in q and ("最多" in q or "most" in q)) or "烧" in q:
        days_ago = 1 if ("昨天" in q or "yesterday" in q) else 0
        return _top_channel_by_tokens(db_path, days_ago)
    if "健康" in q or "health" in q or "渠道" in q or "channel" in q:
        return _channel_health(db_path)
    return ("我能回答：昨天/今天哪个渠道烧了最多 token、某个 key 的状态、"
            "被熔断的 key、渠道健康。例如：\"昨天哪个渠道烧了最多 token？\"")
