"""RelayPilot HTTP API + status page."""
from __future__ import annotations

import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse

load_dotenv()

from relaypilot import db as dbmod
from relaypilot.config import settings
from relaypilot.monitor import build_stack, probe_cycle
from relaypilot.nlq import answer as nlq_answer

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(name)s %(levelname)s %(message)s")

app = FastAPI(title="RelayPilot", version="0.1.0")

SITE_INDEX = os.path.join(os.path.dirname(__file__), "site", "index.html")

_adapter, _alerter, _qm = None, None, None


def stack():
    global _adapter, _alerter, _qm
    if _adapter is None:
        _adapter, _alerter, _qm = build_stack(settings)
    return _adapter, _alerter, _qm


@app.on_event("startup")
def _startup():
    dbmod.init_db(settings.db_path)
    for w in settings.validate():
        logging.getLogger("relaypilot").warning("config: %s", w)


@app.get("/health")
def health():
    return {"ok": True, "mode": "simulation" if settings.simulation_mode else "real",
            "db": settings.db_path}


@app.get("/channels")
def channels():
    return {"probes": dbmod.latest_probes(settings.db_path)}


@app.get("/keys")
def keys():
    return {"keys": dbmod.list_keys(settings.db_path)}


@app.get("/query")
def query(q: str):
    return {"question": q, "answer": nlq_answer(settings.db_path, q)}


@app.post("/monitor/run")
def monitor_run():
    adapter, _, _ = stack()
    return {"probes": probe_cycle(settings, adapter)}


@app.get("/")
def index():
    if os.path.exists(SITE_INDEX):
        return FileResponse(SITE_INDEX)
    return JSONResponse({"service": "RelayPilot", "see": ["/health", "/channels", "/keys", "/query?q=..."]})
