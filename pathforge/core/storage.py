from __future__ import annotations
import json, os, time
from dataclasses import dataclass
from typing import Optional

SAVE_DIR = os.path.join(os.getcwd(), "saves")
META_FILE = os.path.join(SAVE_DIR, "meta.json")
RUN_FILE  = os.path.join(SAVE_DIR, "run.json")

@dataclass
class Meta:
    ascension: int = 0

class SaveManager:
    def __init__(self):
        os.makedirs(SAVE_DIR, exist_ok=True)

    def load_meta(self) -> Meta:
        if not os.path.exists(META_FILE):
            return Meta()
        try:
            with open(META_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
            return Meta(ascension=int(d.get("ascension", 0)))
        except:
            return Meta()

    def save_meta(self, meta: Meta):
        with open(META_FILE, "w", encoding="utf-8") as f:
            json.dump({"ascension": meta.ascension}, f, indent=2)

    def load_run(self) -> Optional[dict]:
        if not os.path.exists(RUN_FILE):
            return None
        try:
            with open(RUN_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return None

    def save_run(self, data: dict):
        data["saved_at"] = time.time()
        with open(RUN_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def clear_run(self):
        if os.path.exists(RUN_FILE):
            try: os.remove(RUN_FILE)
            except: pass
