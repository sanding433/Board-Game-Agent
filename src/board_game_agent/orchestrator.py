from __future__ import annotations

import json
from pathlib import Path

from board_game_agent.agents.critic import Critic
from board_game_agent.agents.legality import LegalityChecker
from board_game_agent.agents.rule_ingestor import RuleIngestor
from board_game_agent.agents.state_parser import SLOT_QUESTIONS, StateParser, missing_critical
from board_game_agent.agents.strategist import Strategist
from board_game_agent.config import Settings
from board_game_agent.llm.client import LLMClient
from board_game_agent.models.schemas import Clarification, GameState
from board_game_agent.session.reducer import reduce_events
from board_game_agent.session.store import SessionStore
from board_game_agent.session.timeline import append_event, read_events, undo_last_user_event


class Orchestrator:
    def __init__(self, settings: Settings, llm: LLMClient | None = None, store: SessionStore | None = None):
        self.settings = settings
        self.llm = llm or LLMClient(settings)
        self.store = store or SessionStore(settings.sessions_dir)
        lang = settings.reply_language
        self.rule_ingestor = RuleIngestor(self.llm, lang)
        self.state_parser = StateParser(self.llm, lang)
        self.legality = LegalityChecker(self.llm, lang)
        self.strategist = Strategist(self.llm, lang)
        self.critic = Critic(self.llm, lang)
        self._turn = 0

    def _require_sid(self, sid: str | None) -> str:
        sid = sid or self.store.get_current()
        if not sid:
            raise ValueError("没有当前 Session。请先执行 new。")
        if not (self.store.path(sid) / "meta.json").exists():
            raise ValueError(f"Session 不存在: {sid}")
        return sid

    def new_session(self, name: str = "") -> str:
        return self.store.create(name=name)

    def load_rules(self, sid: str, path: Path) -> str:
        sid = self._require_sid(sid)
        text = Path(path).read_text(encoding="utf-8")
        self.store.write_rules_raw(sid, text)
        card = self.rule_ingestor.ingest(text)
        self.store.write_rule_card(sid, card)
        return f"规则已加载：{card.game_name or path.name}。critical_slots={card.critical_slots}"

    def _format_clarifications(self, items: list[Clarification]) -> str:
        lines = ["信息不足，请补充："]
        for c in items:
            lines.append(f"- [{c.slot}] {c.question}")
        return "\n".join(lines)

    def _clarifications_for_state(self, state: GameState, card) -> list[Clarification]:
        missing = missing_critical(state, card)
        return [
            Clarification(slot=s, question=SLOT_QUESTIONS.get(s, f"请补充字段：{s}"))
            for s in missing
        ]

    def say(self, sid: str | None, text: str) -> str:
        sid = self._require_sid(sid)
        card = self.store.read_rule_card(sid)
        if card is None:
            raise ValueError("尚未加载规则。请先执行 rules <path>。")
        state = self.store.read_state(sid)
        parsed = self.state_parser.parse(text, card, state)
        for event in parsed.events:
            append_event(self.store, sid, event)
        if parsed.assumptions:
            existing = self.store.read_assumptions(sid)
            block = "\n".join(f"- {a}" for a in parsed.assumptions)
            self.store.write_assumptions(sid, (existing + "\n" + block).strip() + "\n")
        events = read_events(self.store, sid)
        new_state = reduce_events(events)
        clarifications = parsed.clarifications + self._clarifications_for_state(new_state, card)
        # de-dupe by slot
        seen: set[str] = set()
        uniq: list[Clarification] = []
        for c in clarifications:
            if c.slot not in seen:
                seen.add(c.slot)
                uniq.append(c)
        new_state.pending_clarifications = uniq
        self.store.write_state(sid, new_state)
        self.store.append_transcript(sid, f"用户: {text}")
        if uniq:
            msg = self._format_clarifications(uniq)
            self.store.append_transcript(sid, f"系统: {msg}")
            return msg
        if self.settings.auto_advise_after_say:
            return self.advise(sid)
        ack = "局面已更新。输入 advise 获取建议。"
        self.store.append_transcript(sid, f"系统: {ack}")
        return ack

    def advise(self, sid: str | None = None) -> str:
        sid = self._require_sid(sid)
        card = self.store.read_rule_card(sid)
        if card is None:
            raise ValueError("尚未加载规则。请先执行 rules <path>。")
        state = self.store.read_state(sid)
        clarifications = self._clarifications_for_state(state, card)
        if clarifications:
            state.pending_clarifications = clarifications
            self.store.write_state(sid, state)
            return self._format_clarifications(clarifications)
        assumptions = [
            line.lstrip("- ").strip()
            for line in self.store.read_assumptions(sid).splitlines()
            if line.strip()
        ]
        candidates = self.strategist.propose(state, card, assumptions)
        legality = self.legality.check(candidates, state, card)
        advice = self.critic.finalize(candidates, legality, state, card)
        self._turn += 1
        turn_dir = self.store.path(sid) / "turns" / str(self._turn)
        turn_dir.mkdir(parents=True, exist_ok=True)
        (turn_dir / "advice.json").write_text(advice.model_dump_json(indent=2), encoding="utf-8")
        self.store.append_transcript(sid, f"建议: {advice.final_text}")
        return advice.final_text

    def ask(self, sid: str | None, text: str) -> str:
        sid = self._require_sid(sid)
        card = self.store.read_rule_card(sid)
        raw = self.store.read_rules_raw(sid)
        if not raw and card is None:
            raise ValueError("尚未加载规则。")
        messages = [
            {
                "role": "system",
                "content": "你是规则问答助手。只根据提供的规则回答，不要改写对局状态。",
            },
            {
                "role": "user",
                "content": f"规则原文：\n{raw}\n\n规则卡片：{card.model_dump_json() if card else '{}'}\n\n问题：{text}",
            },
        ]
        return self.llm.chat(messages, tier="fast")

    def status(self, sid: str | None = None) -> str:
        sid = self._require_sid(sid)
        state = self.store.read_state(sid)
        meta = self.store.read_meta(sid)
        events = read_events(self.store, sid)
        lines = [
            f"Session: {sid} ({meta.get('name')})",
            f"阶段: {state.phase}",
            f"行动座位: {state.active_seat}",
            f"事件数: {len(events)}",
            f"me: {json.dumps(state.me, ensure_ascii=False)}",
            f"public: {json.dumps(state.public, ensure_ascii=False)}",
            f"假设:\n{self.store.read_assumptions(sid) or '(无)'}",
        ]
        if state.pending_clarifications:
            lines.append("未决追问:")
            for c in state.pending_clarifications:
                lines.append(f"- [{c.slot}] {c.question}")
        return "\n".join(lines)

    def undo(self, sid: str | None = None) -> str:
        sid = self._require_sid(sid)
        undone = undo_last_user_event(self.store, sid)
        if undone is None:
            return "没有可撤销的事件。"
        events = read_events(self.store, sid)
        card = self.store.read_rule_card(sid)
        state = reduce_events(events)
        if card:
            state.pending_clarifications = self._clarifications_for_state(state, card)
        self.store.write_state(sid, state)
        return f"已撤销: {undone.raw_text}"

    def end(self, sid: str | None = None) -> str:
        sid = self._require_sid(sid)
        meta = self.store.read_meta(sid)
        meta["status"] = "ended"
        self.store.write_meta(sid, meta)
        return f"Session {sid} 已结束。文件保留于 {self.store.path(sid)}"
