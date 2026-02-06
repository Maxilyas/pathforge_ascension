
from __future__ import annotations

from typing import Dict, Any
import json, os

PROFILE_FILE = os.path.join(os.getcwd(), "saves", "balance_profile.json")

def load_profile() -> Dict[str, Any] | None:
    if not os.path.exists(PROFILE_FILE):
        return None
    try:
        with open(PROFILE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def apply_profile(towers_db: Dict[str,Any], enemies_db: Dict[str,Any], profile: Dict[str,Any]) -> None:
    """Apply lightweight multipliers to DBs at runtime.

    Profile format:
    {
      "tower": {"damage_mul":0.95,"rate_mul":1.00,"range_mul":1.00,"cost_mul":1.00},
      "enemy": {"hp_mul":1.10,"armor_add":0,"speed_mul":1.00,"regen_mul":1.00,"shield_mul":1.00}
    }
    """
    t = (profile.get("tower") or {})
    e = (profile.get("enemy") or {})

    t_dmg = float(t.get("damage_mul", 1.0))
    t_rate = float(t.get("rate_mul", 1.0))
    t_rng = float(t.get("range_mul", 1.0))
    t_cost = float(t.get("cost_mul", 1.0))

    for _, td in towers_db.items():
        try:
            td["cost"] = int(round(int(td.get("cost", 0)) * t_cost))
        except Exception:
            pass
        base = td.get("base") or {}
        if isinstance(base, dict):
            if "damage" in base:
                base["damage"] = float(base["damage"]) * t_dmg
            if "rate" in base:
                base["rate"] = float(base["rate"]) * t_rate
            if "range" in base:
                base["range"] = float(base["range"]) * t_rng

    e_hp = float(e.get("hp_mul", 1.0))
    e_spd = float(e.get("speed_mul", 1.0))
    e_reg = float(e.get("regen_mul", 1.0))
    e_arm_add = float(e.get("armor_add", 0.0))
    e_shield = float(e.get("shield_mul", 1.0))

    for _, ed in enemies_db.items():
        try:
            ed["hp"] = float(ed.get("hp", 1.0)) * e_hp
        except Exception:
            pass
        try:
            ed["spd"] = float(ed.get("spd", 1.0)) * e_spd
        except Exception:
            pass
        try:
            ed["regen"] = float(ed.get("regen", 0.0)) * e_reg
        except Exception:
            pass
        try:
            ed["armor"] = int(round(float(ed.get("armor", 0)) + e_arm_add))
        except Exception:
            pass
        try:
            ed["shield"] = int(round(float(ed.get("shield", 0)) * e_shield))
        except Exception:
            pass
