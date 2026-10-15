"""Shared fixtures: everything runs on the committed demo window (data/demo/), offline."""

from __future__ import annotations

from pathlib import Path

import pytest

from sim.common import REPO_ROOT

DEMO = REPO_ROOT / "data" / "demo"


@pytest.fixture(scope="session")
def demo_net() -> Path:
    path = DEMO / "demo.net.xml"
    assert path.exists(), "demo window missing: python -m sim.network.build_window --name demo"
    return path


@pytest.fixture(scope="session")
def demo_osm() -> Path:
    return DEMO / "demo.osm.gz"
