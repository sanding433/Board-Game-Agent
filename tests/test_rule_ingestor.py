from board_game_agent.agents.rule_ingestor import RuleIngestor, normalize_rule_card_payload
from board_game_agent.models.schemas import RuleCard


def test_ingest_returns_rule_card(mocker, tmp_path):
    rules = tmp_path / "rules.md"
    rules.write_text("# Toy\npass is legal\n", encoding="utf-8")
    llm = mocker.Mock()
    llm.chat_json.return_value = {
        "game_name": "Toy",
        "phases": ["play"],
        "actions": [{"name": "pass", "summary": "跳过"}],
        "scoring_notes": ["高分胜"],
        "ambiguities": [],
        "critical_slots": ["hand", "funds", "phase", "active_seat"],
        "raw_summary": "简版",
    }
    card = RuleIngestor(llm).ingest(rules.read_text(encoding="utf-8"))
    assert isinstance(card, RuleCard)
    assert card.game_name == "Toy"
    llm.chat_json.assert_called_once()


def test_normalize_phases_objects_and_slots_dict():
    raw = {
        "game_name": "Brass",
        "phases": [
            {"name": "Canal Era", "description": "..."},
            {"name": "Rail Era", "description": "..."},
        ],
        "actions": [{"name": "build", "summary": "建造"}],
        "scoring_notes": "按 VP 计分",
        "ambiguities": [],
        "critical_slots": {"hand": "手牌", "funds": "资金", "phase": "阶段", "active_seat": "座位"},
        "raw_summary": "摘要",
    }
    data = normalize_rule_card_payload(raw)
    assert data["phases"] == ["Canal Era", "Rail Era"]
    assert data["scoring_notes"] == ["按 VP 计分"]
    assert set(data["critical_slots"]) >= {"hand", "funds", "phase", "active_seat"}


def test_ingest_normalizes_drifted_payload(mocker):
    llm = mocker.Mock()
    llm.chat_json.return_value = {
        "game_name": "Brass",
        "phases": [{"name": "Canal Era"}],
        "actions": [{"name": "build", "summary": "建"}],
        "scoring_notes": "VP",
        "ambiguities": [],
        "critical_slots": {"hand": "x", "funds": "y"},
        "raw_summary": "s",
    }
    card = RuleIngestor(llm).ingest("rules")
    assert card.phases == ["Canal Era"]
    assert "hand" in card.critical_slots
