from __future__ import annotations
from dataclasses import dataclass

@dataclass
class Status:
    kind: str
    dur: float
    stacks: int = 1
    strength: float = 0.0
