
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import os, json, csv, time, datetime

def _now_id() -> str:
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

@dataclass
class WaveRow:
    wave: int
    boss: bool = False
    wave_multi: int = 1
    paves_start: int = 0
    paves_end: int = 0
    gold_start: int = 0
    gold_end: int = 0
    lives_start: int = 0
    lives_end: int = 0
    towers: int = 0
    towers_placed: int = 0
    towers_upgraded: int = 0
    enemies_spawned: int = 0
    enemies_killed: int = 0
    enemies_leaked: int = 0
    dmg_total: float = 0.0
    dmg_by_type: Dict[str, float] = field(default_factory=dict)
    perk_taken_id: str = ""
    perk_taken_name: str = ""
    perk_taken_rarity: str = ""

class Telemetry:
    """Lightweight run telemetry.
    Writes:
      - saves/telemetry/run_<id>_waves.csv
      - saves/telemetry/run_<id>_events.jsonl (optional, compact)
    """
    def __init__(self, enabled: bool = True, run_id: Optional[str] = None):
        self.enabled = enabled
        self.run_id = run_id or _now_id()
        self.dir = os.path.join(os.getcwd(), "saves", "telemetry")
        os.makedirs(self.dir, exist_ok=True)
        self.wave_rows: List[WaveRow] = []
        self._cur: Optional[WaveRow] = None

        self._events_path = os.path.join(self.dir, f"run_{self.run_id}_events.jsonl")
        self._waves_path = os.path.join(self.dir, f"run_{self.run_id}_waves.csv")

        self._events_fp = None
        if self.enabled:
            self._events_fp = open(self._events_path, "a", encoding="utf-8")

    def close(self):
        if self._events_fp:
            try:
                self._events_fp.flush()
                self._events_fp.close()
            except Exception:
                pass
            self._events_fp = None
        if self.enabled:
            self.flush_waves()

    def _event(self, kind: str, data: Dict[str, Any]):
        if not self.enabled:
            return
        row = {"t": time.time(), "kind": kind, **data}
        try:
            self._events_fp.write(json.dumps(row, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def start_run(self, seed: int = 0, meta: Optional[Dict[str,Any]] = None):
        self._event("run_start", {"seed": seed, "meta": meta or {}})

    def wave_start(self, wave: int, boss: bool, wave_multi: int, stats):
        if not self.enabled:
            return
        self._cur = WaveRow(
            wave=wave,
            boss=bool(boss),
            wave_multi=int(wave_multi),
            paves_start=int(getattr(stats, "paves", 0)),
            gold_start=int(getattr(stats, "gold", 0)),
            lives_start=int(getattr(stats, "lives", 0)),
            towers=int(getattr(stats, "_telemetry_towers", 0)),
        )
        self._event("wave_start", {"wave": wave, "boss": bool(boss), "multi": int(wave_multi)})

    def wave_end(self, stats):
        if not self.enabled or not self._cur:
            return
        self._cur.paves_end = int(getattr(stats, "paves", 0))
        self._cur.gold_end = int(getattr(stats, "gold", 0))
        self._cur.lives_end = int(getattr(stats, "lives", 0))
        self.wave_rows.append(self._cur)
        self._event("wave_end", {"wave": self._cur.wave})
        self._cur = None

    def tower_placed(self, tower_key: str):
        if not self.enabled or not self._cur:
            return
        self._cur.towers_placed += 1
        self._event("tower_place", {"wave": self._cur.wave, "tower": tower_key})

    def tower_upgraded(self, tower_key: str):
        if not self.enabled or not self._cur:
            return
        self._cur.towers_upgraded += 1
        self._event("tower_upgrade", {"wave": self._cur.wave, "tower": tower_key})

    def enemy_spawned(self, enemy_key: str):
        if not self.enabled or not self._cur:
            return
        self._cur.enemies_spawned += 1
        self._event("enemy_spawn", {"wave": self._cur.wave, "enemy": enemy_key})

    def enemy_killed(self, enemy_key: str):
        if not self.enabled or not self._cur:
            return
        self._cur.enemies_killed += 1
        self._event("enemy_kill", {"wave": self._cur.wave, "enemy": enemy_key})

    def enemy_leaked(self, enemy_key: str):
        if not self.enabled or not self._cur:
            return
        self._cur.enemies_leaked += 1
        self._event("enemy_leak", {"wave": self._cur.wave, "enemy": enemy_key})

    def damage(self, src: str, dmg_type: str, amt: float, crit: bool = False):
        if not self.enabled or not self._cur:
            return
        a = float(max(0.0, amt))
        self._cur.dmg_total += a
        self._cur.dmg_by_type[dmg_type] = float(self._cur.dmg_by_type.get(dmg_type, 0.0) + a)
        # don't spam events for every hit; keep summary only

    def perk_taken(self, perk: Dict[str,Any]):
        if not self.enabled or not self._cur:
            return
        self._cur.perk_taken_id = str(perk.get("rid") or perk.get("id") or "")
        self._cur.perk_taken_name = str(perk.get("name") or "")
        self._cur.perk_taken_rarity = str(perk.get("rarity") or "")
        self._event("perk_taken", {"wave": self._cur.wave, "id": self._cur.perk_taken_id, "rarity": self._cur.perk_taken_rarity})

    def flush_waves(self):
        if not self.enabled:
            return
        # write CSV
        fieldnames = [
            "wave","boss","wave_multi",
            "paves_start","paves_end","gold_start","gold_end","lives_start","lives_end",
            "towers","towers_placed","towers_upgraded",
            "enemies_spawned","enemies_killed","enemies_leaked",
            "dmg_total","dmg_by_type_json",
            "perk_taken_id","perk_taken_name","perk_taken_rarity",
        ]
        try:
            with open(self._waves_path, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=fieldnames)
                w.writeheader()
                for r in self.wave_rows:
                    w.writerow({
                        "wave": r.wave,
                        "boss": int(r.boss),
                        "wave_multi": r.wave_multi,
                        "paves_start": r.paves_start,
                        "paves_end": r.paves_end,
                        "gold_start": r.gold_start,
                        "gold_end": r.gold_end,
                        "lives_start": r.lives_start,
                        "lives_end": r.lives_end,
                        "towers": r.towers,
                        "towers_placed": r.towers_placed,
                        "towers_upgraded": r.towers_upgraded,
                        "enemies_spawned": r.enemies_spawned,
                        "enemies_killed": r.enemies_killed,
                        "enemies_leaked": r.enemies_leaked,
                        "dmg_total": f"{r.dmg_total:.2f}",
                        "dmg_by_type_json": json.dumps(r.dmg_by_type, ensure_ascii=False),
                        "perk_taken_id": r.perk_taken_id,
                        "perk_taken_name": r.perk_taken_name,
                        "perk_taken_rarity": r.perk_taken_rarity,
                    })
        except Exception:
            pass
