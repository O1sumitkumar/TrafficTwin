"""Showreel: every rendered film in order, each after a short title card, joined with crossfades.

    python -m scripts.movies.showreel            # movies/showreel.mp4 (+ .poster.png, .gif, .json)

Inputs are movies/<film>.mp4 in the order of movies/specs/order.yaml (stub specs and films not
rendered yet are skipped and listed), each cut to its spec's `showreel: [start, end]` excerpt so the
reel stays at 2-3 minutes. Title cards are drawn with Pillow (over the film's poster,
blurred and darkened) at the films' size and frame rate; transitions are ffmpeg
`xfade` crossfades, audio-free, H.264 yuv420p CRF 18 like the films.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import typer

from scripts.movies.render import MOVIES_DIR, ffmpeg, make_gif, probe
from scripts.movies.spec import film_names, load_film, load_settings
from sim.common import SYNTHETIC_LABEL

CARD_S = 2.5
XFADE_S = 0.6
FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def font() -> str:
    for f in FONT_CANDIDATES:
        if Path(f).exists():
            return f
    raise FileNotFoundError("no TTF font found for the title cards")


def card_image(film: Any, poster: Path, out: Path, w: int, h: int) -> None:
    """Title card still: the film's poster blurred and darkened, title text centred (Pillow)."""
    from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

    u = h / 1080
    img = Image.open(poster).convert("RGB").resize((w, h))
    img = img.filter(ImageFilter.GaussianBlur(round(14 * u)))
    img = ImageEnhance.Brightness(img).enhance(0.35)
    draw = ImageDraw.Draw(img)
    lines = [
        ("TrafficTwin Jeddah", 22, (231, 183, 95), -110),
        (film.title, 72, (255, 255, 255), -60),
        (film.subtitle, 28, (207, 214, 226), 40),
        (SYNTHETIC_LABEL, 20, (240, 196, 106), 110),
    ]
    for text, size, color, dy in lines:
        f = ImageFont.truetype(font(), round(size * u))
        tw = draw.textlength(text, font=f)
        draw.text(((w - tw) / 2, h / 2 + dy * u), text, font=f, fill=color)
    img.save(out)


def title_card(
    film: Any, poster: Path, out: Path, w: int, h: int, fps: int, r: dict[str, Any]
) -> None:
    still = out.with_suffix(".png")
    card_image(film, poster, still, w, h)
    subprocess.run(
        [
            ffmpeg(),
            "-y",
            "-loglevel",
            "error",
            "-loop",
            "1",
            "-framerate",
            str(fps),
            "-t",
            str(CARD_S),
            "-i",
            str(still),
            "-vf",
            "format=yuv420p",
            "-c:v",
            "libx264",
            "-preset",
            str(r["preset"]),
            "-crf",
            str(r["crf"]),
            "-pix_fmt",
            str(r["pix_fmt"]),
            "-r",
            str(fps),
            str(out),
        ],
        check=True,
    )


def excerpt(film: Any, mp4: Path, out: Path, fps: int, r: dict[str, Any]) -> Path:
    """The `showreel: [start, end]` excerpt of a film (frame-accurate re-encode), or all of it."""
    if film.showreel is None:
        return mp4
    a, b = film.showreel
    subprocess.run(
        [
            ffmpeg(),
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(mp4),
            "-vf",
            f"trim=start_frame={round(a * fps)}:end_frame={round(b * fps)},setpts=PTS-STARTPTS",
            "-c:v",
            "libx264",
            "-preset",
            str(r["preset"]),
            "-crf",
            str(r["crf"]),
            "-pix_fmt",
            str(r["pix_fmt"]),
            "-r",
            str(fps),
            str(out),
        ],
        check=True,
    )
    return out


def build(out_dir: Path = MOVIES_DIR) -> dict[str, Any]:
    r = load_settings()["render"]
    clips: list[tuple[str, Path]] = []
    skipped = []
    for name in film_names():
        film = load_film(name)
        mp4 = out_dir / f"{name}.mp4"
        if film.stub or not mp4.exists():
            skipped.append(name)
            continue
        clips.append((name, mp4))
    if not clips:
        raise FileNotFoundError("no rendered films in movies/ (make movies first)")
    info0 = probe(clips[0][1])
    w, h, fps = info0["width"], info0["height"], round(info0["fps"])
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        parts: list[Path] = []
        for name, mp4 in clips:
            info = probe(mp4)
            if (info["width"], info["height"], round(info["fps"])) != (w, h, fps):
                raise ValueError(f"{name}: size/fps differ from {clips[0][0]}; render all alike")
            film = load_film(name)
            card = tmp / f"{name}.card.mp4"
            title_card(film, out_dir / f"{name}.poster.png", card, w, h, fps, r)
            parts += [card, excerpt(film, mp4, tmp / f"{name}.cut.mp4", fps, r)]
        durations = [probe(p)["duration_s"] for p in parts]
        inputs: list[str] = []
        for p in parts:
            inputs += ["-i", str(p)]
        chain = []
        prev = "[0:v]"
        offset = 0.0
        for k in range(1, len(parts)):
            offset += durations[k - 1] - XFADE_S
            label = f"[v{k}]"
            chain.append(
                f"{prev}[{k}:v]xfade=transition=fade:duration={XFADE_S}:offset={offset:.3f}{label}"
            )
            prev = label
        out = out_dir / "showreel.mp4"
        subprocess.run(
            [
                ffmpeg(),
                "-y",
                "-loglevel",
                "error",
                *inputs,
                "-filter_complex",
                ";".join(chain),
                "-map",
                prev,
                "-c:v",
                "libx264",
                "-preset",
                str(r["preset"]),
                "-crf",
                str(r["crf"]),
                "-pix_fmt",
                str(r["pix_fmt"]),
                "-r",
                str(fps),
                "-movflags",
                "+faststart",
                str(out),
            ],
            check=True,
        )
    info = probe(out)
    poster = out_dir / "showreel.poster.png"
    shutil.copyfile(out_dir / f"{clips[0][0]}.poster.png", poster)
    gif = make_gif(out, out_dir / "showreel.gif", CARD_S + 4.0, r)
    meta = {
        "label": SYNTHETIC_LABEL,
        "films": [n for n, _ in clips],
        "skipped": skipped,
        "card_s": CARD_S,
        "xfade_s": XFADE_S,
        "mp4": info,
        "gif": gif,
    }
    (out_dir / "showreel.json").write_text(json.dumps(meta, indent=1))
    return meta


app = typer.Typer(add_completion=False)


@app.command()
def main(out: Path = typer.Option(MOVIES_DIR, help="directory holding the films")) -> None:
    """Build movies/showreel.mp4 from the rendered films."""
    meta = build(out)
    typer.echo(
        f"showreel: {len(meta['films'])} films, {meta['mp4']['duration_s']:.1f} s"
        f" (skipped: {', '.join(meta['skipped']) or 'none'})"
    )


if __name__ == "__main__":
    app()
