from __future__ import annotations
from typing import Dict, Any, List, Tuple

from ..settings import (
    T_PATH, T_PATH_FAST, T_PATH_MUD, T_PATH_CONDUCT, T_PATH_CRYO, T_PATH_MAGMA, T_PATH_RUNE
)

# NOTE: Data-only module (no pygame import) so it can be used by the balance bot / headless sim.
TALENTS = {
    # --- FORGE (path / terrain) ---
    "F1": {"name":"Essence Amplifiée", "desc":"+30 Pavés immédiatement, et +30 de Cap de Pavés.", "pos":(-2,0),
           "prereq":[], "exclusive":[], "col":(180,140,80),
           "effect":{"grant":{"paves":30, "paves_cap":30}}},
    "F2": {"name":"Routes de Forge", "desc":"Débloque Route & Boue (tuiles).", "pos":(-2,1),
           "prereq":["F1"], "exclusive":[], "col":(180,140,80),
           "effect":{"unlock_paths":[T_PATH_FAST, T_PATH_MUD]}},
    "F3": {"name":"Conductivité", "desc":"Débloque Chemin Conducteur.", "pos":(-2,2),
           "prereq":["F2"], "exclusive":[], "col":(180,140,80),
           "effect":{"unlock_paths":[T_PATH_CONDUCT]}},
    "F4A": {"name":"Runes Vivantes", "desc":"Débloque Rune (rare) + aura de runes. Rune applique VULN plus souvent.", "pos":(-2,3),
            "prereq":["F3"], "exclusive":["F4B"], "col":(180,140,80),
            "effect":{"unlock_paths":[T_PATH_RUNE], "mods":{"rune_aura_radius":3, "rune_aura_dmg_mul":1.08, "rune_aura_range_mul":1.06, "rune_vuln_chance":0.30}}},
    "F4B": {"name":"Cryo-Alchimie", "desc":"Débloque Chemin Cryo + ralentissement prolongé.", "pos":(-1,3),
            "prereq":["F3"], "exclusive":["F4A"], "col":(140,190,255),
            "effect":{"unlock_paths":[T_PATH_CRYO], "mods":{"cryo_tile_slow_extend":0.16}}},
    "F5": {"name":"Fonderie Magma", "desc":"Débloque Chemin Magma + brûlure plus fiable.", "pos":(-2,4),
           "prereq":["F3"], "exclusive":[], "col":(230,120,90),
           "effect":{"unlock_paths":[T_PATH_MAGMA], "mods":{"magma_burn_chance":0.55}}},
    "F6": {"name":"Protocole de Reforge", "desc":"Effacer un chemin rend ses pavés.", "pos":(-2,5),
           "prereq":["F5"], "exclusive":[], "col":(180,140,80),
           "effect":{"mods":{"flag_path_reforge_free":True}}},

    # --- ARSENAL (unlock towers / combat roles) ---
    "A1": {"name":"Artillerie", "desc":"Débloque Mortier (zone).", "pos":(0,0),
           "prereq":[], "exclusive":[], "col":(200,200,200),
           "effect":{"unlock_towers":["MORTAR"]}},
    "A2": {"name":"Précision", "desc":"Débloque Sniper (mono-cible).", "pos":(0,1),
           "prereq":["A1"], "exclusive":[], "col":(200,200,200),
           "effect":{"unlock_towers":["SNIPER"]}},
    "A3": {"name":"Relais", "desc":"Débloque Beacon (support).", "pos":(0,2),
           "prereq":["A1"], "exclusive":[], "col":(255,220,120),
           "effect":{"unlock_towers":["BEACON"]}},
    "A4A":{"name":"Munitions Perforantes", "desc":"Sniper +20% dégâts.", "pos":(-1,3),
           "prereq":["A2"], "exclusive":["A4B"], "col":(200,200,200),
           "effect":{"mods":{"tower_bonus":{"SNIPER":{"damage_mul":1.20}}}}},
    "A4B":{"name":"Doctrine Splash", "desc":"Projectiles: mini AOE (global).", "pos":(1,3),
           "prereq":["A2"], "exclusive":["A4A"], "col":(200,200,200),
           "effect":{"mods":{"flag_all_projectiles_splash":True}}},
    "A5": {"name":"Déchiquetage", "desc":"Touches: chance d'appliquer SHRED.", "pos":(0,4),
           "prereq":["A3"], "exclusive":[], "col":(200,200,200),
           "effect":{"mods":{"global_on_hit":{"SHRED":{"dur":2.0,"stacks":1,"chance":0.18}}}}},
    "A6": {"name":"Prime de Boss", "desc":"Boss: récompenses x2.", "pos":(0,5),
           "prereq":["A5"], "exclusive":[], "col":(255,220,120),
           "effect":{"mods":{"flag_boss_bounty":True}}},

    # --- ARCANA (elemental + hero) ---
    "C1": {"name":"Électromancie", "desc":"Débloque Tesla (chain).", "pos":(3,0),
           "prereq":[], "exclusive":[], "col":(120,170,255),
           "effect":{"unlock_towers":["TESLA"]}},
    "C2": {"name":"Cryomancie", "desc":"Débloque Cryo (slow).", "pos":(3,1),
           "prereq":["C1"], "exclusive":[], "col":(120,170,255),
           "effect":{"unlock_towers":["CRYO"], "mods":{"tower_bonus":{"CRYO":{"slow_strength_add":0.04}}}}},
    "C3": {"name":"Pyromancie", "desc":"Débloque Flame (DoT).", "pos":(3,2),
           "prereq":["C1"], "exclusive":[], "col":(255,150,110),
           "effect":{"unlock_towers":["FLAME"]}},
    "C4A":{"name":"Maîtrise des Arcs", "desc":"Tesla: +2 chains, shock plus long.", "pos":(2,3),
           "prereq":["C1"], "exclusive":["C4B"], "col":(120,170,255),
           "effect":{"mods":{"tower_bonus":{"TESLA":{"chains_add":2,"shock_dur_add":0.5}}, "flag_conduct_mastery":True}}},
    "C4B":{"name":"Maîtrise Thermique", "desc":"Flame: +2 stacks brûlure + chance BURN (global).", "pos":(4,3),
           "prereq":["C3"], "exclusive":["C4A"], "col":(255,150,110),
           "effect":{"mods":{"tower_bonus":{"FLAME":{"burn_stacks_add":2}}, "global_on_hit":{"BURN":{"dur":1.4,"stacks":1,"chance":0.10}}}}},
    "C5": {"name":"Onde de Choc", "desc":"Q : rayon +25% et applique VULN.", "pos":(3,4),
           "prereq":["C2"], "exclusive":[], "col":(200,255,255),
           "effect":{"mods":{"hero_shock_radius_mul":1.25, "hero_shock_apply_vuln":True}}},
    "C6": {"name":"Surcadence", "desc":"Overclock durée +20%.", "pos":(3,5),
           "prereq":["C5"], "exclusive":[], "col":(200,255,255),
           "effect":{"mods":{"overclock_dur_mul":1.20}}},
}

def edges() -> List[Tuple[str,str]]:
    out: List[Tuple[str,str]] = []
    for nid, t in TALENTS.items():
        for p in (t.get("prereq") or []):
            out.append((str(p), str(nid)))
    return out

EDGES = edges()
START_NODES = [nid for nid, t in TALENTS.items() if not (t.get("prereq") or [])]
ALL_NODES = list(TALENTS.keys())
