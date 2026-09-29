from __future__ import annotations

from board_game_agent.models.schemas import Event, GameState


def reduce_events(events: list[Event]) -> GameState:
    state = GameState()
    for event in events:
        parsed = event.parsed or {}
        if "phase" in parsed and parsed["phase"] is not None:
            state.phase = str(parsed["phase"])
        if "active_seat" in parsed and parsed["active_seat"] is not None:
            state.active_seat = str(parsed["active_seat"])
        me = parsed.get("me")
        if isinstance(me, dict):
            state.me.update(me)
        public = parsed.get("public")
        if isinstance(public, dict):
            state.public.update(public)
        oov = parsed.get("out_of_view")
        if isinstance(oov, str) and oov:
            state.out_of_view_notes.append(oov)
        elif isinstance(oov, list):
            state.out_of_view_notes.extend(str(x) for x in oov if x)
        state.last_events.append(event.raw_text)
    state.last_events = state.last_events[-5:]
    return state
