from board_game_agent.config import Settings
from board_game_agent.models.schemas import AdviceResult, CandidateAction, Event, GameState, RuleCard
from board_game_agent.orchestrator import Orchestrator
from board_game_agent.session.store import SessionStore
from board_game_agent.session.timeline import read_events


def test_e2e_mocked_session(mocker, tmp_sessions):
    settings = Settings(sessions_dir=tmp_sessions, deepseek_api_key="k", auto_advise_after_say=False)
    store = SessionStore(tmp_sessions)
    orch = Orchestrator(settings, llm=mocker.Mock(), store=store)
    sid = orch.new_session("e2e")

    orch.rule_ingestor = mocker.Mock()
    orch.rule_ingestor.ingest.return_value = RuleCard(
        game_name="Toy",
        critical_slots=["hand", "funds", "phase", "active_seat"],
    )
    rules = tmp_sessions / "rules.md"
    rules.write_text("# Toy\n", encoding="utf-8")
    orch.load_rules(sid, rules)

    orch.state_parser = mocker.Mock()
    orch.state_parser.parse.return_value = mocker.Mock(
        events=[Event(type="phase_change", raw_text="play", parsed={"phase": "play"})],
        clarifications=[],
        assumptions=[],
    )
    msg1 = orch.say(sid, "进入 play")
    assert "补充" in msg1 or "手牌" in msg1

    orch.state_parser.parse.return_value = mocker.Mock(
        events=[
            Event(
                type="private_info",
                raw_text="完整",
                parsed={
                    "phase": "play",
                    "active_seat": "A",
                    "me": {"hand": ["X"], "funds": 5},
                },
                visibility="private",
            )
        ],
        clarifications=[],
        assumptions=[],
    )
    msg2 = orch.say(sid, "手牌 X，资金 5，轮到 A")
    assert "advise" in msg2.lower() or "建议" in msg2

    orch.strategist = mocker.Mock()
    orch.strategist.propose.return_value = [CandidateAction(action="pass", rationale="稳")]
    orch.legality = mocker.Mock()
    orch.legality.check.return_value = []
    orch.critic = mocker.Mock()
    orch.critic.finalize.return_value = AdviceResult(final_text="建议过牌。")
    advice = orch.advise(sid)
    assert "过牌" in advice
    assert len(read_events(store, sid)) >= 2
    assert orch.undo(sid).startswith("已撤销")
