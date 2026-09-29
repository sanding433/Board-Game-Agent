from board_game_agent.agents.legality import LegalityChecker
from board_game_agent.models.schemas import CandidateAction, GameState, RuleCard


def test_legality_uses_fast_tier(mocker):
    llm = mocker.Mock()
    llm.chat_json.return_value = {
        "reports": [{"action": "pass", "legal": True, "reason": "ok"}]
    }
    reports = LegalityChecker(llm).check(
        [CandidateAction(action="pass", rationale="稳")],
        GameState(phase="play"),
        RuleCard(game_name="Toy"),
    )
    assert reports[0].legal is True
    assert llm.chat_json.call_args.kwargs["tier"] == "fast"
