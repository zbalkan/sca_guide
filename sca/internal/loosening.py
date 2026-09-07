from dataclasses import dataclass, field

from sca.internal.review import DecisionType
from sca.internal.sca import Check


@dataclass
class TailoringRemoval:
    decision: DecisionType
    justification: str
    check: Check


@dataclass
class Tailoring:
    name: str
    id: str
    description: str
    decisions: dict[int, TailoringRemoval] = field(default_factory=dict)
