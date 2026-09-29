from board_game_agent.agents.critic import Critic, normalize_advice_payload
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


def test_normalize_string_clarifications():
    data = normalize_advice_payload(
        {
            "final_text": "建棉纺。",
            "clarifications": ["请确认手牌", "请确认连线"],
        },
        [],
        [],
    )
    assert data["clarifications"][0]["slot"] == "note_0"
    assert "手牌" in data["clarifications"][0]["question"]
