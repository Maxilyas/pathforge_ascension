from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any, List, Set

@dataclass
class CombatStats:
    gold: int = 300
    fragments: int = 0
    paves: int = 120  # Essence de forge: limite de tuiles de chemin par run
    lives: int = 20
    core_shield: int = 0

    wave: int = 1

    # talents
    talent_pts: int = 0
    talent_nodes: Set[str] = field(default_factory=set)

    # perks
    perks: List[dict] = field(default_factory=list)
    perk_rerolls: int = 1

    # multipliers
    dmg_mul: float = 1.0
    rate_mul: float = 1.0
    range_mul: float = 1.0
    gold_per_kill: int = 0
    frag_chance: float = 0.10
    interest: float = 0.02

    weakness_mul: float = 1.8
    enemy_speed_mul: float = 1.0
    tower_cost_mul: float = 1.0
    sell_refund: float = 0.70
    overclock_dur_mul: float = 1.0

    # spells
    spell_cd_mul: float = 1.0
    spell_energy_regen_mul: float = 1.0
    spell_double_chance: float = 0.0

    # flags / mods
    flags: Dict[str, Any] = field(default_factory=dict)
    tower_bonus: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    spell_bonus: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def _ensure_talent_nodes_set(self):
        # Migration safety: older saves or buggy assignments may store a list.
        if isinstance(self.talent_nodes, list):
            self.talent_nodes = set(self.talent_nodes)
        elif self.talent_nodes is None:
            self.talent_nodes = set()

    def has_flag(self, k: str) -> bool:
        return bool(self.flags.get(k))

    def apply_perk(self, perk: dict):
        self.perks.append(perk)
        mods = perk.get("mods") or {}
        grant = perk.get("grant") or {}

        # core numbers
        self.dmg_mul *= float(mods.get("dmg_mul", 1.0))
        self.rate_mul *= float(mods.get("rate_mul", 1.0))
        self.range_mul *= float(mods.get("range_mul", 1.0))
        self.gold_per_kill += int(mods.get("gold_per_kill", 0))
        self.frag_chance += float(mods.get("frag_chance_add", 0.0))
        self.interest += float(mods.get("interest_add", 0.0))

        if "weakness_mul" in mods: self.weakness_mul = float(mods["weakness_mul"])
        self.enemy_speed_mul *= float(mods.get("enemy_speed_mul", 1.0))
        self.tower_cost_mul *= float(mods.get("tower_cost_mul", 1.0))
        if "sell_refund" in mods: self.sell_refund = float(mods["sell_refund"])
        self.overclock_dur_mul *= float(mods.get("overclock_dur_mul", 1.0))

        # spells
        self.spell_cd_mul *= float(mods.get("spell_cd_mul", 1.0))
        self.spell_energy_regen_mul *= float(mods.get("spell_energy_regen_mul", 1.0))
        if "spell_double_chance" in mods:
            self.spell_double_chance = max(self.spell_double_chance, float(mods["spell_double_chance"]))

        # flags
        for k,v in mods.items():
            if k.startswith("flag_"):
                self.flags[k] = v

        tb = mods.get("tower_bonus") or {}
        for tk, data in tb.items():
            self.tower_bonus.setdefault(tk, {}).update(data)

        sb = mods.get("spell_bonus") or {}
        for sk, data in sb.items():
            self.spell_bonus.setdefault(sk, {}).update(data)

        # rerolls
        if "perk_rerolls_add" in mods:
            self.perk_rerolls += int(mods["perk_rerolls_add"])

        # grants
        self.gold += int(grant.get("gold", 0))
        self.fragments += int(grant.get("fragments", 0))
        self.core_shield += int(grant.get("core_shield", 0))
        self.paves += int(grant.get("paves", 0))
        self.lives += int(grant.get("lives", 0))

    def end_wave_income(self, relics_in_path: int = 0):
        # economy
        self.gold += int(self.gold * self.interest)
        if self.has_flag("flag_path_gold"):
            self.gold += 12 * relics_in_path

        # forge resource: recover some paves each cleared wave
        self.paves += 8 + min(8, relics_in_path*2)

    # talents
    def can_buy_node(self, node_id: str, prereq: list[str], exclusive: list[str]) -> bool:
        self._ensure_talent_nodes_set()
        if node_id in self.talent_nodes: return False
        if self.talent_pts <= 0: return False
        if any(e in self.talent_nodes for e in exclusive): return False
        return all(p in self.talent_nodes for p in prereq)

    def buy_node(self, node_id: str, effect: dict):
        self._ensure_talent_nodes_set()
        self.talent_pts -= 1
        self.talent_nodes.add(node_id)
        mods = (effect.get("mods") or {})
        grant = (effect.get("grant") or {})
        # reuse perk-like application (limited)
        self.dmg_mul *= float(mods.get("dmg_mul", 1.0))
        self.rate_mul *= float(mods.get("rate_mul", 1.0))
        self.range_mul *= float(mods.get("range_mul", 1.0))
        self.interest += float(mods.get("interest_add", 0.0))
        if "weakness_mul" in mods: self.weakness_mul = float(mods["weakness_mul"])
        self.overclock_dur_mul *= float(mods.get("overclock_dur_mul", 1.0))
        self.spell_cd_mul *= float(mods.get("spell_cd_mul", 1.0))
        for k,v in mods.items():
            if k.startswith("flag_"):
                self.flags[k] = v
        tb = mods.get("tower_bonus") or {}
        for tk, data in tb.items():
            self.tower_bonus.setdefault(tk, {}).update(data)
        self.lives += int(grant.get("lives", 0))
        self.core_shield += int(grant.get("core_shield", 0))
        self.paves += int(grant.get("paves", 0))
