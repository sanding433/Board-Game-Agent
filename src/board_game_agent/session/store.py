from __future__ import annotations

import json
import uuid
from pathlib import Path

from board_game_agent.models.schemas import GameState, RuleCard


class SessionStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, sid: str) -> Path:
        return self.root / sid

    def create(self, name: str = "") -> str:
        sid = uuid.uuid4().hex[:12]
        root = self.path(sid)
        (root / "rules").mkdir(parents=True)
        (root / "state").mkdir(parents=True)
        (root / "turns").mkdir(parents=True)
        meta = {"id": sid, "name": name or sid, "status": "active"}
        (root / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        (root / "timeline.jsonl").write_text("", encoding="utf-8")
        (root / "assumptions.md").write_text("", encoding="utf-8")
        (root / "transcript.md").write_text("", encoding="utf-8")
        self.write_state(sid, GameState())
        self.set_current(sid)
        return sid

    def list_sessions(self) -> list[str]:
        return sorted(p.name for p in self.root.iterdir() if p.is_dir() and (p / "meta.json").exists())

    def set_current(self, sid: str) -> None:
        (self.root / ".current").write_text(sid, encoding="utf-8")

    def get_current(self) -> str | None:
        p = self.root / ".current"
        if not p.exists():
            return None
        return p.read_text(encoding="utf-8").strip() or None

    def write_rules_raw(self, sid: str, text: str) -> None:
        (self.path(sid) / "rules" / "raw.md").write_text(text, encoding="utf-8")

    def read_rules_raw(self, sid: str) -> str:
        p = self.path(sid) / "rules" / "raw.md"
        if not p.exists():
            return ""
        return p.read_text(encoding="utf-8")

    def write_rule_card(self, sid: str, card: RuleCard) -> None:
        (self.path(sid) / "rules" / "card.json").write_text(
            card.model_dump_json(indent=2), encoding="utf-8"
        )

    def read_rule_card(self, sid: str) -> RuleCard | None:
        p = self.path(sid) / "rules" / "card.json"
        if not p.exists():
            return None
        return RuleCard.model_validate_json(p.read_text(encoding="utf-8"))

    def write_state(self, sid: str, state: GameState) -> None:
        (self.path(sid) / "state" / "current.json").write_text(
            state.model_dump_json(indent=2), encoding="utf-8"
        )

    def read_state(self, sid: str) -> GameState:
        p = self.path(sid) / "state" / "current.json"
        if not p.exists():
            return GameState()
        return GameState.model_validate_json(p.read_text(encoding="utf-8"))

    def write_assumptions(self, sid: str, text: str) -> None:
        (self.path(sid) / "assumptions.md").write_text(text, encoding="utf-8")

    def read_assumptions(self, sid: str) -> str:
        p = self.path(sid) / "assumptions.md"
        if not p.exists():
            return ""
        return p.read_text(encoding="utf-8")

    def append_transcript(self, sid: str, text: str) -> None:
        path = self.path(sid) / "transcript.md"
        with path.open("a", encoding="utf-8") as f:
            f.write(text.rstrip() + "\n\n")

    def read_meta(self, sid: str) -> dict:
        return json.loads((self.path(sid) / "meta.json").read_text(encoding="utf-8"))

    def write_meta(self, sid: str, meta: dict) -> None:
        (self.path(sid) / "meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )
