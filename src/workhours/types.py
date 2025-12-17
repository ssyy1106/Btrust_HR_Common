from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class Shift:
    date: str
    begin: str
    end: str
    lunchMinute: int = 30

@dataclass(frozen=True, slots=True)
class Punch:
    date: str
    time: str

@dataclass(frozen=True, slots=True)
class PunchProblem:
    date: str
    totalHours: float
