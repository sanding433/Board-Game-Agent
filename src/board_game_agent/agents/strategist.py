from __future__ import annotations

from board_game_agent.agents.base import system_prompt
from board_game_agent.llm.client import LLMClient
from board_game_agent.models.schemas import CandidateAction, GameState, RuleCard


class Strategist:
    def __init__(self, llm: LLMClient, language: str = "zh"):
        self.llm = llm
        self.language = language

    def propose(
        self,
        state: GameState,
        card: RuleCard,
        assumptions: list[str],
    ) -> list[CandidateAction]:
        messages = [
            {"role": "system", "content": system_prompt(self.language)},
            {
                "role": "user",
                "content": (
                    "只优化当前玩家收益，给出 1-3 个候选行动。返回 JSON：\n"
                    '{ "candidates": [ { "action", "rationale", "assumptions" } ] }\n'
                    "不要编造隐藏信息；不要上帝视角。\n"
                    f"规则：{card.model_dump_json()}\n局面：{state.model_dump_json()}\n"
                    f"假设：{assumptions}"
                ),
            },
        ]
        data = self.llm.chat_json(messages, tier="reasoning")
        return [CandidateAction.model_validate(c) for c in data.get("candidates", [])]
