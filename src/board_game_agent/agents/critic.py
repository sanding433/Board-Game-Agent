from __future__ import annotations

from board_game_agent.agents.base import system_prompt
from board_game_agent.llm.client import LLMClient
from board_game_agent.models.schemas import (
    AdviceResult,
    CandidateAction,
    GameState,
    LegalityReport,
    RuleCard,
)


class Critic:
    def __init__(self, llm: LLMClient, language: str = "zh"):
        self.llm = llm
        self.language = language

    def finalize(
        self,
        candidates: list[CandidateAction],
        legality: list[LegalityReport],
        state: GameState,
        card: RuleCard,
    ) -> AdviceResult:
        messages = [
            {"role": "system", "content": system_prompt(self.language)},
            {
                "role": "user",
                "content": (
                    "复核候选与合法性，产出最终自然语言建议。返回 JSON：\n"
                    '{ "final_text", "candidates", "legality", "clarifications" }\n'
                    "剔除明显非法；说明玩家视角理由与风险。\n"
                    f"规则：{card.model_dump_json()}\n局面：{state.model_dump_json()}\n"
                    f"候选：{[c.model_dump() for c in candidates]}\n"
                    f"合法性：{[r.model_dump() for r in legality]}"
                ),
            },
        ]
        data = self.llm.chat_json(messages, tier="reasoning")
        if "candidates" not in data:
            data["candidates"] = [c.model_dump() for c in candidates]
        if "legality" not in data:
            data["legality"] = [r.model_dump() for r in legality]
        return AdviceResult.model_validate(data)
