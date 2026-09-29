from __future__ import annotations

from dataclasses import dataclass, field

from typing import Any

from board_game_agent.agents.base import system_prompt
from board_game_agent.llm.client import LLMClient
from board_game_agent.models.schemas import Clarification, Event, EventType, GameState, RuleCard

SLOT_QUESTIONS = {
    "hand": "你的手牌是什么？",
    "funds": "你当前资金多少？",
    "phase": "当前是什么阶段？",
    "active_seat": "现在轮到谁行动？",
}

ALLOWED_EVENT_TYPES: set[str] = {
    "setup",
    "public_action",
    "private_info",
    "phase_change",
    "resolve",
    "correction",
}

EVENT_TYPE_ALIASES: dict[str, EventType] = {
    "phase_declared": "phase_change",
    "phase": "phase_change",
    "era_change": "phase_change",
    "state_update": "private_info",
    "update": "private_info",
    "info": "private_info",
    "hand_update": "private_info",
    "funds_update": "private_info",
    "opponent_action": "public_action",
    "action": "public_action",
    "turn_change": "phase_change",
}


def coerce_event_dict(raw: dict[str, Any]) -> dict[str, Any]:
    data = dict(raw)
    t = str(data.get("type", "private_info"))
    if t not in ALLOWED_EVENT_TYPES:
        data["type"] = EVENT_TYPE_ALIASES.get(t, "private_info")
    if "raw_text" not in data or not data["raw_text"]:
        data["raw_text"] = str(data.get("text") or data.get("content") or "")
    if "parsed" not in data or not isinstance(data.get("parsed"), dict):
        data["parsed"] = data["parsed"] if isinstance(data.get("parsed"), dict) else {}
    vis = data.get("visibility", "public")
    if vis not in ("private", "public"):
        data["visibility"] = "private" if "private" in str(vis).lower() else "public"
    data["conflict"] = bool(data.get("conflict", False))
    return data


def missing_critical(state: GameState, card: RuleCard) -> list[str]:
    missing: list[str] = []
    for slot in card.critical_slots:
        if slot == "phase" and not state.phase:
            missing.append(slot)
        elif slot == "active_seat" and not state.active_seat:
            missing.append(slot)
        elif slot == "funds" and "funds" not in state.me:
            missing.append(slot)
        elif slot == "hand" and "hand" not in state.me:
            missing.append(slot)
        elif slot not in ("phase", "active_seat", "funds", "hand"):
            if slot not in state.me and slot not in state.public:
                missing.append(slot)
    return missing


@dataclass
class ParseResult:
    events: list[Event] = field(default_factory=list)
    clarifications: list[Clarification] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)


class StateParser:
    def __init__(self, llm: LLMClient, language: str = "zh"):
        self.llm = llm
        self.language = language

    def parse(self, text: str, card: RuleCard, state: GameState) -> ParseResult:
        messages = [
            {"role": "system", "content": system_prompt(self.language)},
            {
                "role": "user",
                "content": (
                    "把玩家自然语言解析为 JSON：\n"
                    '{ "events": [ { "type", "raw_text", "parsed", "visibility", "conflict" } ], '
                    '"clarifications": [ { "slot", "question" } ], "assumptions": [string] }\n'
                    "type 只能是: setup | public_action | private_info | phase_change | resolve | correction\n"
                    "parsed 可含 phase, active_seat, me{}, public{}, out_of_view。\n"
                    "只记录当前玩家可知信息；上帝视角放入 out_of_view。\n"
                    f"规则卡片：{card.model_dump_json()}\n"
                    f"当前局面：{state.model_dump_json()}\n"
                    f"用户输入：{text}"
                ),
            },
        ]
        data = self.llm.chat_json(messages, tier="fast")
        events = [
            Event.model_validate(coerce_event_dict(e))
            for e in data.get("events", [])
            if isinstance(e, dict)
        ]
        clarifications: list[Clarification] = []
        for c in data.get("clarifications", []):
            if isinstance(c, dict) and c.get("slot"):
                clarifications.append(
                    Clarification(
                        slot=str(c["slot"]),
                        question=str(c.get("question") or SLOT_QUESTIONS.get(str(c["slot"]), f"请补充：{c['slot']}")),
                    )
                )
        assumptions = [str(a) for a in data.get("assumptions", [])]
        return ParseResult(events=events, clarifications=clarifications, assumptions=assumptions)
