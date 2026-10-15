"""Pydantic models for the behavioural YAML files (population config, day types).

Every behavioural number sits in a block that carries `source:` (citation) or `assumption:`
(reasoning and plausible range); the models refuse blocks without one. Times of day are written
as "HH:MM" (may exceed 24:00 for after-midnight activity) and durations in minutes.

    python -m sim.schemas sim/daytypes/weekday.yaml      # validate one file
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import typer
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from sim.common import load_yaml


def hhmm_to_s(value: str | int | float) -> float:
    """'07:30' -> 27000.0; numbers are taken as seconds."""
    if isinstance(value, int | float):
        return float(value)
    hours, minutes = value.strip().split(":")
    return int(hours) * 3600.0 + int(minutes) * 60.0


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Sourced(Strict):
    """A behavioural block: must say where its numbers come from."""

    source: str | None = None
    assumption: str | None = None

    @model_validator(mode="after")
    def _has_provenance(self) -> Sourced:
        if not (self.source or self.assumption):
            raise ValueError(f"{type(self).__name__}: needs `source:` or `assumption:`")
        return self


class Component(Strict):
    w: float = Field(gt=0)
    mean: str
    sd_min: float = Field(ge=0)

    @property
    def mean_s(self) -> float:
        return hhmm_to_s(self.mean)


class TimeDist(Sourced):
    """Time-of-day distribution: a normal or a mixture of normals, truncated to [lo, hi]."""

    dist: Literal["normal", "mixture", "uniform"] = "normal"
    mean: str | None = None
    sd_min: float | None = None
    components: list[Component] | None = None
    lo: str
    hi: str

    @model_validator(mode="after")
    def _shape(self) -> TimeDist:
        if self.dist == "normal" and (self.mean is None or self.sd_min is None):
            raise ValueError("normal needs mean and sd_min")
        if self.dist == "mixture" and not self.components:
            raise ValueError("mixture needs components")
        if hhmm_to_s(self.lo) >= hhmm_to_s(self.hi):
            raise ValueError("lo must be before hi")
        return self

    def as_components(self) -> list[tuple[float, float, float]]:
        """[(weight, mean_s, sd_s)]; uniform -> one component with sd = -1 as a marker."""
        if self.dist == "normal":
            assert self.mean is not None and self.sd_min is not None
            return [(1.0, hhmm_to_s(self.mean), self.sd_min * 60.0)]
        if self.dist == "uniform":
            return [(1.0, 0.0, -1.0)]
        assert self.components is not None
        total = sum(c.w for c in self.components)
        return [(c.w / total, c.mean_s, c.sd_min * 60.0) for c in self.components]

    @property
    def lo_s(self) -> float:
        return hhmm_to_s(self.lo)

    @property
    def hi_s(self) -> float:
        return hhmm_to_s(self.hi)


class DurationDist(Sourced):
    """Activity duration in minutes, normal truncated to [lo_min, hi_min]."""

    mean_min: float = Field(gt=0)
    sd_min: float = Field(ge=0)
    lo_min: float = Field(ge=0)
    hi_min: float = Field(gt=0)


class Probability(Sourced):
    value: float = Field(ge=0, le=1)


class Rate(Sourced):
    """Tours per person per day (Poisson-like: integer part certain, fraction a probability)."""

    value: float = Field(ge=0)


class SplitShift(Sourced):
    """Share of workers who go home between two shifts (retail split shift)."""

    probability: float = Field(ge=0, le=1)
    break_start: TimeDist
    break_min: DurationDist


class MainTour(Strict):
    """The mandatory tour of a segment (work, school, university)."""

    participation: Probability
    start: TimeDist
    duration: DurationDist
    split_shift: SplitShift | None = None
    stop_on_return: Probability | None = None


class SecondaryTour(Strict):
    rate: Rate
    start: TimeDist
    duration: DurationDist


class Prayer(Sourced):
    """Mosque trips keyed to the computed adhan time of one prayer."""

    share_adult_males: float = Field(ge=0, le=1)
    share_adult_females: float = Field(ge=0, le=1)
    depart_offset_min: float
    duration_min: float = Field(gt=0)
    distance: Literal["local", "district"] = "local"


class AirportFlows(Sourced):
    trips_per_day: float = Field(ge=0)
    hourly_profile: list[float] = Field(min_length=24, max_length=24)
    to_makkah_share: float = Field(0.0, ge=0, le=1)


class SpecialFlags(Strict):
    ramadan: bool = False
    friday: bool = False
    umrah_season: bool = False
    school_day: bool = True


class DayType(Strict):
    """A Jeddah time-of-day profile (sim/daytypes/<id>.yaml)."""

    id: str
    kind: Literal["daytype"]
    title: str
    date: str = Field(description="simulated date (YYYY-MM-DD), drives prayer times")
    special: SpecialFlags = SpecialFlags()
    main_tours: dict[str, MainTour]
    secondary_tours: dict[str, dict[str, SecondaryTour]]
    prayers: dict[str, Prayer]
    airport: AirportFlows
    notes: str | None = None

    @field_validator("main_tours")
    @classmethod
    def _known_segments(cls, v: dict[str, MainTour]) -> dict[str, MainTour]:
        known = set(MAIN_SEGMENTS)
        unknown = set(v) - known
        if unknown:
            raise ValueError(f"unknown main-tour segments {sorted(unknown)}; known {sorted(known)}")
        return v

    @field_validator("secondary_tours")
    @classmethod
    def _known_groups(
        cls, v: dict[str, dict[str, SecondaryTour]]
    ) -> dict[str, dict[str, SecondaryTour]]:
        unknown = set(v) - set(STATUS_GROUPS)
        if unknown:
            raise ValueError(f"unknown status groups {sorted(unknown)}; known {STATUS_GROUPS}")
        for tours in v.values():
            bad = set(tours) - set(SECONDARY_PURPOSES)
            if bad:
                raise ValueError(f"unknown secondary purposes {sorted(bad)}")
        return v

    @field_validator("prayers")
    @classmethod
    def _known_prayers(cls, v: dict[str, Prayer]) -> dict[str, Prayer]:
        bad = set(v) - set(PRAYERS)
        if bad:
            raise ValueError(f"unknown prayers {sorted(bad)}; known {PRAYERS}")
        return v


# Segment vocabulary shared by the population, day types and policies.
WORK_SECTORS = (
    "government",
    "private_office",
    "retail_hospitality",
    "health",
    "education",
    "industrial_port",
    "logistics_ridehail",
)
MAIN_SEGMENTS = (*WORK_SECTORS, "school", "university")
STATUS_GROUPS = ("worker", "student", "homemaker", "other")
SECONDARY_PURPOSES = ("shopping", "leisure", "personal")
PRAYERS = ("fajr", "dhuhr", "asr", "maghrib", "isha", "jumuah")


def validate_file(path: Path) -> BaseModel:
    data: dict[str, Any] = load_yaml(path)
    kind = data.get("kind")
    if kind == "daytype":
        return DayType.model_validate(data)
    raise ValueError(f"{path}: unknown kind {kind!r}")


def load_daytype(name_or_path: str | Path) -> DayType:
    path = Path(name_or_path)
    if not path.suffix:
        path = Path(__file__).resolve().parent / "daytypes" / f"{name_or_path}.yaml"
    return DayType.model_validate(load_yaml(path))


app = typer.Typer(add_completion=False, help=__doc__)


@app.command()
def main(files: list[Path]) -> None:
    for f in files:
        validate_file(f)
        typer.echo(f"ok {f}")


if __name__ == "__main__":
    app()
