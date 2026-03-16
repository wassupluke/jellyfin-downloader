# Watches Page: Mobile Layout + Live Run Progress

**Date:** 2026-03-15
**Branch:** fix/mobile-layout

---

## Problem

1. On small screens the Edit/Run/Del action buttons in the Channel Watches table overflow the viewport.
2. Triggering a watch run gives no feedback — the page just reloads with a new Last Run timestamp after the job completes.

---

## Design

### 1. Mobile card layout

**Approach:** Two render paths in the same Jinja template, toggled by a CSS media query at ≤ 600 px.

- Desktop: existing `<table>` unchanged.
- Mobile: a `<div class="watch-cards">` list rendered from the same loop. Each card contains:
  - **Header row:** watch name (bold) + enabled/disabled badge
  - **Meta row:** date window, interval, last-run timestamp
  - **Button row:** Edit | Run | Del as `flex: 1` buttons spanning full card width

The table is `display: none` on mobile; the card list is `display: none` on desktop. No CSS table-to-block tricks needed.

The media query lives in a `{% block styles %}` in `watches.html`, not in `base.html`, so it does not affect other pages.

### 2. Live progress for watch runs

#### Backend

**`/watches/<id>/run` (POST)**

- Generates a UUID `job_id`.
- Creates a `_jobs[job_id]` entry (same schema as manual downloads: `status`, `progress`, `log`, `title`).
- Stores the `watch_id → job_id` mapping in a module-level dict `_watch_jobs`.
- Spawns a thread: `_run_watch(watch, job_id=job_id)`.
- Returns `{"job_id": "<uuid>"}` as JSON. No redirect.
- No CSRF token needed — the app has no CSRF middleware.

**`_run_watch(watch, job_id=None)`**

- Gains an optional `job_id` parameter.
- When `job_id` is provided, writes progress events to `_jobs[job_id]` (percent, current title, done/error) using the same helpers as manual downloads.
- Removes the entry from `_watch_jobs` in a `try/finally` block to guarantee cleanup even on an unhandled exception.
- The `_jobs[job_id]` entry is **not** removed after completion (matching existing manual download behavior). This means a client that connects to the SSE stream after the job has already finished will still receive the terminal `done`/`error` event and close cleanly, eliminating the race condition between page load and SSE connect.

**`GET /watches/running`**

- Returns `{watch_id: job_id, ...}` for all currently active watch jobs from `_watch_jobs`.
- Used by the page on load to reconnect SSE for any in-progress jobs.

The existing `GET /progress/<job_id>/stream` SSE endpoint requires no changes.

#### Frontend

**Run button (mobile card + desktop table)**

- Changed from `<form method="POST">` to a JS `fetch` call.
- On success: receives `{job_id}`, opens `EventSource('/progress/<job_id>/stream')`.
- While running: shows progress bar + current file/title below it (reusing existing progress bar markup from `index.html`), disables Edit/Run/Del.
- On SSE `done` or `error` event: re-enables buttons, updates Last Run text inline, closes stream.

**Page load reconnect**

- `watches.html` calls `GET /watches/running` on `DOMContentLoaded`.
- For each returned `{watch_id, job_id}`, reconnects SSE and activates the in-progress state on the relevant card.

---

## Files changed

| File                     | Change                                                                                                                                                                  |
| ------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `app.py`                 | Add `_watch_jobs` dict; update `/watches/<id>/run` to return JSON + create job; update `_run_watch` to emit progress via `try/finally`; add `/watches/running` endpoint |
| `templates/watches.html` | Add `.watch-cards` mobile markup; convert Run button to fetch; add progress bar markup + JS; add `{% block styles %}` with media query                                  |

---

## Out of scope

- Scheduler-triggered runs do not get progress tracking (daemon thread, no user watching).
- No changes to manual download flow.
- No changes to the watch edit/create form.
