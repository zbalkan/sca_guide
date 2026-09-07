from dataclasses import dataclass, field

from sca.internal.review import DecisionType
from sca.internal.sca import Check


@dataclass
class TailoringRemoval:
    decision: DecisionType
    justification: str
    check: Check


class TailoringException(TailoringRemoval):
    def __init__(self, justification: str, exception_check: Check) -> None:
        super().__init__(
            decision=DecisionType.EXCEPTION,
            justification=justification,
            check=exception_check,
        )


@dataclass
class Tailoring:
    name: str
    id: str
    description: str
    decisions: dict[int, TailoringRemoval] = field(default_factory=dict)
