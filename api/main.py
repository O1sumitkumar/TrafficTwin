"""FastAPI app stub. Runs, policies, scenarios and streaming arrive in M3."""

from __future__ import annotations

from fastapi import FastAPI

from sim.common import SYNTHETIC_LABEL

app = FastAPI(title="TrafficTwin Jeddah API", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "label": SYNTHETIC_LABEL}
