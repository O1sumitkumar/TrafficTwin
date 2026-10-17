"""Voice-over for the films: narration scripts -> speech -> timing, voice track and subtitles.

    uv run python -m scripts.movies.narrate validate          # movies/specs/*.narration.yaml
    uv run python -m scripts.movies.narrate speak evacuation  # WAVs + timing for one film
    make voice-setup                                          # the offline TTS venv (.venv-tts)

A narration script (`movies/specs/<film>.narration.yaml`) has 4-8 plain-English lines, each tied to
a shot of the film: `at` (seconds into the shot, i.e. a camera moment) or `sim_t` (the moment the
shot's sim clock reaches it), or neither (straight after the line before). The last line is the
caveat. Every number spoken must already be in the docs (`NUMBER_DOCS`); `validate` checks that.

Each line is spoken by Kokoro-82M (scripts/movies/tts_kokoro.py, run in `.venv-tts`; cached per
text + voice + versions under runs/movies/_voice/). The measured durations set the timing: a line
starts at its anchor, never before the previous line has ended (+ gap), and the shot is slowed down
(camera keyframes stretched, the sim time-lapse rate drops) until its last line ends inside it:
shots stretch to fit speech, never the reverse. `apply_timing` returns the stretched film;
`voice_track` mixes the lines into one WAV of the film's length; `write_srt` writes the subtitles.
Same script + model + settings => same samples (seeded TTS), so the voice track hash is stable.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import subprocess
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import typer
import yaml
from pydantic import Field, model_validator

from scripts.movies.spec import SPECS_DIR, Film, Strict, film_names, load_film, load_settings
from sim.common import REPO_ROOT

NARRATION_SUFFIX = ".narration.yaml"
TTS_WORKER = Path(__file__).with_name("tts_kokoro.py")
# numbers spoken in a narration must appear in one of these (MOVIES_V2: never invent a number)
NUMBER_DOCS = [
    "docs/policies.md",
    "docs/loop.md",
    "docs/evacuation.md",
    "docs/strategist.md",
    "docs/events.md",
    "docs/movies.md",
]
CAVEAT_WORDS = ("synthetic", "uncalibrated")


class Line(Strict):
    text: str = Field(min_length=3)
    shot: str | None = None  # film narration: shot id the line belongs to
    film: str | None = None  # showreel narration: film whose excerpt the line belongs to
    at: float | None = Field(default=None, ge=0)  # seconds into the shot (camera moment)
    sim_t: float | None = None  # or: when the shot's sim clock reaches this

    @model_validator(mode="after")
    def _anchor(self) -> Line:
        if (self.shot is None) == (self.film is None):
            raise ValueError(f"line {self.text[:30]!r}: give exactly one of `shot` or `film`")
        if self.at is not None and self.sim_t is not None:
            raise ValueError(f"line {self.text[:30]!r}: give `at` or `sim_t`, not both")
        return self


class Narration(Strict):
    film: str
    voice: str | None = None  # default: settings voice.voice (one voice for every film)
    lines: list[Line] = Field(min_length=1, max_length=12)


def narration_path(film: str) -> Path:
    return SPECS_DIR / f"{film}{NARRATION_SUFFIX}"


def load_narration(film: str) -> Narration | None:
    path = narration_path(film)
    if not path.exists():
        return None
    nar = Narration.model_validate(yaml.safe_load(path.read_text()))
    if nar.film != film:
        raise ValueError(f"{path.name}: film {nar.film!r} must be {film!r}")
    return nar


# ----------------------------------------------------------------------------- checks


NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _numbers(text: str) -> list[str]:
    return [m.group(0).rstrip(",").replace(",", "") for m in NUM_RE.finditer(text)]


def doc_numbers() -> set[str]:
    nums: set[str] = set()
    for d in NUMBER_DOCS:
        p = REPO_ROOT / d
        if p.exists():
            nums.update(_numbers(p.read_text()))
    return nums


def check(nar: Narration, film: Film | None, known: set[str]) -> list[str]:
    """Problems with a narration script (empty list = OK)."""
    errs = []
    if film is not None:
        if not 4 <= len(nar.lines) <= 8:
            errs.append(f"{len(nar.lines)} lines (want 4-8)")
        ids = [s.id for s in film.shots]
        order = [ids.index(ln.shot) if ln.shot in ids else -1 for ln in nar.lines]
        if -1 in order:
            errs.append(f"unknown shot in {[ln.shot for ln in nar.lines if ln.shot not in ids]}")
        elif order != sorted(order):
            errs.append("lines must follow the shot order")
    last = nar.lines[-1].text.lower()
    if not all(w in last for w in CAVEAT_WORDS):
        errs.append("the last line must be the caveat (synthetic demand, uncalibrated)")
    for ln in nar.lines:
        for n in _numbers(ln.text):
            if n not in known:
                errs.append(f"number {n} in {ln.text[:40]!r} is not in {', '.join(NUMBER_DOCS)}")
    return errs


# ----------------------------------------------------------------------------- speech


def _settings() -> dict[str, Any]:
    return load_settings()["voice"]


def tts_python() -> Path:
    py = REPO_ROOT / str(_settings()["venv"]) / "bin" / "python"
    if not py.exists():
        raise FileNotFoundError(f"{py} missing: run `make voice-setup` (offline TTS venv)")
    return py


def tts_env() -> dict[str, str]:
    env = dict(os.environ)
    env.setdefault("HF_HUB_OFFLINE", "1")  # the model is in the HF cache after voice-setup
    env.setdefault("TOKENIZERS_PARALLELISM", "false")
    env.pop("VIRTUAL_ENV", None)
    return env


_VERSIONS: dict[str, str] | None = None


def tts_versions() -> dict[str, str]:
    global _VERSIONS
    if _VERSIONS is None:
        res = subprocess.run(
            [str(tts_python()), str(TTS_WORKER), "--versions"],
            capture_output=True, text=True, check=True, env=tts_env(),
        )  # fmt: skip
        _VERSIONS = json.loads(res.stdout.strip().splitlines()[-1])
    return _VERSIONS


def voice_dir() -> Path:
    return REPO_ROOT / "runs" / "movies" / "_voice"


def line_key(text: str, voice: str, cfg: dict[str, Any], ver: dict[str, str]) -> str:
    raw = json.dumps([text, voice, cfg["speed"], cfg["seed"], ver], sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def wav_seconds(path: Path) -> float:
    with wave.open(str(path)) as w:
        return w.getnframes() / w.getframerate()


def speak(texts: list[str], voice: str) -> list[Path]:
    """WAV per text (cached); missing ones are synthesised in one TTS process."""
    cfg = _settings()
    ver = tts_versions()
    paths = [voice_dir() / f"{line_key(t, voice, cfg, ver)}.wav" for t in texts]
    jobs = [{"text": t, "out": str(p)} for t, p in zip(texts, paths, strict=True) if not p.exists()]
    if jobs:
        cmd = [str(tts_python()), str(TTS_WORKER), "--voice", voice, "--speed", str(cfg["speed"]),
               "--seed", str(cfg["seed"])]  # fmt: skip
        res = subprocess.run(
            cmd, input=json.dumps(jobs), capture_output=True, text=True, env=tts_env()
        )
        if res.returncode != 0:
            raise RuntimeError(f"TTS failed: {res.stderr[-2000:]}")
    missing = [p for p in paths if not p.exists()]
    if missing:
        raise RuntimeError(f"TTS wrote no audio for {missing}")
    return paths


# ----------------------------------------------------------------------------- timing


@dataclass
class Timed:
    text: str
    wav: Path
    seconds: float
    start_s: float = 0.0
    shot: str = ""

    @property
    def end_s(self) -> float:
        return self.start_s + self.seconds


@dataclass
class Timing:
    film: str
    voice: str
    lines: list[Timed]
    stretch: dict[str, float]  # shot id -> factor (1 = unchanged)
    duration_s: float
    versions: dict[str, str] = field(default_factory=dict)

    def as_json(self) -> dict[str, Any]:
        return {
            "film": self.film,
            "voice": self.voice,
            "duration_s": round(self.duration_s, 4),
            "stretch": {k: round(v, 5) for k, v in self.stretch.items()},
            "lines": [
                {
                    "text": t.text,
                    "shot": t.shot,
                    "start_s": round(t.start_s, 3),
                    "end_s": round(t.end_s, 3),
                    "seconds": round(t.seconds, 3),
                    "wav": t.wav.name,
                }
                for t in self.lines
            ],  # fmt: skip
            "versions": self.versions,
        }


def _sim_anchor(shot: Any, sim_t: float) -> float:
    """Shot-local time when the shot's sim clock reaches sim_t (keyframes, linear between)."""
    keys = [(k.t, k.sim_t) for k in shot.camera if k.sim_t is not None]
    if len(keys) == 1 or sim_t <= keys[0][1]:
        return keys[0][0] if sim_t <= keys[0][1] else keys[-1][0]
    for (t0, s0), (t1, s1) in zip(keys, keys[1:], strict=False):
        if s0 <= sim_t <= s1 and s1 > s0:
            return t0 + (sim_t - s0) / (s1 - s0) * (t1 - t0)
    return keys[-1][0]


def plan_timing(
    film: Film, nar: Narration, seconds: list[float], wavs: list[Path], fps: int | None = None
) -> Timing:
    """Place the lines, find each shot's stretch (with `fps`: stretched shots last whole frames)."""
    cfg = _settings()
    gap, lead, tail = float(cfg["gap_s"]), float(cfg["lead_s"]), float(cfg["tail_s"])
    by_shot: dict[str, list[int]] = {}
    for i, ln in enumerate(nar.lines):
        by_shot.setdefault(str(ln.shot), []).append(i)
    timed = [Timed(ln.text, w, s, shot=str(ln.shot)) for ln, w, s in zip(nar.lines, wavs, seconds,
                                                                        strict=True)]  # fmt: skip
    stretch: dict[str, float] = {}
    shot_start = 0.0
    prev_end = film.title_card_s + float(cfg["after_title_s"]) - gap
    for shot in film.shots:
        idx = by_shot.get(shot.id, [])
        base = []
        for i in idx:
            ln = nar.lines[i]
            if ln.at is not None:
                base.append(ln.at)
            elif ln.sim_t is not None:
                base.append(_sim_anchor(shot, ln.sim_t))
            else:
                base.append(None)
        k = 1.0
        for _ in range(50):
            p = prev_end
            for j, i in enumerate(idx):
                anchor = shot_start + max(lead, (base[j] or 0.0) * k) if base[j] is not None else 0
                timed[i].start_s = max(p + gap, anchor, shot_start + lead)
                p = timed[i].end_s
            need = (p + tail - shot_start) if idx else 0.0
            if need <= shot.duration_s * k + 1e-6:
                break
            k = need / shot.duration_s
            if fps:  # a whole number of frames, so the film's length is exact
                k = math.ceil(shot.duration_s * k * fps - 1e-6) / (fps * shot.duration_s)
        stretch[shot.id] = k
        if idx:
            prev_end = timed[idx[-1]].end_s
        shot_start += shot.duration_s * k
    return Timing(film.film, "", timed, stretch, shot_start)


def apply_timing(film: Film, timing: Timing) -> Film:
    """The film with every shot (camera keyframes, duration) stretched by its factor."""
    data = film.model_dump()
    old_bounds, new_bounds = [], []
    o = n = 0.0
    for shot in data["shots"]:
        k = timing.stretch.get(shot["id"], 1.0)
        old_bounds.append((o, o + shot["duration_s"], k))
        new_bounds.append(n)
        o += shot["duration_s"]
        shot["duration_s"] = round(shot["duration_s"] * k, 6)
        for key in shot["camera"]:
            key["t"] = round(key["t"] * k, 6)
        n += shot["duration_s"]
    data["duration_s"] = round(sum(s["duration_s"] for s in data["shots"]), 6)

    def remap(t: float) -> float:
        for (a, b, k), s0 in zip(old_bounds, new_bounds, strict=True):
            if t <= b + 1e-9:
                return round(s0 + (t - a) * k, 3)
        return data["duration_s"]

    if data.get("showreel"):
        data["showreel"] = [remap(data["showreel"][0]), remap(data["showreel"][1])]
    return Film.model_validate(data)


def prepare(film: Film, fps: int | None = None) -> Timing | None:
    """Speak a film's narration (cached) and plan its timing; None when the film has none."""
    nar = load_narration(film.film)
    if nar is None:
        return None
    voice = nar.voice or str(_settings()["voice"])
    wavs = speak([ln.text for ln in nar.lines], voice)
    timing = plan_timing(film, nar, [wav_seconds(w) for w in wavs], wavs, fps)
    timing.voice = voice
    timing.versions = tts_versions()
    k_max = max(timing.stretch.values(), default=1.0)
    if k_max > float(_settings()["max_stretch"]):
        print(f"[narrate] {film.film}: a shot is stretched x{k_max:.2f} to fit its speech")
    return timing


# ----------------------------------------------------------------------------- audio + subtitles


def _read_wav(path: Path) -> np.ndarray:
    with wave.open(str(path)) as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.int32)


def voice_track(lines: list[tuple[float, Path]], duration_s: float, out: Path) -> str:
    """Mix (start_s, wav) lines into one 16-bit mono WAV of duration_s; return its sha256[:16]."""
    rate = int(_settings()["sample_rate"])
    n = int(round(duration_s * rate))
    mix = np.zeros(n, dtype=np.int32)
    for start, wav in lines:
        a = _read_wav(wav)
        i = int(round(start * rate))
        j = min(n, i + len(a))
        if i < n:
            mix[i:j] += a[: j - i]
    pcm = np.clip(mix, -32768, 32767).astype("<i2").tobytes()
    out.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    return hashlib.sha256(pcm).hexdigest()[:16]


def _srt_time(t: float) -> str:
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def write_srt(lines: list[tuple[float, float, str]], out: Path) -> None:
    blocks = [
        f"{k}\n{_srt_time(a)} --> {_srt_time(b)}\n{text}\n"
        for k, (a, b, text) in enumerate(lines, start=1)
    ]
    out.write_text("\n".join(blocks), encoding="utf-8")


# ----------------------------------------------------------------------------- CLI

app = typer.Typer(add_completion=False, help=__doc__)


@app.callback()
def _cli() -> None:
    """Film narration tools."""


@app.command()
def validate() -> None:
    """Check every narration script: anchors, 4-8 lines, caveat last, numbers from the docs."""
    known = doc_numbers()
    bad = 0
    paths = sorted(SPECS_DIR.glob(f"*{NARRATION_SUFFIX}"))
    for path in paths:
        name = path.name[: -len(NARRATION_SUFFIX)]
        try:
            nar = load_narration(name)
            assert nar is not None
            film = load_film(name) if name in film_names() else None
            errs = check(nar, film, known)
        except (ValueError, OSError) as exc:
            errs = [str(exc)]
        bad += bool(errs)
        detail = "".join(f"\n     {e}" for e in errs)
        typer.echo(f"{'FAIL' if errs else 'OK  '} {path.name}{detail}")
    missing = [n for n in film_names() if not narration_path(n).exists() and not load_film(n).stub]
    for n in missing:
        typer.echo(f"WARN {n}: no narration script")
    raise typer.Exit(1 if bad else 0)


@app.command("speak")
def speak_cmd(film: str) -> None:
    """Synthesise one film's narration and print the timing (shot stretch factors)."""
    timing = prepare(load_film(film))
    if timing is None:
        raise typer.BadParameter(f"no {narration_path(film).name}")
    typer.echo(json.dumps(timing.as_json(), indent=1, ensure_ascii=False))


if __name__ == "__main__":
    app()
