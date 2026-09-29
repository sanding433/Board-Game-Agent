from __future__ import annotations

from typing import Any

from board_game_agent.agents.base import system_prompt
from board_game_agent.llm.client import LLMClient
from board_game_agent.models.schemas import (
    AdviceResult,
    CandidateAction,
    Clarification,
    GameState,
    LegalityReport,
    RuleCard,
)


def normalize_advice_payload(
    data: dict[str, Any],
    candidates: list[CandidateAction],
    legality: list[LegalityReport],
) -> dict[str, Any]:
    out = dict(data)
    if not isinstance(out.get("final_text"), str) or not out.get("final_text"):
        out["final_text"] = str(out.get("advice") or out.get("text") or "暂无可用建议。")
    if "candidates" not in out:
        out["candidates"] = [c.model_dump() for c in candidates]
    if "legality" not in out:
        out["legality"] = [r.model_dump() for r in legality]
    clar = out.get("clarifications", [])
    if isinstance(clar, list):
        norm: list[dict[str, str]] = []
        for i, item in enumerate(clar):
            if isinstance(item, Clarification):
                norm.append(item.model_dump())
            elif isinstance(item, dict) and item.get("slot"):
                norm.append(
                    {
                        "slot": str(item["slot"]),
                        "question": str(item.get("question") or item["slot"]),
                    }
                )
            elif isinstance(item, str) and item.strip():
                norm.append({"slot": f"note_{i}", "question": item.strip()})
        out["clarifications"] = norm
    else:
        out["clarifications"] = []
    return out


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
                    "{\n"
                    '  "final_text": string,\n'
                    '  "candidates": [ { "action", "rationale", "assumptions" } ],\n'
                    '  "legality": [ { "action", "legal", "reason" } ],\n'
                    '  "clarifications": [ { "slot", "question" } ]\n'
                    "}\n"
                    "clarifications 必须是对象数组，不要用纯字符串。\n"
                    "剔除明显非法；说明玩家视角理由与风险。\n"
                    f"规则：{card.model_dump_json()}\n局面：{state.model_dump_json()}\n"
                    f"候选：{[c.model_dump() for c in candidates]}\n"
                    f"合法性：{[r.model_dump() for r in legality]}"
                ),
            },
        ]
        data = self.llm.chat_json(messages, tier="reasoning")
        return AdviceResult.model_validate(
            normalize_advice_payload(data, candidates, legality)
        )
