from board_game_agent.models.schemas import AdviceResult, Event, RuleCard


def test_event_roundtrip():
    e = Event(type="private_info", raw_text="我有 £30", visibility="private")
    data = e.model_dump()
    assert Event.model_validate(data).raw_text == "我有 £30"


def test_rule_card_critical_slots():
    card = RuleCard(
        game_name="Toy",
        phases=["setup", "play"],
        actions=[{"name": "pass", "summary": "跳过"}],
        scoring_notes=["分高者胜"],
        ambiguities=[],
        critical_slots=["hand", "funds", "phase", "active_seat"],
    )
    assert "hand" in card.critical_slots


def test_advice_result():
    a = AdviceResult(final_text="建议过牌。", candidates=[], clarifications=[])
    assert "过牌" in a.final_text
