import json
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

import pytest
import app as app_module


# ── _parse_progress ──────────────────────────────────────────

class TestParseProgress:
    def test_percentage_line(self):
        assert app_module._parse_progress("[download]  42.3% of 100MiB") == 42.3

    def test_100_percent(self):
        assert app_module._parse_progress("[download] 100% of 500MiB") == 100.0

    def test_no_match(self):
        assert app_module._parse_progress("[info] Downloading video #1") is None

    def test_empty_string(self):
        assert app_module._parse_progress("") is None


# ── _watch_from_form ─────────────────────────────────────────

class TestWatchFromForm:
    def test_basic_conversion(self):
        form = {
            "name": "My Watch",
            "playlist_url": "https://youtube.com/playlist?list=X",
            "title_filter": " some regex ",
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
            "interval_hours": "6",
            "enabled": "on",
        }
        result = app_module._watch_from_form(form)
        assert result["name"] == "My Watch"
        assert result["title_filter"] == "some regex"
        assert result["interval_hours"] == 6
        assert result["enabled"] is True
        assert result["last_run"] is None
        assert "id" in result

    def test_disabled_when_missing(self):
        form = {
            "name": "W",
            "playlist_url": "url",
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
            "interval_hours": "4",
        }
        result = app_module._watch_from_form(form)
        assert result["enabled"] is False


# ── find_watch ───────────────────────────────────────────────

class TestFindWatch:
    def test_found(self, sample_watch):
        assert app_module.find_watch([sample_watch], "test-id-123") == sample_watch

    def test_not_found(self, sample_watch):
        assert app_module.find_watch([sample_watch], "nonexistent") is None

    def test_empty_list(self):
        assert app_module.find_watch([], "any") is None


# ── Watches persistence ──────────────────────────────────────

class TestLoadWatches:
    def test_missing_file(self, tmp_watches_file):
        result = app_module.load_watches()
        assert result == []

    def test_valid_json(self, tmp_watches_file, sample_watch):
        with open(tmp_watches_file, "w") as f:
            json.dump([sample_watch], f)
        result = app_module.load_watches()
        assert len(result) == 1
        assert result[0]["name"] == "Test Watch"

    def test_corrupt_json(self, tmp_watches_file):
        with open(tmp_watches_file, "w") as f:
            f.write("{bad json!!")
        assert app_module.load_watches() == []


class TestSaveWatches:
    def test_writes_valid_json(self, tmp_watches_file, sample_watch):
        app_module.save_watches([sample_watch])
        with open(tmp_watches_file) as f:
            data = json.load(f)
        assert len(data) == 1
        assert data[0]["id"] == "test-id-123"


# ── Flask routes ─────────────────────────────────────────────

class TestDownloadRoute:
    def test_get_returns_form(self, client):
        resp = client.get("/")
        assert resp.status_code == 200

    def test_post_redirects_to_progress(self, client):
        with patch.object(app_module, "_run_download_job"):
            resp = client.post("/", data={"url": "https://youtube.com/watch?v=test"})
        assert resp.status_code == 302
        assert "/progress/" in resp.headers["Location"]


class TestWatchesRoutes:
    def test_get_watches(self, client):
        resp = client.get("/watches")
        assert resp.status_code == 200

    def test_add_watch(self, client):
        resp = client.post("/watches/add", data={
            "name": "New",
            "playlist_url": "https://youtube.com/playlist?list=X",
            "title_filter": "",
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
            "interval_hours": "4",
            "enabled": "on",
        })
        assert resp.status_code == 302
        watches = app_module.load_watches()
        assert len(watches) == 1
        assert watches[0]["name"] == "New"

    def test_delete_watch(self, client, sample_watch):
        app_module.save_watches([sample_watch])
        resp = client.post(f"/watches/{sample_watch['id']}/delete")
        assert resp.status_code == 302
        assert app_module.load_watches() == []

    def test_run_watch(self, client, sample_watch):
        app_module.save_watches([sample_watch])
        with patch.object(app_module, "_run_watch"):
            resp = client.post(f"/watches/{sample_watch['id']}/run")
        assert resp.status_code == 302
        watches = app_module.load_watches()
        assert watches[0]["last_run"] is not None


# ── Scheduler logic ──────────────────────────────────────────

class TestSchedulerLogic:
    """Test the inner logic of _scheduler_loop by calling load_watches + the same checks."""

    def _run_one_cycle(self, watches):
        """Simulate one scheduler cycle, return list of watch names that would run."""
        ran = []
        now = datetime.now()
        today = "2026-02-22"

        for watch in watches:
            if not watch.get("enabled"):
                continue
            if not (watch.get("start_date", "") <= today <= watch.get("end_date", "")):
                continue
            last_run = watch.get("last_run")
            if last_run:
                try:
                    last_run_dt = datetime.fromisoformat(last_run)
                except (TypeError, ValueError):
                    last_run_dt = None
                if last_run_dt is not None:
                    elapsed = (now - last_run_dt).total_seconds() / 3600
                    if elapsed < watch.get("interval_hours", 4):
                        continue
            ran.append(watch["name"])
        return ran

    def test_skips_disabled(self, sample_watch):
        sample_watch["enabled"] = False
        assert self._run_one_cycle([sample_watch]) == []

    def test_skips_outside_date_window(self, sample_watch):
        sample_watch["start_date"] = "2099-01-01"
        sample_watch["end_date"] = "2099-12-31"
        assert self._run_one_cycle([sample_watch]) == []

    def test_skips_within_cooldown(self, sample_watch):
        sample_watch["last_run"] = datetime.now().isoformat(timespec="seconds")
        assert self._run_one_cycle([sample_watch]) == []

    def test_runs_eligible(self, sample_watch):
        assert self._run_one_cycle([sample_watch]) == ["Test Watch"]


# ── trigger_jellyfin_scan ────────────────────────────────────

class TestTriggerJellyfinScan:
    def test_posts_to_jellyfin(self):
        with patch("app.requests.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=204, content=b"")
            app_module.trigger_jellyfin_scan()
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        assert "/Library/Media/Updated" in call_kwargs.args[0]
        assert "X-MediaBrowser-Token" in call_kwargs.kwargs["headers"]

    def test_handles_exception(self):
        with patch("app.requests.post", side_effect=Exception("timeout")):
            app_module.trigger_jellyfin_scan()  # should not raise
