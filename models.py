from dataclasses import dataclass

@dataclass(frozen=True)
class Job:
    uid: int
    u: int
    v: int
    k: int
    length_m: float
    priority: int
    name: str
    highway: str

@dataclass
class Segment:
    u: int
    v: int
    k: int | None
    length_m: float
    is_service: bool
    is_repeat: bool
    priority: int | None
    job_uid: int | None
    step: int
    kind: str

@dataclass
class Route:
    truck_id: int
    segments: list
    meters_total: float
    meters_service: float
    meters_repeat: float
    finish_priority_h: dict
    covered_jobs: int