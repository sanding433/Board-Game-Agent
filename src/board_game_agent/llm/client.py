from __future__ import annotations

import json
import re
import time
from typing import Any, Literal

from openai import APIError, OpenAI

from board_game_agent.config import Settings

Tier = Literal["fast", "reasoning"]


def extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", text)
        if not m:
            raise
        return json.loads(m.group(0))


class LLMClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._client = OpenAI(
            api_key=settings.deepseek_api_key or "missing",
            base_url=settings.deepseek_base_url,
        )

    def _model(self, tier: Tier) -> str:
        return self.settings.model_fast if tier == "fast" else self.settings.model_reasoning

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        tier: Tier = "fast",
        temperature: float = 0.2,
    ) -> str:
        last_err: Exception | None = None
        for attempt in range(2):
            try:
                resp = self._client.chat.completions.create(
                    model=self._model(tier),
                    messages=messages,
                    temperature=temperature,
                )
                return resp.choices[0].message.content or ""
            except APIError as exc:
                last_err = exc
                if attempt == 0:
                    time.sleep(0.5)
                    continue
                raise
        raise last_err  # pragma: no cover

    def chat_json(
        self, messages: list[dict[str, str]], *, tier: Tier = "fast"
    ) -> dict[str, Any]:
        text = self.chat(messages, tier=tier)
        return extract_json_object(text)
