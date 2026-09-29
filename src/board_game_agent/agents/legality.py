from __future__ import annotations

from board_game_agent.agents.base import system_prompt
from board_game_agent.llm.client import LLMClient
from board_game_agent.models.schemas import CandidateAction, GameState, LegalityReport, RuleCard


class LegalityChecker:
    def __init__(self, llm: LLMClient, language: str = "zh"):
        self.llm = llm
        self.language = language

    def check(
        self,
        candidates: list[CandidateAction],
        state: GameState,
        card: RuleCard,
    ) -> list[LegalityReport]:
        messages = [
            {"role": "system", "content": system_prompt(self.language)},
            {
                "role": "user",
                "content": (
                    "对照规则卡片判断候选行动是否合法。返回 JSON：\n"
                    '{ "reports": [ { "action", "legal", "reason" } ] }\n'
                    f"规则：{card.model_dump_json()}\n局面：{state.model_dump_json()}\n"
                    f"候选：{[c.model_dump() for c in candidates]}"
                ),
            },
        ]
        data = self.llm.chat_json(messages, tier="fast")
        return [LegalityReport.model_validate(r) for r in data.get("reports", [])]
