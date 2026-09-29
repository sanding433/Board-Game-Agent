from board_game_agent.models.schemas import Event
from board_game_agent.session.reducer import reduce_events


def test_reduce_merges_parsed_fields():
    events = [
        Event(type="phase_change", raw_text="进入运河期", parsed={"phase": "canal"}, visibility="public"),
        Event(type="private_info", raw_text="资金30", parsed={"me": {"funds": 30}}, visibility="private"),
        Event(
            type="public_action",
            raw_text="对手建厂",
            parsed={"public": {"last_build": "coal"}},
            visibility="public",
        ),
    ]
    state = reduce_events(events)
    assert state.phase == "canal"
    assert state.me["funds"] == 30
    assert state.public["last_build"] == "coal"


def test_out_of_view_does_not_enter_me_or_public_as_fact():
    events = [
        Event(
            type="private_info",
            raw_text="对手手里有铁牌",
            parsed={"out_of_view": "对手手牌=铁"},
            visibility="private",
        ),
    ]
    state = reduce_events(events)
    assert "对手手牌" not in str(state.me)
    assert any("对手手牌" in n for n in state.out_of_view_notes)
