(() => {
  const storyEl = document.getElementById("story");
  const storyBtn = document.getElementById("generate-story-btn");
  const storyErr = document.getElementById("story-gen-error");

  if (storyBtn && storyEl) {
    storyBtn.addEventListener("click", async () => {
      if (storyErr) {
        storyErr.hidden = true;
        storyErr.textContent = "";
      }
      storyBtn.disabled = true;
      try {
        const res = await fetch("/api/generate-story", {
          method: "POST",
          headers: { Accept: "application/json" },
        });
        const body = await res.json().catch(() => ({}));
        if (!res.ok) {
          const msg = body.detail || `Generate story failed (${res.status})`;
          if (storyErr) {
            storyErr.hidden = false;
            storyErr.textContent = msg;
          }
          return;
        }
        storyEl.value = body.story || "";
      } catch (err) {
        if (storyErr) {
          storyErr.hidden = false;
          storyErr.textContent = err.message || String(err);
        }
      } finally {
        storyBtn.disabled = false;
      }
    });
  }

  const form = document.getElementById("generate-form");
  if (!form) return;

  const pitchInput = document.getElementById("pitch");
  const speedInput = document.getElementById("speed");
  const videoSpeedInput = document.getElementById("video_speed");
  const pitchValue = document.getElementById("pitch-value");
  const speedValue = document.getElementById("speed-value");
  const videoSpeedValue = document.getElementById("video-speed-value");
  const videoSpeedField = document.getElementById("video-speed-field");

  function formatPitchLabel(n) {
    const v = Number(n);
    return (v > 0 ? "+" : "") + v + "%";
  }
  function formatSpeedLabel(n) {
    return Number(n) + "%";
  }
  function syncVoiceSliders() {
    if (pitchValue) pitchValue.textContent = formatPitchLabel(pitchInput.value);
    if (speedValue) speedValue.textContent = formatSpeedLabel(speedInput.value);
    if (videoSpeedValue && videoSpeedInput) {
      videoSpeedValue.textContent = formatSpeedLabel(videoSpeedInput.value);
    }
  }
  if (pitchInput && speedInput) {
    pitchInput.addEventListener("input", syncVoiceSliders);
    speedInput.addEventListener("input", syncVoiceSliders);
    if (videoSpeedInput) videoSpeedInput.addEventListener("input", syncVoiceSliders);
    syncVoiceSliders();
  }

  const generateBtn = document.getElementById("generate-btn");
  const modeTabs = [...form.querySelectorAll('[role="tab"][data-mode]')];
  const singleBlock = document.getElementById("single-source-block");
  const pictureBlock = document.getElementById("picture-source-block");
  const redditBlock = document.getElementById("reddit-source-block");
  const sourceSelect = document.getElementById("source_name");
  const imageSelect = document.getElementById("image_name");
  const kenBurnsEl = document.getElementById("ken_burns");
  const hasVideos = form.dataset.hasVideos === "true";
  let currentMode = "single";
  function imageSelectHasValue() {
    return Boolean(imageSelect && imageSelect.value);
  }
  function syncGenerateEnabled() {
    if (!generateBtn) return;
    if (currentMode === "picture") {
      generateBtn.disabled = !imageSelectHasValue();
    } else if (currentMode === "reddit") {
      generateBtn.disabled = !hasVideos;
    } else {
      generateBtn.disabled = !(sourceSelect && sourceSelect.value);
    }
  }
  const VIDEO_BOUNDS = {
    single: { min: 50, max: 200 },
    reddit: { min: 100, max: 500 },
  };
  function clampVideoSpeedForMode(mode) {
    if (!videoSpeedInput || mode === "picture") return;
    const b = VIDEO_BOUNDS[mode === "reddit" ? "reddit" : "single"];
    videoSpeedInput.min = String(b.min);
    videoSpeedInput.max = String(b.max);
    const v = Number(videoSpeedInput.value);
    if (v < b.min) videoSpeedInput.value = String(b.min);
    if (v > b.max) videoSpeedInput.value = String(b.max);
    syncVoiceSliders();
  }
  function setMode(mode) {
    currentMode = mode;
    const isPicture = mode === "picture";
    if (singleBlock) singleBlock.hidden = mode !== "single";
    if (pictureBlock) pictureBlock.hidden = !isPicture;
    if (redditBlock) redditBlock.hidden = mode !== "reddit";
    if (videoSpeedField) videoSpeedField.hidden = isPicture;
    for (const tab of modeTabs) {
      const selected = tab.dataset.mode === mode;
      tab.setAttribute("aria-selected", String(selected));
      tab.tabIndex = selected ? 0 : -1;
    }
    syncGenerateEnabled();
    clampVideoSpeedForMode(mode);
  }
  for (const tab of modeTabs) {
    tab.addEventListener("click", () => setMode(tab.dataset.mode));
    tab.addEventListener("keydown", (event) => {
      const currentIndex = modeTabs.indexOf(tab);
      let nextIndex;
      if (event.key === "ArrowRight") nextIndex = (currentIndex + 1) % modeTabs.length;
      if (event.key === "ArrowLeft") nextIndex = (currentIndex - 1 + modeTabs.length) % modeTabs.length;
      if (event.key === "Home") nextIndex = 0;
      if (event.key === "End") nextIndex = modeTabs.length - 1;
      if (nextIndex === undefined) return;
      event.preventDefault();
      const nextTab = modeTabs[nextIndex];
      setMode(nextTab.dataset.mode);
      nextTab.focus();
    });
  }
  if (sourceSelect) sourceSelect.addEventListener("change", syncGenerateEnabled);
  if (imageSelect) imageSelect.addEventListener("change", syncGenerateEnabled);
  syncGenerateEnabled();

  const statusEl = document.getElementById("status");
  const errorEl = document.getElementById("error");
  const resultEl = document.getElementById("result");
  const player = document.getElementById("player");
  const download = document.getElementById("download");
  const downloadCard = document.getElementById("download-card");

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

  function showResult(outputName, titleCardName) {
    const url = `/media/outputs/${encodeURIComponent(outputName)}`;
    resultEl.hidden = false;
    player.src = url;
    download.href = url;
    download.download = outputName;
    if (downloadCard) {
      if (titleCardName) {
        const cardUrl = `/media/outputs/${encodeURIComponent(titleCardName)}`;
        downloadCard.hidden = false;
        downloadCard.href = cardUrl;
        downloadCard.download = titleCardName;
      } else {
        downloadCard.hidden = true;
        downloadCard.removeAttribute("href");
        downloadCard.removeAttribute("download");
      }
    }
    prependRecentOutput(outputName);
  }

  function prependRecentOutput(outputName) {
    const section = document.querySelector(".recent-outputs");
    if (!section) return;
    let list = section.querySelector("ul.source-list");
    const empty = section.querySelector(":scope > p");
    if (!list) {
      if (empty) empty.remove();
      list = document.createElement("ul");
      list.className = "source-list";
      section.appendChild(list);
    }
    for (const li of [...list.querySelectorAll("li")]) {
      const label = li.querySelector("span");
      if (label && label.textContent === outputName) {
        li.remove();
      }
    }
    const li = document.createElement("li");
    const nameSpan = document.createElement("span");
    nameSpan.textContent = outputName;
    const meta = document.createElement("span");
    meta.className = "meta";
    meta.textContent = "new";
    const link = document.createElement("a");
    link.href = `/media/outputs/${encodeURIComponent(outputName)}`;
    link.textContent = "Play / download";
    li.append(nameSpan, meta, link);
    list.prepend(li);
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
      syncGenerateEnabled();
      if (job.output_name) {
        showResult(job.output_name, job.title_card_name || null);
      }
      return;
    }
    if (job.status === "error") {
      stopPolling();
      syncGenerateEnabled();
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
      mode: currentMode,
      source_name:
        currentMode === "picture"
          ? document.getElementById("image_name").value
          : currentMode === "single"
            ? document.getElementById("source_name").value
            : "",
      story: document.getElementById("story").value,
      voice: document.getElementById("voice").value,
      pitch: Number(document.getElementById("pitch").value),
      speed: Number(document.getElementById("speed").value),
      video_speed: Number(document.getElementById("video_speed").value),
      ken_burns:
        currentMode === "picture" &&
        Boolean(document.getElementById("ken_burns") && document.getElementById("ken_burns").checked),
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
        syncGenerateEnabled();
        setStatus("busy");
        showError(body.detail || "A job is already in progress");
        return;
      }
      if (!res.ok) {
        syncGenerateEnabled();
        setStatus("error");
        showError(body.detail || `Create failed (${res.status})`);
        return;
      }
      setStatus(body.status || "queued");
      pollTimer = setInterval(() => {
        pollJob(body.id).catch((err) => {
          stopPolling();
          syncGenerateEnabled();
          showError(err.message || String(err));
        });
      }, 1000);
      await pollJob(body.id);
    } catch (err) {
      syncGenerateEnabled();
      setStatus("error");
      showError(err.message || String(err));
    }
  });
})();
