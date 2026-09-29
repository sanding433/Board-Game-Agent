from board_game_agent.config import Settings
from board_game_agent.llm.client import LLMClient


def test_chat_uses_base_url_and_model(mocker):
    settings = Settings(deepseek_api_key="k", deepseek_base_url="https://api.deepseek.com")
    fake = mocker.Mock()
    fake.choices = [mocker.Mock(message=mocker.Mock(content='{"ok": true}'))]
    create = mocker.patch("board_game_agent.llm.client.OpenAI")
    create.return_value.chat.completions.create.return_value = fake

    client = LLMClient(settings)
    text = client.chat([{"role": "user", "content": "hi"}], tier="fast")
    assert text == '{"ok": true}'
    kwargs = create.return_value.chat.completions.create.call_args.kwargs
    assert kwargs["model"] == settings.model_fast


def test_chat_json_parses_object(mocker):
    settings = Settings(deepseek_api_key="k")
    fake = mocker.Mock()
    fake.choices = [mocker.Mock(message=mocker.Mock(content='{"a": 1}'))]
    mocker.patch("board_game_agent.llm.client.OpenAI").return_value.chat.completions.create.return_value = fake
    client = LLMClient(settings)
    assert client.chat_json([{"role": "user", "content": "x"}], tier="fast") == {"a": 1}
