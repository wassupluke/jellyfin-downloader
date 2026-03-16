document.querySelectorAll(".local-time").forEach((el) => {
  const utc = el.dataset.utc;
  if (!utc) return;
  try {
    const d = new Date(
      utc.includes("T") || utc.includes("Z") ? utc : utc + "Z",
    );
    if (!isNaN(d)) el.textContent = d.toLocaleString();
  } catch (e) {}
});

const _openStreams = [];
window.addEventListener("beforeunload", () =>
  _openStreams.forEach((es) => es.close()),
);

function startWatchProgress(watchId, jobId) {
  document
    .querySelectorAll('.watch-progress[data-watch-id="' + watchId + '"]')
    .forEach((el) => (el.style.display = "block"));
  document
    .querySelectorAll('.run-btn[data-watch-id="' + watchId + '"]')
    .forEach((btn) => (btn.disabled = true));
  document
    .querySelectorAll('a.btn-blue[href*="/' + watchId + '/edit"]')
    .forEach((btn) => (btn.style.pointerEvents = "none"));

  const es = new EventSource("/progress/" + jobId + "/stream");
  _openStreams.push(es);
  es.onmessage = function (e) {
    const d = JSON.parse(e.data);
    const pct = Math.round(d.progress) + "%";
    document
      .querySelectorAll(
        '.watch-progress[data-watch-id="' + watchId + '"] .watch-prog-bar',
      )
      .forEach((bar) => {
        bar.style.width = pct;
        bar.textContent = pct;
        if (d.status === "error") bar.style.background = "#e53935";
      });
    document
      .querySelectorAll(
        '.watch-progress[data-watch-id="' + watchId + '"] .watch-prog-title',
      )
      .forEach((el) => {
        if (d.title) el.textContent = d.title;
      });
    if (d.status === "done" || d.status === "error") {
      es.close();
      _openStreams.splice(_openStreams.indexOf(es), 1);
      document
        .querySelectorAll('.run-btn[data-watch-id="' + watchId + '"]')
        .forEach((btn) => (btn.disabled = false));
      document
        .querySelectorAll('a.btn-blue[href*="/' + watchId + '/edit"]')
        .forEach((btn) => (btn.style.pointerEvents = ""));
      setTimeout(() => {
        document
          .querySelectorAll('.watch-progress[data-watch-id="' + watchId + '"]')
          .forEach((el) => (el.style.display = "none"));
      }, 2000);
    }
  };
  es.onerror = function () {
    es.close();
    _openStreams.splice(_openStreams.indexOf(es), 1);
    document
      .querySelectorAll('.run-btn[data-watch-id="' + watchId + '"]')
      .forEach((btn) => (btn.disabled = false));
  };
}

document.addEventListener("click", function (e) {
  const btn = e.target.closest(".run-btn");
  if (!btn) return;
  const watchId = btn.dataset.watchId;
  btn.disabled = true;
  fetch("/watches/" + watchId + "/run", { method: "POST" })
    .then((r) => r.json())
    .then((data) => startWatchProgress(watchId, data.job_id))
    .catch(() => {
      btn.disabled = false;
    });
});

document.addEventListener("DOMContentLoaded", function () {
  fetch("/watches/running")
    .then((r) => r.json())
    .then((running) => {
      Object.entries(running).forEach(([watchId, jobId]) =>
        startWatchProgress(watchId, jobId),
      );
    });
});
