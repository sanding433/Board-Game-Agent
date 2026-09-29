from board_game_agent.agents.critic import Critic
from board_game_agent.models.schemas import CandidateAction, GameState, LegalityReport, RuleCard


def test_critic_finalize(mocker):
    llm = mocker.Mock()
    llm.chat_json.return_value = {
        "final_text": "建议过牌。",
        "candidates": [],
        "legality": [],
        "clarifications": [],
    }
    result = Critic(llm).finalize(
        [CandidateAction(action="pass", rationale="稳")],
        [LegalityReport(action="pass", legal=True)],
        GameState(phase="play"),
        RuleCard(game_name="Toy"),
    )
    assert "过牌" in result.final_text
    assert llm.chat_json.call_args.kwargs["tier"] == "reasoning"
