from __future__ import annotations

from board_game_agent.agents.base import system_prompt
from board_game_agent.llm.client import LLMClient
from board_game_agent.models.schemas import RuleCard


class RuleIngestor:
    def __init__(self, llm: LLMClient, language: str = "zh"):
        self.llm = llm
        self.language = language

    def ingest(self, rules_text: str) -> RuleCard:
        messages = [
            {"role": "system", "content": system_prompt(self.language)},
            {
                "role": "user",
                "content": (
                    "将下列桌游规则整理为 JSON，字段必须包含：\n"
                    "game_name, phases, actions ([{name, summary}]), scoring_notes, "
                    "ambiguities, critical_slots, raw_summary。\n"
                    "critical_slots 至少包含 hand, funds, phase, active_seat（若规则适用）。\n\n"
                    f"规则文本：\n{rules_text}"
                ),
            },
        ]
        data = self.llm.chat_json(messages, tier="fast")
        return RuleCard.model_validate(data)
