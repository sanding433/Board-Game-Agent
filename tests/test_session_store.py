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
