# Board Game Advisor Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a Python CLI that runs a full-game Session: user uploads Markdown rules, narrates seat-visible info in natural language, multi-agent pipeline (DeepSeek) clarifies then advises from that player's perspective.

**Architecture:** Disk-backed Session (`timeline.jsonl` → `state/current.json`) with a deterministic orchestrator calling five agents (RuleIngestor → StateParser → LegalityChecker → Strategist → Critic) over an OpenAI-compatible DeepSeek client. Users only see NL; structured JSON is internal.

**Tech Stack:** Python 3.11+, `openai` SDK, `pydantic` v2, `typer` (or `argparse`), `pytest`, `python-dotenv`. LLM: DeepSeek API (`deepseek-chat` / `deepseek-reasoner`).

**Spec:** `docs/superpowers/specs/2026-09-29-board-game-agent-design.md`

---

## File structure

```
board-game-agent/
  pyproject.toml
  .env.example
  README.md
  src/board_game_agent/
    __init__.py
    __main__.py
    cli.py
    config.py
    llm/
      __init__.py
      client.py
    models/
      __init__.py
      schemas.py
    session/
      __init__.py
      store.py
      timeline.py
      reducer.py
    agents/
      __init__.py
      base.py
      rule_ingestor.py
      state_parser.py
      legality.py
      strategist.py
      critic.py
    orchestrator.py
  tests/
    conftest.py
    test_config.py
    test_schemas.py
    test_session_store.py
    test_timeline.py
    test_reducer.py
    test_llm_client.py
    test_rule_ingestor.py
    test_state_parser.py
    test_legality.py
    test_strategist.py
    test_critic.py
    test_orchestrator.py
    test_cli.py
  fixtures/
    toy_game/
      rules.md
    birmingham/
      rules.md          # short stub / condensed notes for tests — user replaces with full text for table play
      scripts/
        opening_missing_hand.md
```

---

### Task 1: Project scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `src/board_game_agent/__init__.py`
- Create: `src/board_game_agent/__main__.py`
- Create: `tests/conftest.py`
- Create: `README.md` (minimal: install + env + `python -m board_game_agent --help`)

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "board-game-agent"
version = "0.1.0"
description = "Multi-agent CLI advisor for board games (player-perspective)"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
  "openai>=1.40.0",
  "pydantic>=2.7.0",
  "pydantic-settings>=2.3.0",
  "python-dotenv>=1.0.0",
  "typer>=0.12.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0.0", "pytest-mock>=3.14.0"]

[project.scripts]
bga = "board_game_agent.cli:app"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

- [ ] **Step 2: Create package stubs and `.env.example`**

`.env.example`:

```env
DEEPSEEK_API_KEY=sk-...
DEEPSEEK_BASE_URL=https://api.deepseek.com
MODEL_FAST=deepseek-chat
MODEL_REASONING=deepseek-reasoner
REPLY_LANGUAGE=zh
AUTO_ADVISE_AFTER_SAY=false
SESSIONS_DIR=sessions
```

`src/board_game_agent/__init__.py`:

```python
__version__ = "0.1.0"
```

`src/board_game_agent/__main__.py`:

```python
from board_game_agent.cli import app

if __name__ == "__main__":
    app()
```

`tests/conftest.py`:

```python
import pytest
from pathlib import Path


@pytest.fixture
def tmp_sessions(tmp_path: Path) -> Path:
    d = tmp_path / "sessions"
    d.mkdir()
    return d
```

- [ ] **Step 3: Install editable package**

Run: `pip install -e ".[dev]"`  
Expected: succeeds with no errors

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml .env.example README.md src/board_game_agent/__init__.py src/board_game_agent/__main__.py tests/conftest.py
git commit -m "chore: scaffold Python package for board game agent"
```

---

### Task 2: Config

**Files:**
- Create: `src/board_game_agent/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_config.py
import os
from board_game_agent.config import Settings


def test_settings_from_env(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("MODEL_FAST", "deepseek-chat")
    s = Settings()
    assert s.deepseek_api_key == "test-key"
    assert s.model_fast == "deepseek-chat"
    assert s.auto_advise_after_say is False
```

- [ ] **Step 2: Run test — expect FAIL**

Run: `pytest tests/test_config.py -v`  
Expected: FAIL (module not found or Settings missing)

- [ ] **Step 3: Implement `config.py`**

```python
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    model_fast: str = "deepseek-chat"
    model_reasoning: str = "deepseek-reasoner"
    reply_language: str = "zh"
    auto_advise_after_say: bool = False
    sessions_dir: Path = Path("sessions")
```

- [ ] **Step 4: Run test — expect PASS**

Run: `pytest tests/test_config.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/board_game_agent/config.py tests/test_config.py
git commit -m "feat: add Settings for DeepSeek and session paths"
```

---

### Task 3: Pydantic schemas

**Files:**
- Create: `src/board_game_agent/models/__init__.py`
- Create: `src/board_game_agent/models/schemas.py`
- Create: `tests/test_schemas.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_schemas.py
from board_game_agent.models.schemas import Event, GameState, RuleCard, AdviceResult


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
```

- [ ] **Step 2: Run — expect FAIL**

Run: `pytest tests/test_schemas.py -v`

- [ ] **Step 3: Implement schemas**

```python
# src/board_game_agent/models/schemas.py
from __future__ import annotations
from typing import Any, Literal
from pydantic import BaseModel, Field


EventType = Literal[
    "setup", "public_action", "private_info", "phase_change", "resolve", "correction"
]
Visibility = Literal["private", "public"]


class Event(BaseModel):
    type: EventType
    raw_text: str
    parsed: dict[str, Any] = Field(default_factory=dict)
    visibility: Visibility = "public"
    conflict: bool = False


class Clarification(BaseModel):
    slot: str
    question: str


class RuleCard(BaseModel):
    game_name: str = ""
    phases: list[str] = Field(default_factory=list)
    actions: list[dict[str, Any]] = Field(default_factory=list)
    scoring_notes: list[str] = Field(default_factory=list)
    ambiguities: list[str] = Field(default_factory=list)
    critical_slots: list[str] = Field(
        default_factory=lambda: ["hand", "funds", "phase", "active_seat"]
    )
    raw_summary: str = ""


class GameState(BaseModel):
    phase: str | None = None
    active_seat: str | None = None
    me: dict[str, Any] = Field(default_factory=dict)
    public: dict[str, Any] = Field(default_factory=dict)
    last_events: list[str] = Field(default_factory=list)
    pending_clarifications: list[Clarification] = Field(default_factory=list)
    out_of_view_notes: list[str] = Field(default_factory=list)


class CandidateAction(BaseModel):
    action: str
    rationale: str
    assumptions: list[str] = Field(default_factory=list)


class LegalityReport(BaseModel):
    action: str
    legal: bool
    reason: str = ""


class AdviceResult(BaseModel):
    final_text: str
    candidates: list[CandidateAction] = Field(default_factory=list)
    legality: list[LegalityReport] = Field(default_factory=list)
    clarifications: list[Clarification] = Field(default_factory=list)
```

`models/__init__.py`: re-export the public models.

- [ ] **Step 4: Run — expect PASS**

Run: `pytest tests/test_schemas.py -v`

- [ ] **Step 5: Commit**

```bash
git add src/board_game_agent/models tests/test_schemas.py
git commit -m "feat: add Event, GameState, RuleCard, Advice schemas"
```

---

### Task 4: Session store + timeline

**Files:**
- Create: `src/board_game_agent/session/__init__.py`
- Create: `src/board_game_agent/session/store.py`
- Create: `src/board_game_agent/session/timeline.py`
- Create: `tests/test_session_store.py`
- Create: `tests/test_timeline.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_session_store.py
from board_game_agent.session.store import SessionStore


def test_create_session_layout(tmp_sessions):
    store = SessionStore(tmp_sessions)
    sid = store.create(name="toy")
    root = store.path(sid)
    assert (root / "meta.json").exists()
    assert (root / "timeline.jsonl").exists()
    assert (root / "rules").is_dir()
    assert (root / "state").is_dir()


def test_write_and_read_rules(tmp_sessions):
    store = SessionStore(tmp_sessions)
    sid = store.create(name="toy")
    store.write_rules_raw(sid, "# Toy Rules\nPass is legal.\n")
    assert "Pass" in store.read_rules_raw(sid)
```

```python
# tests/test_timeline.py
from board_game_agent.models.schemas import Event
from board_game_agent.session.store import SessionStore
from board_game_agent.session.timeline import append_event, read_events, undo_last_user_event


def test_append_and_undo(tmp_sessions):
    store = SessionStore(tmp_sessions)
    sid = store.create(name="toy")
    append_event(store, sid, Event(type="setup", raw_text="开局", visibility="public"))
    append_event(store, sid, Event(type="private_info", raw_text="手牌 A", visibility="private"))
    assert len(read_events(store, sid)) == 2
    undone = undo_last_user_event(store, sid)
    assert undone is not None
    assert len(read_events(store, sid)) == 1
```

- [ ] **Step 2: Run — expect FAIL**

Run: `pytest tests/test_session_store.py tests/test_timeline.py -v`

- [ ] **Step 3: Implement store + timeline**

`store.py` responsibilities:
- `create(name) -> sid` (uuid4 hex short)
- `path(sid)`, `list_sessions()`, `set_current` / `get_current` via `sessions/.current`
- `write_rules_raw` / `read_rules_raw`
- `write_rule_card` / `read_rule_card` (JSON)
- `write_state` / `read_state`
- `write_assumptions` / `append_transcript`
- ensure dirs: `rules/`, `state/`, `turns/`

`timeline.py`:
- append one JSON line per Event to `timeline.jsonl`
- `read_events` → `list[Event]`
- `undo_last_user_event` pops last line (all events from user narration are user events in MVP)

- [ ] **Step 4: Run — expect PASS**

Run: `pytest tests/test_session_store.py tests/test_timeline.py -v`

- [ ] **Step 5: Commit**

```bash
git add src/board_game_agent/session tests/test_session_store.py tests/test_timeline.py
git commit -m "feat: session store and append-only timeline with undo"
```

---

### Task 5: State reducer (deterministic, no LLM)

**Files:**
- Create: `src/board_game_agent/session/reducer.py`
- Create: `tests/test_reducer.py`

- [ ] **Step 1: Write failing tests**

```python
from board_game_agent.models.schemas import Event, GameState
from board_game_agent.session.reducer import reduce_events


def test_reduce_merges_parsed_fields():
    events = [
        Event(type="phase_change", raw_text="进入运河期", parsed={"phase": "canal"}, visibility="public"),
        Event(type="private_info", raw_text="资金30", parsed={"me": {"funds": 30}}, visibility="private"),
        Event(type="public_action", raw_text="对手建厂", parsed={"public": {"last_build": "coal"}}, visibility="public"),
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
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement `reduce_events`**

Merge `parsed` keys shallowly into `GameState`:
- `phase`, `active_seat` overwrite when present
- `me` / `public` dicts update via `.update`
- `out_of_view` string/list → `out_of_view_notes`
- `last_events` = last 5 `raw_text` values
- Do **not** invent fields; missing → leave `None`/empty

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add src/board_game_agent/session/reducer.py tests/test_reducer.py
git commit -m "feat: deterministic timeline-to-GameState reducer"
```

---

### Task 6: DeepSeek LLM client

**Files:**
- Create: `src/board_game_agent/llm/__init__.py`
- Create: `src/board_game_agent/llm/client.py`
- Create: `tests/test_llm_client.py`

- [ ] **Step 1: Write failing tests (mocked)**

```python
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
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement client**

```python
# src/board_game_agent/llm/client.py
from __future__ import annotations
import json
import re
from typing import Any, Literal
from openai import OpenAI
from board_game_agent.config import Settings

Tier = Literal["fast", "reasoning"]


class LLMClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._client = OpenAI(
            api_key=settings.deepseek_api_key or "missing",
            base_url=settings.deepseek_base_url,
        )

    def _model(self, tier: Tier) -> str:
        return self.settings.model_fast if tier == "fast" else self.settings.model_reasoning

    def chat(self, messages: list[dict[str, str]], *, tier: Tier = "fast", temperature: float = 0.2) -> str:
        resp = self._client.chat.completions.create(
            model=self._model(tier),
            messages=messages,
            temperature=temperature,
        )
        return resp.choices[0].message.content or ""

    def chat_json(self, messages: list[dict[str, str]], *, tier: Tier = "fast") -> dict[str, Any]:
        text = self.chat(messages, tier=tier)
        return extract_json_object(text)


def extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", text)
        if not m:
            raise
        return json.loads(m.group(0))
```

Retry once on API error inside `chat` (catch `openai.APIError`, sleep 0.5s, retry once, then re-raise).

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add src/board_game_agent/llm tests/test_llm_client.py
git commit -m "feat: OpenAI-compatible DeepSeek LLM client"
```

---

### Task 7: Agent base + RuleIngestor

**Files:**
- Create: `src/board_game_agent/agents/__init__.py`
- Create: `src/board_game_agent/agents/base.py`
- Create: `src/board_game_agent/agents/rule_ingestor.py`
- Create: `tests/test_rule_ingestor.py`
- Create: `fixtures/toy_game/rules.md`

- [ ] **Step 1: Add toy fixture**

`fixtures/toy_game/rules.md`:

```markdown
# 玩具竞速

2 名玩家。阶段：setup → play → end。
每回合当前玩家必须执行一个行动：build（花 1 元放一块）、pass。
资金保密。手牌：每人 2 张地点牌（A/B/C）。
公开信息：公共轨道上的块数。
得分：块多者胜。结束：任一方 pass 两次后进入 end。
```

- [ ] **Step 2: Write failing test with mock LLM**

```python
from board_game_agent.agents.rule_ingestor import RuleIngestor
from board_game_agent.models.schemas import RuleCard


def test_ingest_returns_rule_card(mocker, tmp_path):
    rules = (tmp_path / "rules.md")
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
```

- [ ] **Step 3: Implement**

`base.py`: small helper `system_prompt(language: str) -> str` prefix “用中文思考与输出 JSON …” when `reply_language=zh`.

`rule_ingestor.py`: prompt asks for exact RuleCard JSON keys; `tier="fast"`; validate with `RuleCard.model_validate`.

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add src/board_game_agent/agents fixtures/toy_game/rules.md tests/test_rule_ingestor.py
git commit -m "feat: RuleIngestor agent digests Markdown into RuleCard"
```

---

### Task 8: StateParser + clarification policy A

**Files:**
- Create: `src/board_game_agent/agents/state_parser.py`
- Create: `tests/test_state_parser.py`

- [ ] **Step 1: Write failing tests**

```python
from board_game_agent.agents.state_parser import StateParser
from board_game_agent.models.schemas import GameState, RuleCard


def _card():
    return RuleCard(game_name="Toy", critical_slots=["hand", "funds", "phase", "active_seat"])


def test_parser_emits_event_and_clarifications(mocker):
    llm = mocker.Mock()
    llm.chat_json.return_value = {
        "events": [
            {
                "type": "phase_change",
                "raw_text": "进入 play",
                "parsed": {"phase": "play"},
                "visibility": "public",
                "conflict": False,
            }
        ],
        "clarifications": [
            {"slot": "hand", "question": "你的手牌是什么？"},
            {"slot": "funds", "question": "你当前资金多少？"},
        ],
        "assumptions": [],
    }
    result = StateParser(llm).parse("进入 play 阶段，轮到我", _card(), GameState())
    assert result.events[0].parsed["phase"] == "play"
    assert {c.slot for c in result.clarifications} >= {"hand", "funds"}


def test_missing_critical_slots_forced_when_model_forgets():
    # After LLM returns events with phase set but no clarifications,
    # StateParser.missing_critical(state, card) must still list empty hand/funds/active_seat
    from board_game_agent.agents.state_parser import missing_critical

    state = GameState(phase="play")
    missing = missing_critical(state, _card())
    assert "hand" in missing and "funds" in missing and "active_seat" in missing
```

Implement `missing_critical` as pure function:
- `phase` missing if `state.phase` is None
- `active_seat` missing if `state.active_seat` is None
- `funds` missing if `"funds" not in state.me`
- `hand` missing if `"hand" not in state.me`
- Extend later via rule card without hardcoding game logic beyond these slot names

- [ ] **Step 2–4: Implement, test PASS, commit**

```bash
git commit -m "feat: StateParser with clarify-first critical slot checks"
```

---

### Task 9: LegalityChecker, Strategist, Critic

**Files:**
- Create: `src/board_game_agent/agents/legality.py`
- Create: `src/board_game_agent/agents/strategist.py`
- Create: `src/board_game_agent/agents/critic.py`
- Create: `tests/test_legality.py`
- Create: `tests/test_strategist.py`
- Create: `tests/test_critic.py`

- [ ] **Step 1: Failing tests with mocks**

Each agent:
- **LegalityChecker(llm)**: `check(candidates, state, card) -> list[LegalityReport]` via `chat_json`, `tier="fast"`
- **Strategist(llm)**: `propose(state, card, assumptions) -> list[CandidateAction]`, `tier="reasoning"`
- **Critic(llm)**: `finalize(candidates, legality, state, card) -> AdviceResult`, `tier="reasoning"`

Assert mock called with expected tier; validate pydantic parsing.

- [ ] **Step 2: Implement three modules with strict JSON schemas in prompts**

Prompts must state: optimize **current player only**; never invent hidden info; cite rule card actions.

- [ ] **Step 3: Tests PASS**

- [ ] **Step 4: Commit**

```bash
git commit -m "feat: legality, strategist, and critic agents"
```

---

### Task 10: Orchestrator pipeline

**Files:**
- Create: `src/board_game_agent/orchestrator.py`
- Create: `tests/test_orchestrator.py`

- [ ] **Step 1: Write failing tests**

```python
def test_say_with_missing_critical_does_not_call_strategist(mocker, tmp_sessions):
    # Wire SessionStore + mocked agents
    # say("阶段 play") → clarifications non-empty, strategist.propose not called


def test_advise_blocked_when_clarifications_pending(mocker, tmp_sessions):
    # pending clarifications → returns questions, no strategist


def test_advise_runs_full_pipeline_when_state_complete(mocker, tmp_sessions):
    # state has phase, active_seat, me.hand, me.funds
    # strategist → legality → critic called in order
```

- [ ] **Step 2: Implement `Orchestrator`**

Methods:
- `new_session(name) -> sid`
- `load_rules(sid, path)`
- `say(sid, text) -> str`  # NL response (questions or ack)
- `advise(sid) -> str`
- `ask(sid, text) -> str`  # rules Q&A using fast model + rule card/raw; no timeline write
- `status(sid) -> str`
- `undo(sid) -> str`
- `end(sid) -> str`

`say` flow:
1. StateParser.parse
2. append events; update assumptions file if any
3. reduce → write state
4. merge clarifications via `missing_critical`
5. if clarifications: return NL questions; **do not** strategist
6. if `settings.auto_advise_after_say`: run advise pipeline else return short ack (“局面已更新，输入 advise 获取建议”)

`advise` flow:
1. if `missing_critical`: return questions (policy A) — do not call strategist
2. else Strategist → Legality → Critic; save under `turns/<n>/`; append transcript; return `final_text`

- [ ] **Step 3: Tests PASS**

- [ ] **Step 4: Commit**

```bash
git commit -m "feat: orchestrator enforces clarify-then-advise pipeline"
```

---

### Task 11: CLI

**Files:**
- Create: `src/board_game_agent/cli.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Failing CLI tests via Typer's `CliRunner`**

Cover: `new`, `rules` (with toy fixture), `say`, `status`, `undo`, `advise` (mocked orchestrator or mocked LLM).

- [ ] **Step 2: Implement Typer app**

Commands matching spec: `new`, `use`, `rules`, `say`, `advise`, `ask`, `status`, `undo`, `end`.  
Global `--verbose` flag stores on context.

Wire `Settings()` + `LLMClient` + `Orchestrator` lazily so `--help` works without API key.

- [ ] **Step 3: `python -m board_game_agent --help` works**

- [ ] **Step 4: Commit**

```bash
git commit -m "feat: CLI for full-game Session commands"
```

---

### Task 12: Birmingham fixture stub + README for table play

**Files:**
- Create: `fixtures/birmingham/rules.md`
- Create: `fixtures/birmingham/scripts/opening_missing_hand.md`
- Modify: `README.md`

- [ ] **Step 1: Write `fixtures/birmingham/rules.md` as a short placeholder**

Do **not** paste a copyrighted full rulebook. Content = pointer:

```markdown
# Brass: Birmingham — 规则占位

请将你合法持有的规则整理为 Markdown 后替换本文件，或在 CLI 中：

  bga rules path/to/your_birmingham_rules.md

测试只依赖「存在可 ingest 的文本」；桌测请使用完整自备规则。
```

- [ ] **Step 2: Script checklist for human table test**

`opening_missing_hand.md`: steps — new session → rules → say phase only → expect clarification for hand/funds → say full private info → advise.

- [ ] **Step 3: Expand README**

Install, `.env` with DeepSeek key, toy game dry-run with mocks note, Birmingham table-play workflow, clarify-first behavior, disclaimer (player-perspective approximate advice).

- [ ] **Step 4: Commit**

```bash
git commit -m "docs: Birmingham fixture stub and table-play README"
```

---

### Task 13: End-to-end mocked smoke + verification

**Files:**
- Create: `tests/test_e2e_mocked.py`

- [ ] **Step 1: One mocked E2E**

`new` → ingest toy rules (mock) → `say` incomplete → assert clarification text → `say` complete slots → `advise` → assert critic final_text returned; timeline has ≥2 events; `undo` works.

- [ ] **Step 2: Run full suite**

Run: `pytest -v`  
Expected: all PASS (no real network)

- [ ] **Step 3: Commit**

```bash
git commit -m "test: mocked end-to-end Session smoke"
```

---

## Self-review checklist (plan author)

| Spec requirement | Task |
|------------------|------|
| Full-game Session + timeline | 4, 10 |
| NL in / NL out | 10, 11 |
| Five agents + orchestrator | 7–10 |
| Clarify-first (A) + critical_slots | 8, 10 |
| Player-perspective / out_of_view | 5, 9 |
| DeepSeek OpenAI-compatible | 2, 6 |
| CLI commands | 11 |
| Toy + Birmingham validation path | 7, 12, 13 |
| Undo / status / errors | 4, 10, 11 |
| No copyrighted full Brass rules in repo | 12 |

No TBD placeholders; types aligned on `Event`, `GameState`, `RuleCard`, `AdviceResult`, `LLMClient.chat` / `chat_json`, `Orchestrator.say` / `advise`.

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-09-29-board-game-agent.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks  
2. **Inline Execution** — this session with executing-plans and checkpoints  

Which approach?
