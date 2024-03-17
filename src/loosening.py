

from dataclasses import dataclass

from sca import Check


@dataclass
class Decision:
    justification: str
    suppressed_check: Check


@dataclass
class Loosening:
    title: str
    decisions: dict[int, Decision]
