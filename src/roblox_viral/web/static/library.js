(() => {
  const form = document.getElementById("youtube-form");
  if (!form) return;

  const statusEl = document.getElementById("yt-status");
  const errorEl = document.getElementById("yt-error");
  const messageEl = document.getElementById("yt-message");
  const btn = document.getElementById("youtube-btn");
  let pollTimer = null;

  function setStatus(t) {
    statusEl.textContent = t;
  }
  function showError(msg) {
    errorEl.hidden = false;
    errorEl.textContent = msg;
    messageEl.hidden = true;
  }
  function showMessage(msg) {
    messageEl.hidden = false;
    messageEl.textContent = msg;
    errorEl.hidden = true;
  }
  function clearFeedback() {
    errorEl.hidden = true;
    errorEl.textContent = "";
    messageEl.hidden = true;
    messageEl.textContent = "";
  }
  function stopPolling() {
    if (pollTimer !== null) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  }

  async function pollJob(jobId) {
    const res = await fetch(`/api/jobs/${encodeURIComponent(jobId)}`, {
      headers: { Accept: "application/json" },
    });
    if (!res.ok) throw new Error(`Status request failed (${res.status})`);
    const job = await res.json();
    setStatus(job.status);
    if (job.status === "done") {
      stopPolling();
      btn.disabled = false;
      const slices = (job.created_slices || []).join(", ");
      showMessage(slices ? `Created: ${slices}` : "Import complete.");
      window.setTimeout(() => window.location.reload(), 800);
      return;
    }
    if (job.status === "error") {
      stopPolling();
      btn.disabled = false;
      showError(job.error || "Import failed");
    }
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearFeedback();
    stopPolling();
    btn.disabled = true;
    setStatus("starting");
    try {
      const res = await fetch("/api/library/youtube", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify({
          url: document.getElementById("youtube_url").value,
          name: document.getElementById("youtube_name").value,
        }),
      });
      const body = await res.json().catch(() => ({}));
      if (res.status === 409) {
        btn.disabled = false;
        setStatus("busy");
        showError(body.detail || "A job is already in progress");
        return;
      }
      if (!res.ok) {
        btn.disabled = false;
        setStatus("error");
        showError(body.detail || `Import failed (${res.status})`);
        return;
      }
      setStatus(body.status || "queued");
      pollTimer = setInterval(() => {
        pollJob(body.id).catch((err) => {
          stopPolling();
          btn.disabled = false;
          showError(err.message || String(err));
        });
      }, 1000);
      await pollJob(body.id);
    } catch (err) {
      btn.disabled = false;
      setStatus("error");
      showError(err.message || String(err));
    }
  });
})();
