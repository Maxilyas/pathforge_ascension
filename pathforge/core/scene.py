from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Optional

@dataclass
class SceneResult:
    next_scene: Optional[str] = None
    payload: Any = None

class Scene:
    name = "SCENE"
    def __init__(self, game):
        self.game = game
        self._result = SceneResult()

    def enter(self, payload=None): ...
    def exit(self): ...
    def handle_event(self, event): ...
    def update(self, dt: float): ...
    def draw(self, screen): ...

    def request(self, next_scene: str, payload=None):
        self._result = SceneResult(next_scene, payload)

    def consume_result(self) -> SceneResult:
        r = self._result
        self._result = SceneResult()
        return r
