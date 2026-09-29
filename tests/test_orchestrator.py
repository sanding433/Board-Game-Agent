from pathlib import Path

from board_game_agent.config import Settings
from board_game_agent.models.schemas import Clarification, Event, GameState, RuleCard
from board_game_agent.orchestrator import Orchestrator
from board_game_agent.session.store import SessionStore


def _ready_state() -> GameState:
    return GameState(
        phase="play",
        active_seat="A",
        me={"hand": ["A", "B"], "funds": 10},
        public={},
    )


def _card() -> RuleCard:
    return RuleCard(game_name="Toy", critical_slots=["hand", "funds", "phase", "active_seat"])


def test_say_with_missing_critical_does_not_call_strategist(mocker, tmp_sessions):
    settings = Settings(sessions_dir=tmp_sessions, deepseek_api_key="k")
    store = SessionStore(tmp_sessions)
    orch = Orchestrator(settings, llm=mocker.Mock(), store=store)
    sid = orch.new_session("t")
    store.write_rule_card(sid, _card())
    orch.state_parser = mocker.Mock()
    orch.state_parser.parse.return_value = mocker.Mock(
        events=[Event(type="phase_change", raw_text="play", parsed={"phase": "play"})],
        clarifications=[],
        assumptions=[],
    )
    orch.strategist = mocker.Mock()
    msg = orch.say(sid, "进入 play")
    assert "补充" in msg or "手牌" in msg or "资金" in msg
    orch.strategist.propose.assert_not_called()


def test_advise_blocked_when_clarifications_pending(mocker, tmp_sessions):
    settings = Settings(sessions_dir=tmp_sessions, deepseek_api_key="k")
    store = SessionStore(tmp_sessions)
    orch = Orchestrator(settings, llm=mocker.Mock(), store=store)
    sid = orch.new_session("t")
    store.write_rule_card(sid, _card())
    store.write_state(sid, GameState(phase="play"))
    orch.strategist = mocker.Mock()
    msg = orch.advise(sid)
    assert "补充" in msg
    orch.strategist.propose.assert_not_called()


def test_advise_runs_full_pipeline_when_state_complete(mocker, tmp_sessions):
    settings = Settings(sessions_dir=tmp_sessions, deepseek_api_key="k")
    store = SessionStore(tmp_sessions)
    orch = Orchestrator(settings, llm=mocker.Mock(), store=store)
    sid = orch.new_session("t")
    store.write_rule_card(sid, _card())
    store.write_state(sid, _ready_state())
    orch.strategist = mocker.Mock()
    orch.strategist.propose.return_value = []
    orch.legality = mocker.Mock()
    orch.legality.check.return_value = []
    orch.critic = mocker.Mock()
    orch.critic.finalize.return_value = mocker.Mock(final_text="建议过牌。", model_dump_json=lambda indent=2: "{}")
    # AdviceResult needs model_dump_json - use real AdviceResult
    from board_game_agent.models.schemas import AdviceResult

    orch.critic.finalize.return_value = AdviceResult(final_text="建议过牌。")
    text = orch.advise(sid)
    assert "过牌" in text
    orch.strategist.propose.assert_called_once()
    orch.legality.check.assert_called_once()
    orch.critic.finalize.assert_called_once()
