
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, List, Tuple
import random
import copy

# Rarity codes used throughout UI
RARITIES = ["C", "R", "E", "L", "SS+", "SS++", "SSS", "Ω"]

# Base weights: Ω is *extremely* rare (order of millions).
BASE_WEIGHTS: Dict[str, float] = {
    "C": 1.00,
    "R": 0.35,
    "E": 0.12,
    "L": 0.03,
    "SS+": 0.006,
    "SS++": 0.0012,
    "SSS": 0.00005,
    "Ω": 0.00000008,  # ~1 in 12.5M before bias / pool size
}

# Roll ranges by rarity (additive fraction; e.g. +0.12 means +12%)
RANGE_BY_RARITY = {
    "C":   (0.06, 0.12),
    "R":   (0.12, 0.20),
    "E":   (0.20, 0.32),
    "L":   (0.32, 0.48),
    "SS+": (0.48, 0.70),
    "SS++":(0.70, 0.95),
    "SSS": (0.95, 1.25),
    "Ω":   (1.25, 1.80),
}

GPK_BY_RARITY = {  # gold per kill additive
    "C": (1, 2), "R": (2, 4), "E": (4, 7), "L": (7, 11),
    "SS+": (11, 16), "SS++": (16, 23), "SSS": (23, 32), "Ω": (40, 60),
}

PAVES_BY_RARITY = {
    "C": (2, 4), "R": (4, 7), "E": (7, 12), "L": (12, 18),
    "SS+": (18, 28), "SS++": (28, 40), "SSS": (40, 60), "Ω": (80, 120),
}

def _bias_weights(base: Dict[str, float], bias: float) -> Dict[str, float]:
    """bias: 0..0.6. Pushes probability mass upward."""
    b = max(0.0, min(0.60, float(bias)))
    w = dict(base)
    w["C"] *= (1.0 - 0.78*b)
    w["R"] *= (1.0 - 0.55*b)
    w["E"] *= (1.0 + 0.40*b)
    w["L"] *= (1.0 + 1.05*b)
    w["SS+"] *= (1.0 + 1.90*b)
    w["SS++"] *= (1.0 + 2.50*b)
    w["SSS"] *= (1.0 + 3.10*b)
    w["Ω"] *= (1.0 + 3.60*b)
    return w

def _pick_weighted(rng: random.Random, items: List[Tuple[Any, float]]) -> Any:
    total = 0.0
    for _, w in items:
        total += float(w)
    if total <= 0:
        return items[0][0]
    r = rng.random() * total
    acc = 0.0
    for it, w in items:
        acc += float(w)
        if acc >= r:
            return it
    return items[-1][0]

def _fmt_pct(x: float) -> str:
    return f"{int(round(x*100))}%"

def _resolve_roll(defn: Dict[str, Any], rng: random.Random) -> Dict[str, Any]:
    """Turn a template into a concrete perk with rolled values."""
    p = copy.deepcopy(defn)
    roll = p.get("roll") or {}
    if not roll:
        p["rid"] = p.get("id")
        return p

    kind = str(roll.get("kind", ""))
    rarity = str(p.get("rarity", "C"))
    p["rid"] = f"{p.get('id','P')}-{rng.randint(100000, 999999)}"

    mods = p.get("mods") or {}
    grant = p.get("grant") or {}
    p["mods"] = mods
    p["grant"] = grant

    if kind == "dmg_mul":
        lo, hi = RANGE_BY_RARITY.get(rarity, (0.06, 0.12))
        val = rng.uniform(lo, hi)
        # If it's a dmg-type specialization, map to that type.
        dtm = mods.get("dmg_type_mul") if isinstance(mods, dict) else None
        if isinstance(dtm, dict) and len(dtm) >= 1:
            new_map = {}
            for dt in dtm.keys():
                new_map[str(dt)] = float(1.0 + val)
            mods["dmg_type_mul"] = new_map
            dt0 = next(iter(new_map.keys()))
            p["name"] = f"{dt0} +{_fmt_pct(val)}"
            p["rolled"] = {"dmg_type_mul_add": val, "types": list(new_map.keys())}
        else:
            mods["dmg_mul"] = float(1.0 + val)
            p["name"] = f"{p.get('name','Puissance')} +{_fmt_pct(val)}"
            p["rolled"] = {"dmg_mul_add": val}

    elif kind == "rate_mul":
        lo, hi = RANGE_BY_RARITY.get(rarity, (0.06, 0.12))
        val = rng.uniform(lo, hi)
        mods["rate_mul"] = float(1.0 + val)
        p["name"] = f"{p.get('name','Cadence')} +{_fmt_pct(val)}"
        p["rolled"] = {"rate_mul_add": val}

    elif kind == "range_mul":
        lo, hi = RANGE_BY_RARITY.get(rarity, (0.06, 0.12))
        val = rng.uniform(lo*0.7, hi*0.7)
        mods["range_mul"] = float(1.0 + val)
        p["name"] = f"{p.get('name','Portée')} +{_fmt_pct(val)}"
        p["rolled"] = {"range_mul_add": val}

    elif kind == "gold_per_kill":
        lo, hi = GPK_BY_RARITY.get(rarity, (1, 2))
        val = rng.randint(int(lo), int(hi))
        mods["gold_per_kill"] = int(val)
        p["name"] = f"{p.get('name','Prime')} +{val} or/kill"
        p["rolled"] = {"gold_per_kill_add": val}

    elif kind == "paves":
        lo, hi = PAVES_BY_RARITY.get(rarity, (2, 4))
        val = rng.randint(int(lo), int(hi))
        grant["paves"] = int(val)
        p["name"] = f"{p.get('name','Essence de forge')} +{val} pavés"
        p["rolled"] = {"paves_add": val}

    elif kind == "paves_cap":
        lo, hi = PAVES_BY_RARITY.get(rarity, (2, 4))
        val = rng.randint(int(lo), int(hi))
        grant["paves_cap"] = int(val)
        p["name"] = f"{p.get('name','Cap de forge')} +{val} cap"
        p["rolled"] = {"paves_cap_add": val}

    elif kind == "talent_pt":
        grant["talent_pts"] = 1
        p["name"] = f"{p.get('name','Éveil')} +1 point de talent"
        p["rolled"] = {"talent_pts_add": 1}

    elif kind == "tower_bonus_damage":
        tower = str(roll.get("tower", ""))
        lo, hi = RANGE_BY_RARITY.get(rarity, (0.06, 0.12))
        val = rng.uniform(lo, hi)
        mods.setdefault("tower_bonus", {}).setdefault(tower, {})["damage_mul"] = float(1.0 + val)
        p["name"] = f"{tower} • Dégâts +{_fmt_pct(val)}"
        p["rolled"] = {"tower": tower, "damage_mul_add": val}

    elif kind == "tower_bonus_rate":
        tower = str(roll.get("tower", ""))
        lo, hi = RANGE_BY_RARITY.get(rarity, (0.06, 0.12))
        val = rng.uniform(lo, hi)
        mods.setdefault("tower_bonus", {}).setdefault(tower, {})["rate_mul"] = float(1.0 + val)
        p["name"] = f"{tower} • Cadence +{_fmt_pct(val)}"
        p["rolled"] = {"tower": tower, "rate_mul_add": val}

    elif kind == "global_on_hit":
        status = str(roll.get("status", "SHRED"))
        dur = float(roll.get("dur", 2.0))
        stacks = int(roll.get("stacks", 1))
        base = {"C":0.10,"R":0.14,"E":0.18,"L":0.24,"SS+":0.30,"SS++":0.36,"SSS":0.42,"Ω":0.55}.get(rarity, 0.10)
        chance = min(0.80, base + rng.random()*0.06)
        mods.setdefault("global_on_hit", {})[status] = {"dur":dur, "stacks":stacks, "chance":chance}
        p["name"] = f"On-hit • {status} ({int(chance*100)}%)"
        p["rolled"] = {"status": status, "chance": chance}

    return p

@dataclass
class PerkPool:
    perks: List[Dict[str, Any]]

    def __post_init__(self):
        self.by_rarity: Dict[str, List[Dict[str, Any]]] = {r: [] for r in RARITIES}
        for p in self.perks:
            r = str(p.get("rarity", "C"))
            if r not in self.by_rarity:
                r = "C"
            self.by_rarity[r].append(p)
        if not self.by_rarity["C"]:
            self.by_rarity["C"] = [{"id":"FALLBACK","name":"Fallback","rarity":"C","mods":{}}]

    def roll(self, rng: random.Random, n: int = 3, rarity_bias: float = 0.0) -> List[Dict[str, Any]]:
        w = _bias_weights(BASE_WEIGHTS, rarity_bias)
        picks: List[Dict[str, Any]] = []
        used_ids = set()
        tries = 0
        while len(picks) < n and tries < 5000:
            tries += 1
            rarity = _pick_weighted(rng, [(r, w.get(r, 1.0)) for r in RARITIES])
            bucket = self.by_rarity.get(rarity) or self.by_rarity["C"]
            base = bucket[rng.randrange(0, len(bucket))]
            bid = str(base.get("id", ""))
            if not bid or bid in used_ids:
                continue
            used_ids.add(bid)
            picks.append(_resolve_roll(base, rng))
        return picks

def extend_with_procedural(perks_db: List[Dict[str, Any]], towers_db: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Add *thousands* of procedural perk templates."""
    out = list(perks_db)

    tower_keys = sorted(list(towers_db.keys()))
    dmg_types = ["KINETIC","PIERCE","ENERGY","FIRE","COLD","EXPLOSIVE","BIO"]

    dmg_flavors = ["Forge","Rage","Discipline","Focus","Fury","Zenith","Momentum","Overdrive","Precision","Anvil","Ascension","Vanguard"]
    eco_flavors = ["Bourse","Tribut","Pillage","Dîme","Contrat","Prime","Courtage","Bénéfice","Usure","Orfèvre","Banquier","Pari"]
    util_flavors = ["Cartographie","Visée","Lunette","Optique","Recon","Radar","Tactique","Coordination","Commandement","Balistique"]
    onhit_flavors = ["Étincelle","Fissure","Saignée","Corrosion","Gel","Surtension","Cicatrice","Marquage","Fracture","Venin"]

    # --- generic multipliers (many variants) ---
    for r in RARITIES:
        for i, nm in enumerate(dmg_flavors):
            out.append({"id":f"GEN_DMG_{r}_{i}", "name":f"{nm} (Dégâts)", "rarity":r, "tags":["POWER"], "roll":{"kind":"dmg_mul"}})
            out.append({"id":f"GEN_RATE_{r}_{i}", "name":f"{nm} (Cadence)", "rarity":r, "tags":["POWER"], "roll":{"kind":"rate_mul"}})
        for i, nm in enumerate(util_flavors):
            out.append({"id":f"GEN_RANGE_{r}_{i}", "name":f"{nm} (Portée)", "rarity":r, "tags":["UTILITY"], "roll":{"kind":"range_mul"}})
        for i, nm in enumerate(eco_flavors):
            out.append({"id":f"GEN_GPK_{r}_{i}", "name":f"{nm} (Prime)", "rarity":r, "tags":["ECONOMY"], "roll":{"kind":"gold_per_kill"}})
            out.append({"id":f"GEN_PAV_{r}_{i}", "name":f"{nm} (Pavés)", "rarity":r, "tags":["PATH","ECONOMY"], "roll":{"kind":"paves"}})
            out.append({"id":f"GEN_CAP_{r}_{i}", "name":f"{nm} (Cap)", "rarity":r, "tags":["PATH","ECONOMY"], "roll":{"kind":"paves_cap"}})

    # --- damage-type specialization ---
    for dt in dmg_types:
        for r in RARITIES:
            for i, nm in enumerate(dmg_flavors):
                out.append({
                    "id": f"DT_{dt}_{r}_{i}",
                    "name": f"{nm} • {dt}",
                    "rarity": r,
                    "tags": ["TYPE", dt, "POWER"],
                    "mods": {"dmg_type_mul": {dt: 1.0}},
                    "roll": {"kind": "dmg_mul"},
                })

    # --- tower-specific bonuses ---
    for tk in tower_keys:
        for r in RARITIES:
            for i, nm in enumerate(dmg_flavors):
                out.append({"id":f"T_{tk}_DMG_{r}_{i}", "name":f"{nm} • {tk} Dégâts", "rarity":r, "tags":["TOWER",tk,"POWER"], "roll":{"kind":"tower_bonus_damage","tower":tk}})
                out.append({"id":f"T_{tk}_RATE_{r}_{i}", "name":f"{nm} • {tk} Cadence", "rarity":r, "tags":["TOWER",tk,"POWER"], "roll":{"kind":"tower_bonus_rate","tower":tk}})

    # --- global on-hit statuses ---
    status_templates = [
        ("SHRED", 2.0, 1, ["ANTI_ARMOR"]),
        ("POISON", 2.4, 1, ["DOT"]),
        ("VULN", 1.6, 1, ["BURST"]),
        ("SLOW", 1.0, 1, ["CONTROL"]),
        ("SHOCK", 1.2, 1, ["ENERGY"]),
    ]
    for status, dur, stacks, tags in status_templates:
        for r in RARITIES:
            for i, nm in enumerate(onhit_flavors):
                out.append({
                    "id": f"GOH_{status}_{r}_{i}",
                    "name": f"{nm} • {status}",
                    "rarity": r,
                    "tags": ["ON_HIT"] + tags,
                    "roll": {"kind":"global_on_hit","status":status,"dur":dur,"stacks":stacks},
                })

    # --- ultra rare run-changers ---
    out.append({
        "id":"OMEGA_TALENT_PT",
        "name":"Éveil",
        "rarity":"Ω",
        "tags":["UNIQUE","TALENT"],
        "roll":{"kind":"talent_pt"},
    })

    # other Ω collectibles (fun)
    omega_names = ["Clé Primordiale","Cœur de Forge","Sceau de l'Infini","Fragment Absolu"]
    for i, nm in enumerate(omega_names):
        out.append({
            "id": f"OMEGA_RELIC_{i}",
            "name": nm,
            "rarity": "Ω",
            "tags": ["UNIQUE","OMEGA"],
            "mods": {"perk_rerolls_add": 2} if i==2 else {"gold_per_kill": 25} if i==1 else {"dmg_mul": 1.25, "rate_mul": 1.12} if i==0 else {"range_mul": 1.18, "tower_cost_mul": 0.90},
        })

    # reroll economy variants
    out.append({"id":"SSS_REROLL_1", "name":"Forge du Destin • +1 reroll", "rarity":"SSS", "tags":["UNIQUE","PERK"], "mods":{"perk_rerolls_add":1}})
    out.append({"id":"L_REROLL_1", "name":"Reroll • +1", "rarity":"L", "tags":["PERK"], "mods":{"perk_rerolls_add":1}})

    return out
