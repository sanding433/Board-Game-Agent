from board_game_agent.agents.state_parser import StateParser, coerce_event_dict, missing_critical
from board_game_agent.models.schemas import Event, GameState, RuleCard


def _card():
    return RuleCard(game_name="Toy", critical_slots=["hand", "funds", "phase", "active_seat"])


def test_parser_emits_event_and_clarifications(mocker):
    llm = mocker.Mock()
    llm.chat_json.return_value = {
        "events": [
            {
                "type": "phase_change",
                "raw_text": "进入 play",
                "parsed": {"phase": "play"},
                "visibility": "public",
                "conflict": False,
            }
        ],
        "clarifications": [
            {"slot": "hand", "question": "你的手牌是什么？"},
            {"slot": "funds", "question": "你当前资金多少？"},
        ],
        "assumptions": [],
    }
    result = StateParser(llm).parse("进入 play 阶段，轮到我", _card(), GameState())
    assert result.events[0].parsed["phase"] == "play"
    assert {c.slot for c in result.clarifications} >= {"hand", "funds"}


def test_missing_critical_slots_forced_when_model_forgets():
    state = GameState(phase="play")
    missing = missing_critical(state, _card())
    assert "hand" in missing and "funds" in missing and "active_seat" in missing


def test_coerce_event_aliases():
    e = Event.model_validate(
        coerce_event_dict({"type": "phase_declared", "raw_text": "运河期", "parsed": {"phase": "canal"}})
    )
    assert e.type == "phase_change"
    e2 = Event.model_validate(
        coerce_event_dict({"type": "state_update", "raw_text": "资金30", "parsed": {"me": {"funds": 30}}})
    )
    assert e2.type == "private_info"
