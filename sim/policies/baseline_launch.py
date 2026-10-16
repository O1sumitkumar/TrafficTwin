"""Run a Tier A baseline with run-time overrides, without editing sim/population/ (M4 ownership).

    python -m sim.policies.baseline_launch friday --routing-threads 8 --gzip

`--routing-threads` overrides `assignment.routing_threads` (the run then records
`routes_deterministic: false`, TA-015); `--gzip` makes the final simulation write gzipped
tripinfo/edgedata/emissions (TA-016: uncompressed 10 % city outputs are ~3 GB). Used for the M4
Friday and Ramadan baselines; integration should fold `--gzip` into baseline.py.
"""

from __future__ import annotations

from pathlib import Path

import typer

import sim.population.baseline as b

app = typer.Typer(add_completion=False, help=__doc__)


def patch(routing_threads: int | None, gz: bool) -> None:
    orig_cfg, orig_run = b.baseline_config, b.run_measured

    def cfg(path: Path = b.BASELINE_CONFIG) -> dict:
        c = orig_cfg(path)
        if routing_threads:
            c["assignment"] = {**c["assignment"], "routing_threads": routing_threads}
        return c

    def run_measured(cmd: list, log: Path, cwd: Path = b.REPO_ROOT) -> dict:
        cmd = [str(c) for c in cmd]
        if gz and cmd and cmd[0].endswith("/sumo") and "--additional-files" in cmd:
            add = Path(cmd[cmd.index("--additional-files") + 1])
            add = add if add.is_absolute() else b.REPO_ROOT / add
            add.write_text(add.read_text().replace('.xml"', '.xml.gz"'))
            i = cmd.index("--tripinfo-output")
            cmd[i + 1] += ".gz"
        return orig_run(cmd, log, cwd)

    b.baseline_config = cfg
    b.run_measured = run_measured


@app.command()
def main(
    daytype: str,
    seed: int = typer.Option(1),
    sample: float = typer.Option(0.10),
    routing_threads: int | None = typer.Option(None),
    gzip: bool = typer.Option(False, "--gzip"),
) -> None:
    patch(routing_threads, gzip)
    b.run_baseline(daytype, seed, sample)


if __name__ == "__main__":
    app()
