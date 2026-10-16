"""Copy the README/doc previews of rendered films into docs/img/movies/.

    python -m scripts.movies.assets          # (make movies-docs)

For every rendered film: the GIF preview (<= 6 s, <= 3 MB, made by the render) and a 1280 px JPEG
still from the poster frame. movies/ stays git-ignored; these small previews are committed.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import typer

from scripts.movies.render import MOVIES_DIR, ffmpeg
from scripts.movies.spec import film_names
from sim.common import REPO_ROOT

DOCS_IMG = REPO_ROOT / "docs" / "img" / "movies"
STILL_WIDTH = 1280
STILL_QSCALE = 4  # ffmpeg mjpeg quality (2 best .. 31 worst)


def export(out: Path = DOCS_IMG) -> list[str]:
    out.mkdir(parents=True, exist_ok=True)
    done = []
    for name in [*film_names(), "showreel"]:
        poster = MOVIES_DIR / f"{name}.poster.png"
        gif = MOVIES_DIR / f"{name}.gif"
        if not poster.exists():
            continue
        subprocess.run(
            [
                ffmpeg(),
                "-y",
                "-loglevel",
                "error",
                "-i",
                str(poster),
                "-vf",
                f"scale={STILL_WIDTH}:-2",
                "-q:v",
                str(STILL_QSCALE),
                str(out / f"{name}.jpg"),
            ],
            check=True,
        )
        if gif.exists() and name != "showreel":
            shutil.copyfile(gif, out / f"{name}.gif")
        done.append(name)
    return done


app = typer.Typer(add_completion=False)


@app.command()
def main() -> None:
    """Export GIF previews and JPEG stills of the rendered films to docs/img/movies/."""
    typer.echo(f"exported: {', '.join(export()) or 'nothing (render first)'}")


if __name__ == "__main__":
    app()
