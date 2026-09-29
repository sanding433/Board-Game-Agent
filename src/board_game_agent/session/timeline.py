from __future__ import annotations

from board_game_agent.models.schemas import Event
from board_game_agent.session.store import SessionStore


def append_event(store: SessionStore, sid: str, event: Event) -> None:
    path = store.path(sid) / "timeline.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write(event.model_dump_json() + "\n")


def read_events(store: SessionStore, sid: str) -> list[Event]:
    path = store.path(sid) / "timeline.jsonl"
    if not path.exists():
        return []
    events: list[Event] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            events.append(Event.model_validate_json(line))
    return events


def undo_last_user_event(store: SessionStore, sid: str) -> Event | None:
    events = read_events(store, sid)
    if not events:
        return None
    undone = events[-1]
    remaining = events[:-1]
    path = store.path(sid) / "timeline.jsonl"
    path.write_text(
        "".join(e.model_dump_json() + "\n" for e in remaining),
        encoding="utf-8",
    )
    return undone
