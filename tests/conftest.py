import json
import pytest
import app as app_module


@pytest.fixture
def client(tmp_path):
    watches_file = str(tmp_path / "watches.json")
    with (
        pytest.MonkeyPatch.context() as mp,
    ):
        mp.setattr(app_module, "WATCHES_FILE", watches_file)
        mp.setattr(app_module, "ARCHIVES_DIR", str(tmp_path / "archives"))
        app_module.app.config["TESTING"] = True
        with app_module.app.test_client() as c:
            yield c


@pytest.fixture
def tmp_watches_file(tmp_path):
    path = str(tmp_path / "watches.json")
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(app_module, "WATCHES_FILE", path)
        yield path


@pytest.fixture
def sample_watch():
    return {
        "id": "test-id-123",
        "name": "Test Watch",
        "playlist_url": "https://youtube.com/playlist?list=TEST",
        "title_filter": "test.*",
        "start_date": "2025-01-01",
        "end_date": "2027-12-31",
        "interval_hours": 4,
        "enabled": True,
        "last_run": None,
    }
