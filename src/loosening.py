

from dataclasses import dataclass

from sca import Check


@dataclass
class Decision:
    justification: str
    suppressed_check: Check


@dataclass
class Loosening:
    name: str
    id: str
    description: str
    decisions: dict[int, Decision]

    def get_ids(self) -> list[int]:
        if self.decisions:
            return [k for k, _ in self.decisions.items()]
        else:
            return []
