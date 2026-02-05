from __future__ import annotations

class GameClock:
    def __init__(self):
        self.time_scale = 1.0

    def scaled_dt(self, dt: float) -> float:
        return dt * self.time_scale

    def cycle_speed(self) -> int:
        # x1 / x2 / x3
        if self.time_scale < 1.5:
            self.time_scale = 2.0
        elif self.time_scale < 2.5:
            self.time_scale = 3.0
        else:
            self.time_scale = 1.0
        return int(self.time_scale)
