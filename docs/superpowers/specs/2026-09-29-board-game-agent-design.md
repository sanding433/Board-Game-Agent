# Board Game Advisor Agent — Design Spec

**Date:** 2026-09-29  
**Status:** Approved for implementation planning  
**Primary validation game:** Brass: Birmingham  
**Interface (MVP):** Local CLI

## Goal

Build a **multi-agent, multi-game** advisor that helps one seated player play a full offline (or digital) game session.

- Input: natural language only (rules as Markdown/text; all observable game info as chat).
- Output: natural language action advice, clarifications, and short rationale.
- Objective: **approximate best play from that player's perspective** given information they can legally know — not global omniscient optimality.
- Games are not hard-coded: the user uploads rules; agents digest them. Brass: Birmingham is the first real-table validation target. Puzzle-style modes are deferred.

## Non-goals (MVP)

- Camera / image board recognition
- Hard-coded Brass rules engine or perfect legality prover
- Web UI, Discord, etc.
- Full game-tree solver or multiplayer ELO ranking
- Puzzle exhaustive search mode
- PDF/image rulebook ingest (text/Markdown only)

## Product shape: one full game = one Session

A Session lasts from setup through end of a real playthrough.

1. User creates a Session and uploads a rules Markdown file.
2. Throughout the game, the user narrates everything knowable from their seat: hand, money, public board, others' revealed actions, phase changes, etc.
3. The system asks clarifying questions when critical slots are missing (policy **A**: clarify before advising).
4. When information is sufficient, it returns player-perspective action advice in natural language.
5. The user reports what actually happened (including other players' moves); the Session timeline advances.

Internal structured artifacts exist for multi-agent collaboration and debugging; users never have to edit JSON.

## Architecture

### Stack (recommended)

- Python 3.11+
- OpenAI-compatible chat API (model configurable via `.env`)
- Lightweight custom orchestrator (deterministic state machine). Migrate to LangGraph later only if orchestration complexity warrants it.
- Session files on disk under `sessions/<id>/`

### Agents

| Agent | Role |
|-------|------|
| **RuleIngestor** | Digest uploaded rules into a reusable rule card (phases, action catalog, scoring, constraints, ambiguity notes). |
| **StateParser** | Turn user natural language into timeline Events; reduce to `state/current.json`; emit clarification questions when critical info is missing. |
| **LegalityChecker** | Check candidate actions against the rule card + current state; flag illegal proposals with rule-grounded reasons. |
| **Strategist** | Propose 1–3 candidate actions optimizing **only the current player's** expected outcome under stated assumptions. |
| **Critic** | Adversarial pass: catch illegal moves, missed scoring, short-sightedness; emit final natural-language advice. |

**Orchestrator** (mostly non-LLM): owns Session lifecycle, command routing, agent order, and persistence.

### Agent pipeline (one advice beat)

```
User NL
  → StateParser → Event(s) and/or Clarifications
  → (if clarifications pending: stop and ask; do not run Strategist)
  → Strategist → candidates
  → LegalityChecker → filter / annotate
  → Critic → final NL advice
  → persist transcript + turn artifacts
```

## Session layout

```
sessions/<id>/
  meta.json              # game label, seat, created_at, phase summary
  rules/raw.md           # user-uploaded text
  rules/card.json        # ingested rule card
  timeline.jsonl         # append-only event log (one JSON object per line)
  state/current.json     # reduction of timeline; player-visible only
  assumptions.md         # explicit hypotheses (never silent omniscience)
  turns/<n>/             # optional per-advise working files
  transcript.md          # human-readable dialogue excerpt for table postmortem
```

### Intermediate schemas (logical)

**Event:** `type` (`setup` | `public_action` | `private_info` | `phase_change` | `resolve` | `correction`), `raw_text`, `parsed`, `visibility` (`private` | `public`), `timestamp`.

**State:** `phase`, `active_seat`, `me` (private info), `public` (shared board), `last_events`, `pending_clarifications`.

**Rule card:** phase machine summary, legal action catalog, scoring/end conditions, listed ambiguities for ingest QA, and `critical_slots` (fields that must be known before advice under policy A — e.g. hand, funds, phase, active seat).

### Player-perspective constraint

`state/current.json` must not treat information the current player should not know as hard fact. If the user supplies out-of-view info, mark it `out_of_view` or move it into `assumptions.md`, and do not use it as certainty unless the user confirms “play under this hypothesis.”

## CLI

| Command | Behavior |
|---------|----------|
| `new [--name NAME]` | Create Session; print id |
| `use <id>` | Switch current Session |
| `rules <path>` | Load/replace rules; run RuleIngestor |
| `say <text>` | Main input: narrate observables / actions |
| `advise` | Force Strategist→Legality→Critic even if thin info (still list assumptions); normal path after `say` still prefers clarify-first when critical slots missing |
| `ask <text>` | Rules Q&A without mutating timeline (by default) |
| `status` | Phase, seat, recent events, pending questions, assumptions |
| `undo` | Drop last user Event |
| `end` | Close Session; keep files for replay |

Config (`.env`): API key/base URL, model, reply language (default Chinese), optional `auto_advise_after_say` (default off while clarify-first is strict — after clarifications resolved, user runs `advise` or enables auto).

Verbose flag: `--verbose` prints paths to JSON artifacts and candidate/legality summaries; default UX is NL only.

## Clarification policy (A)

If critical slots for a legal recommendation are missing (e.g. hand contents, funds, whose turn, current phase for Brass), **ask before advising**. Do not invent private state.

Non-critical gaps may be listed as assumptions only when the user explicitly runs `advise` and accepts assumption-tagged output — still preferred to ask when the gap blocks legality.

## Error handling

| Case | Response |
|------|----------|
| No Session / no rules | Refuse with next-step hint |
| Ingest failure | Keep `raw.md`; report failing sections; allow re-`rules` |
| Contradictory narration | Surface conflict; block or mark `conflict`; user `undo` / corrects via `say` |
| All candidates illegal | Explain; ask for correction or safer legal options |
| Model/API failure | Retry once; preserve Session; suggest later `advise` |
| Empty / oversized input | Reject; ask to split |

## Validation strategy

### Automated

- Session/timeline/undo/status file invariants
- State reduction unit tests with fixture Events
- Visibility tests (hidden info must not become hard state)
- Agent I/O schema checks with mocked LLM
- CLI smoke tests without network

### Fixtures

- `fixtures/birmingham/rules.md` plus short scripted beats (opening, mid-game public update, missing-info must clarify)

### Human / table play (primary quality bar)

Owner plays Brass: Birmingham (and later other games) offline with friends:

1. Narrate seat-visible info and public actions into the CLI.
2. Answer agent clarifications; take or adapt advice at the table.
3. After the game, review `transcript.md` + `timeline.jsonl`; note good/bad advice and rules misunderstandings.

Success for MVP:

- New game playable after uploading rules text, no code change
- Clarify-first behavior is reliable on missing critical info
- Advice is actionable and rule-plausible in real Brass sessions
- Full Session survives a multi-hour table game without corruption
- System honestly frames output as player-perspective approximate best play

## Future extensions (out of MVP scope)

- Puzzle / solitaire “search for a solution” mode on the same Session skeleton
- PDF/image rules and board vision
- LangGraph migration if graphs get complex
- Web UI on top of the same Session store

## Design decisions log

- Modern euro-style games first; Brass: Birmingham as validation sample
- Multi-agent pipeline over single-shot RAG or free-form orchestrator
- NL in / NL out; structured state only internal
- Full-game Session with timeline, not one-shot position tool
- Clarify-before-advise (policy A)
- CLI first; Python + light custom orchestration
