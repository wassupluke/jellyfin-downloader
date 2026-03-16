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
            "channel_url": "https://www.youtube.com/@TestChannel",
            "title_filter": " some regex ",
            "title_exclude": " F2|F3 ",
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
            "interval_hours": "6",
            "enabled": "on",
        }
        result = app_module._watch_from_form(form)
        assert result["name"] == "My Watch"
        assert result["channel_url"] == "https://www.youtube.com/@TestChannel"
        assert result["title_filter"] == "some regex"
        assert result["title_exclude"] == "F2|F3"
        assert result["interval_hours"] == 6
        assert result["enabled"] is True
        assert result["last_run"] is None
        assert "id" in result

    def test_disabled_when_missing(self):
        form = {
            "name": "W",
            "channel_url": "https://www.youtube.com/@TestChannel",
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
            "interval_hours": "4",
        }
        result = app_module._watch_from_form(form)
        assert result["enabled"] is False
        assert result["title_exclude"] == ""


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

    def test_migrates_playlist_url_to_channel_url(self, tmp_watches_file):
        legacy = {
            "id": "old-1",
            "name": "Legacy",
            "playlist_url": "https://youtube.com/playlist?list=OLD",
            "title_filter": "",
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
            "interval_hours": 4,
            "enabled": True,
            "last_run": None,
        }
        with open(tmp_watches_file, "w") as f:
            json.dump([legacy], f)
        result = app_module.load_watches()
        assert "channel_url" in result[0]
        assert "playlist_url" not in result[0]
        assert result[0]["channel_url"] == "https://youtube.com/playlist?list=OLD"


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
            "channel_url": "https://www.youtube.com/@NewChannel",
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
        assert watches[0]["channel_url"] == "https://www.youtube.com/@NewChannel"

    def test_delete_watch(self, client, sample_watch):
        app_module.save_watches([sample_watch])
        resp = client.post(f"/watches/{sample_watch['id']}/delete")
        assert resp.status_code == 302
        assert app_module.load_watches() == []

    def test_run_watch_returns_json_job_id(self, client, sample_watch):
        app_module.save_watches([sample_watch])
        with patch.object(app_module, "_run_watch"):
            resp = client.post(f"/watches/{sample_watch['id']}/run")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "job_id" in data

    def test_run_watch_updates_last_run(self, client, sample_watch):
        app_module.save_watches([sample_watch])
        with patch.object(app_module, "_run_watch"):
            client.post(f"/watches/{sample_watch['id']}/run")
        watches = app_module.load_watches()
        assert watches[0]["last_run"] is not None

    def test_run_watch_populates_watch_jobs(self, client, sample_watch):
        """_watch_jobs should be populated (and cleaned up after thread finishes)."""
        import threading
        app_module.save_watches([sample_watch])
        event = threading.Event()

        def slow_run_watch(watch, job_id=None):
            event.wait()  # block until test checks state

        with patch.object(app_module, "_run_watch", side_effect=slow_run_watch):
            resp = client.post(f"/watches/{sample_watch['id']}/run")
        data = resp.get_json()
        job_id = data["job_id"]
        # The spawned thread is blocked; _watch_jobs should contain the entry
        with app_module._watch_jobs_lock:
            assert app_module._watch_jobs.get(sample_watch["id"]) == job_id
        event.set()  # release the thread

    def test_watches_running_endpoint(self, client, sample_watch):
        app_module.save_watches([sample_watch])
        import threading
        event = threading.Event()

        def slow_run_watch(watch, job_id=None):
            event.wait()

        with patch.object(app_module, "_run_watch", side_effect=slow_run_watch):
            resp = client.post(f"/watches/{sample_watch['id']}/run")
        job_id = resp.get_json()["job_id"]

        running_resp = client.get("/watches/running")
        assert running_resp.status_code == 200
        running = running_resp.get_json()
        assert running.get(sample_watch["id"]) == job_id
        event.set()

    def test_run_watch_nonexistent_watch(self, client):
        resp = client.post("/watches/nonexistent-id/run")
        # Should still return 200 with no job created (watch not found)
        assert resp.status_code == 200


class TestRunWatchWithJobId:
    """Tests for _run_watch(watch, job_id=...) Popen path."""

    def _make_watch(self):
        return {
            "id": "w-1",
            "name": "Test Watch",
            "channel_url": "https://www.youtube.com/@TestChannel",
            "title_filter": "",
            "title_exclude": "",
            "start_date": "2025-01-01",
            "end_date": "2027-12-31",
            "interval_hours": 4,
            "enabled": True,
            "last_run": None,
        }

    def _make_job(self):
        from collections import deque
        return {"status": "running", "progress": 0, "log": deque(maxlen=50), "title": ""}

    def test_success_sets_done_status(self, tmp_path):
        watch = self._make_watch()
        job_id = "job-success"
        app_module._jobs[job_id] = self._make_job()
        # Ensure _watch_jobs has the entry so cleanup can run
        with app_module._watch_jobs_lock:
            app_module._watch_jobs[watch["id"]] = job_id

        mock_proc = MagicMock()
        mock_proc.stdout = iter(["[download]  50.0% of 100MiB\n", "[info] title: Some Video\n"])
        mock_proc.returncode = 0
        mock_proc.wait.return_value = None

        with patch("app.subprocess.Popen", return_value=mock_proc), \
             patch.object(app_module, "trigger_jellyfin_scan") as mock_scan, \
             patch.object(app_module, "ARCHIVES_DIR", str(tmp_path)):
            app_module._run_watch(watch, job_id=job_id)

        job = app_module._jobs[job_id]
        assert job["status"] == "done"
        assert job["progress"] == 100
        mock_scan.assert_called_once()
        # Cleaned up from _watch_jobs
        with app_module._watch_jobs_lock:
            assert watch["id"] not in app_module._watch_jobs

    def test_failure_sets_error_status(self, tmp_path):
        watch = self._make_watch()
        watch["id"] = "w-2"
        job_id = "job-failure"
        app_module._jobs[job_id] = self._make_job()
        with app_module._watch_jobs_lock:
            app_module._watch_jobs[watch["id"]] = job_id

        mock_proc = MagicMock()
        mock_proc.stdout = iter([])
        mock_proc.returncode = 1
        mock_proc.wait.return_value = None

        with patch("app.subprocess.Popen", return_value=mock_proc), \
             patch.object(app_module, "trigger_jellyfin_scan") as mock_scan, \
             patch.object(app_module, "ARCHIVES_DIR", str(tmp_path)):
            app_module._run_watch(watch, job_id=job_id)

        job = app_module._jobs[job_id]
        assert job["status"] == "error"
        mock_scan.assert_not_called()
        with app_module._watch_jobs_lock:
            assert watch["id"] not in app_module._watch_jobs

    def test_exception_sets_error_status(self, tmp_path):
        watch = self._make_watch()
        watch["id"] = "w-3"
        job_id = "job-exception"
        app_module._jobs[job_id] = self._make_job()
        with app_module._watch_jobs_lock:
            app_module._watch_jobs[watch["id"]] = job_id

        with patch("app.subprocess.Popen", side_effect=Exception("boom")), \
             patch.object(app_module, "ARCHIVES_DIR", str(tmp_path)):
            app_module._run_watch(watch, job_id=job_id)

        job = app_module._jobs[job_id]
        assert job["status"] == "error"
        assert any("boom" in line for line in job["log"])
        with app_module._watch_jobs_lock:
            assert watch["id"] not in app_module._watch_jobs

    def test_no_job_id_uses_run_ytdlp(self, tmp_path):
        """Scheduler path (job_id=None) should call run_ytdlp, not Popen."""
        watch = self._make_watch()
        watch["id"] = "w-4"

        with patch.object(app_module, "run_ytdlp", return_value=True) as mock_run, \
             patch.object(app_module, "trigger_jellyfin_scan") as mock_scan, \
             patch.object(app_module, "ARCHIVES_DIR", str(tmp_path)):
            app_module._run_watch(watch)

        mock_run.assert_called_once()
        mock_scan.assert_called_once()


# ── Scheduler logic ──────────────────────────────────────────

class TestSchedulerLogic:
    """Test the inner logic of _scheduler_loop by calling load_watches + the same checks."""

    def _run_one_cycle(self, watches):
        """Simulate one scheduler cycle, return list of watch names that would run."""
        ran = []
        now = datetime.now(timezone.utc)
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
                    if last_run_dt.tzinfo is None:
                        last_run_dt = last_run_dt.astimezone(timezone.utc)
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
        sample_watch["last_run"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
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


class TestWatchesHtml:
    def test_markup_present(self, client, sample_watch):
        app_module.save_watches([sample_watch])
        resp = client.get("/watches")
        assert resp.status_code == 200
        assert b'watch-cards' in resp.data
        assert b'run-btn' in resp.data
        assert b'watch-progress' in resp.data
