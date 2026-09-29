from board_game_agent.config import Settings


def test_settings_from_env(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("MODEL_FAST", "deepseek-chat")
    s = Settings()
    assert s.deepseek_api_key == "test-key"
    assert s.model_fast == "deepseek-chat"
    assert s.auto_advise_after_say is False
