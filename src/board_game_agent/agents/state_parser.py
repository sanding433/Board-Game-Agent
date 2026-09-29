from __future__ import annotations

from dataclasses import dataclass, field

from board_game_agent.agents.base import system_prompt
from board_game_agent.llm.client import LLMClient
from board_game_agent.models.schemas import Clarification, Event, GameState, RuleCard

SLOT_QUESTIONS = {
    "hand": "你的手牌是什么？",
    "funds": "你当前资金多少？",
    "phase": "当前是什么阶段？",
    "active_seat": "现在轮到谁行动？",
}


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
                    "parsed 可含 phase, active_seat, me{}, public{}, out_of_view。\n"
                    "只记录当前玩家可知信息；上帝视角放入 out_of_view。\n"
                    f"规则卡片：{card.model_dump_json()}\n"
                    f"当前局面：{state.model_dump_json()}\n"
                    f"用户输入：{text}"
                ),
            },
        ]
        data = self.llm.chat_json(messages, tier="fast")
        events = [Event.model_validate(e) for e in data.get("events", [])]
        clarifications = [Clarification.model_validate(c) for c in data.get("clarifications", [])]
        assumptions = [str(a) for a in data.get("assumptions", [])]
        return ParseResult(events=events, clarifications=clarifications, assumptions=assumptions)
