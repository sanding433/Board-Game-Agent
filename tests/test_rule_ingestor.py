from board_game_agent.agents.rule_ingestor import RuleIngestor
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
