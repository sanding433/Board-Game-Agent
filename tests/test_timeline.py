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
