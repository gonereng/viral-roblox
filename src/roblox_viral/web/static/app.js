(() => {
  const form = document.getElementById("generate-form");
  if (!form) return;

  const statusEl = document.getElementById("status");
  const errorEl = document.getElementById("error");
  const resultEl = document.getElementById("result");
  const player = document.getElementById("player");
  const download = document.getElementById("download");
  const generateBtn = document.getElementById("generate-btn");

  let pollTimer = null;

  function setStatus(text) {
    statusEl.textContent = text;
  }

  function showError(message) {
    errorEl.hidden = false;
    errorEl.textContent = message;
  }

  function clearError() {
    errorEl.hidden = true;
    errorEl.textContent = "";
  }

  function stopPolling() {
    if (pollTimer !== null) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  }

  function showResult(outputName) {
    const url = `/media/outputs/${encodeURIComponent(outputName)}`;
    resultEl.hidden = false;
    player.src = url;
    download.href = url;
    download.download = outputName;
  }

  async function pollJob(jobId) {
    const res = await fetch(`/api/jobs/${encodeURIComponent(jobId)}`, {
      headers: { Accept: "application/json" },
    });
    if (!res.ok) {
      throw new Error(`Status request failed (${res.status})`);
    }
    const job = await res.json();
    setStatus(job.status);
    if (job.status === "done") {
      stopPolling();
      generateBtn.disabled = false;
      if (job.output_name) {
        showResult(job.output_name);
      }
      return;
    }
    if (job.status === "error") {
      stopPolling();
      generateBtn.disabled = false;
      showError(job.error || "Render failed");
    }
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearError();
    resultEl.hidden = true;
    player.removeAttribute("src");
    stopPolling();

    const payload = {
      source_name: document.getElementById("source_name").value,
      story: document.getElementById("story").value,
      voice: document.getElementById("voice").value,
    };

    generateBtn.disabled = true;
    setStatus("starting");

    try {
      const res = await fetch("/api/jobs", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify(payload),
      });
      const body = await res.json().catch(() => ({}));
      if (res.status === 409) {
        generateBtn.disabled = false;
        setStatus("busy");
        showError(body.detail || "A render job is already in progress");
        return;
      }
      if (!res.ok) {
        generateBtn.disabled = false;
        setStatus("error");
        showError(body.detail || `Create failed (${res.status})`);
        return;
      }
      setStatus(body.status || "queued");
      pollTimer = setInterval(() => {
        pollJob(body.id).catch((err) => {
          stopPolling();
          generateBtn.disabled = false;
          showError(err.message || String(err));
        });
      }, 1000);
      await pollJob(body.id);
    } catch (err) {
      generateBtn.disabled = false;
      setStatus("error");
      showError(err.message || String(err));
    }
  });
})();
