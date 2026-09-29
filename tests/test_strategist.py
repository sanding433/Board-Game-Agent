from board_game_agent.agents.strategist import Strategist
from board_game_agent.models.schemas import GameState, RuleCard


def test_strategist_uses_reasoning_tier(mocker):
    llm = mocker.Mock()
    llm.chat_json.return_value = {
        "candidates": [{"action": "pass", "rationale": "保资源", "assumptions": []}]
    }
    cands = Strategist(llm).propose(GameState(phase="play"), RuleCard(game_name="Toy"), [])
    assert cands[0].action == "pass"
    assert llm.chat_json.call_args.kwargs["tier"] == "reasoning"
