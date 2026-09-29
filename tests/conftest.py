import pytest
from pathlib import Path


@pytest.fixture
def tmp_sessions(tmp_path: Path) -> Path:
    d = tmp_path / "sessions"
    d.mkdir()
    return d
