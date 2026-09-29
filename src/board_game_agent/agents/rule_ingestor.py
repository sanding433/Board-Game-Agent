from __future__ import annotations

from typing import Any

from board_game_agent.agents.base import system_prompt
from board_game_agent.llm.client import LLMClient
from board_game_agent.models.schemas import RuleCard

DEFAULT_CRITICAL = ["hand", "funds", "phase", "active_seat"]


def normalize_rule_card_payload(data: dict[str, Any]) -> dict[str, Any]:
    """Coerce common LLM shape drift into RuleCard fields."""
    out = dict(data)

    phases = out.get("phases", [])
    if isinstance(phases, list):
        normalized_phases: list[str] = []
        for p in phases:
            if isinstance(p, str):
                normalized_phases.append(p)
            elif isinstance(p, dict):
                normalized_phases.append(str(p.get("name") or p.get("phase") or p))
            else:
                normalized_phases.append(str(p))
        out["phases"] = normalized_phases

    for key in ("scoring_notes", "ambiguities"):
        val = out.get(key, [])
        if isinstance(val, str):
            out[key] = [val] if val.strip() else []
        elif val is None:
            out[key] = []

    slots = out.get("critical_slots", DEFAULT_CRITICAL)
    if isinstance(slots, dict):
        out["critical_slots"] = list(slots.keys()) or list(DEFAULT_CRITICAL)
    elif isinstance(slots, list):
        norm_slots: list[str] = []
        for s in slots:
            if isinstance(s, str):
                norm_slots.append(s)
            elif isinstance(s, dict):
                norm_slots.append(str(s.get("slot") or s.get("name") or s))
            else:
                norm_slots.append(str(s))
        out["critical_slots"] = norm_slots or list(DEFAULT_CRITICAL)
    else:
        out["critical_slots"] = list(DEFAULT_CRITICAL)

    # Ensure defaults present
    for slot in DEFAULT_CRITICAL:
        if slot not in out["critical_slots"]:
            out["critical_slots"].append(slot)

    actions = out.get("actions", [])
    if isinstance(actions, dict):
        out["actions"] = [{"name": k, "summary": str(v)} for k, v in actions.items()]
    elif not isinstance(actions, list):
        out["actions"] = []

    if not isinstance(out.get("game_name"), str):
        out["game_name"] = str(out.get("game_name") or "")
    if not isinstance(out.get("raw_summary"), str):
        out["raw_summary"] = str(out.get("raw_summary") or "")

    return out


class RuleIngestor:
    def __init__(self, llm: LLMClient, language: str = "zh"):
        self.llm = llm
        self.language = language

    def ingest(self, rules_text: str) -> RuleCard:
        # Truncate extremely long rulebooks to stay within context; keep head+tail.
        text = rules_text
        max_chars = 60000
        if len(text) > max_chars:
            head = text[:45000]
            tail = text[-10000:]
            text = head + "\n\n...[truncated]...\n\n" + tail

        messages = [
            {"role": "system", "content": system_prompt(self.language)},
            {
                "role": "user",
                "content": (
                    "将下列桌游规则整理为 JSON，字段类型必须严格如下：\n"
                    '- game_name: string\n'
                    '- phases: string[]（只要阶段名，不要对象）\n'
                    '- actions: [{ "name": string, "summary": string }]\n'
                    '- scoring_notes: string[]\n'
                    '- ambiguities: string[]\n'
                    '- critical_slots: string[]（至少含 hand, funds, phase, active_seat）\n'
                    '- raw_summary: string\n'
                    "只返回 JSON 对象。\n\n"
                    f"规则文本：\n{text}"
                ),
            },
        ]
        data = self.llm.chat_json(messages, tier="fast")
        return RuleCard.model_validate(normalize_rule_card_payload(data))
