"""Integration wiring: sim.runner dispatch and the event registry (no simulation)."""

from __future__ import annotations

import contextlib
from pathlib import Path
from typing import Any

import pytest

from sim import runner
from sim.events import registry


def test_runner_routes_evacuation_scenarios(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[tuple[str, Any]] = []

    def fake_evac(ref: str, window: str | None, seed: int, **kw: Any) -> dict[str, Any]:
        calls.append(("evac", ref))
        (tmp_path / "evacuation_report.md").write_text("ok")
        return {"out": tmp_path}

    def fake_scen(ref: str, *a: Any, **kw: Any) -> dict[str, Any]:
        calls.append(("scenario", ref))
        return {}

    monkeypatch.setattr("sim.events.evacuation.run", fake_evac)
    monkeypatch.setattr("sim.scenarios.run.run_scenario", fake_scen)
    runner.run_scenario_cli("evac_demo", None, 1, tmp_path)
    runner.run_scenario_cli("accident_tahlia", None, 1, tmp_path)
    assert calls == [("evac", "evac_demo"), ("scenario", "accident_tahlia")]


def test_build_events_registers_evacuation_lazily(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delitem(registry.EVENT_CLASSES, "evacuation", raising=False)
    # the stub plan is incomplete; only the registration matters here
    with contextlib.suppress(Exception):
        registry.build_events([{"type": "evacuation"}])
    assert "evacuation" in registry.EVENT_CLASSES
