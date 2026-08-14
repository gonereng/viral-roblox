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
  const pitchValue = document.getElementById("pitch-value");
  const speedValue = document.getElementById("speed-value");

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
  }
  if (pitchInput && speedInput) {
    pitchInput.addEventListener("input", syncVoiceSliders);
    speedInput.addEventListener("input", syncVoiceSliders);
    syncVoiceSliders();
  }

  const generateBtn = document.getElementById("generate-btn");
  const tabRoblox = document.getElementById("tab-roblox");
  const tabPicture = document.getElementById("tab-picture");
  const robloxBlock = document.getElementById("roblox-source-block");
  const pictureBlock = document.getElementById("picture-source-block");
  const sourceSelect = document.getElementById("source_name");
  const imageSelect = document.getElementById("image_name");
  const imageFile = document.getElementById("image-file");
  const imageUploadBtn = document.getElementById("image-upload-btn");
  const imageDeleteBtn = document.getElementById("image-delete-btn");
  const imageErr = document.getElementById("image-error");
  const kenBurnsEl = document.getElementById("ken_burns");
  let currentMode = "roblox";

  function showImageError(message) {
    if (!imageErr) return;
    imageErr.hidden = false;
    imageErr.textContent = message;
  }
  function clearImageError() {
    if (!imageErr) return;
    imageErr.hidden = true;
    imageErr.textContent = "";
  }
  function imageSelectHasValue() {
    return Boolean(imageSelect && imageSelect.value);
  }
  function syncGenerateEnabled() {
    if (!generateBtn) return;
    if (currentMode === "picture") {
      generateBtn.disabled = !imageSelectHasValue();
    } else {
      generateBtn.disabled = !(sourceSelect && sourceSelect.value);
    }
  }
  function setMode(mode) {
    currentMode = mode;
    const isPicture = mode === "picture";
    if (robloxBlock) robloxBlock.hidden = isPicture;
    if (pictureBlock) pictureBlock.hidden = !isPicture;
    if (tabRoblox) tabRoblox.setAttribute("aria-selected", isPicture ? "false" : "true");
    if (tabPicture) tabPicture.setAttribute("aria-selected", isPicture ? "true" : "false");
    syncGenerateEnabled();
  }
  if (tabRoblox) tabRoblox.addEventListener("click", () => setMode("roblox"));
  if (tabPicture) tabPicture.addEventListener("click", () => setMode("picture"));

  if (imageUploadBtn && imageFile && imageSelect) {
    imageUploadBtn.addEventListener("click", async () => {
      clearImageError();
      const file = imageFile.files && imageFile.files[0];
      if (!file) {
        showImageError("Choose an image file first");
        return;
      }
      const data = new FormData();
      data.append("file", file, file.name);
      imageUploadBtn.disabled = true;
      try {
        const res = await fetch("/api/images", {
          method: "POST",
          headers: { Accept: "application/json" },
          body: data,
        });
        const body = await res.json().catch(() => ({}));
        if (!res.ok) {
          showImageError(body.detail || `Upload failed (${res.status})`);
          return;
        }
        const empty = imageSelect.querySelector("option[disabled]");
        if (empty) empty.remove();
        const opt = document.createElement("option");
        opt.value = body.name;
        opt.textContent = body.name;
        imageSelect.append(opt);
        imageSelect.value = body.name;
        if (imageDeleteBtn) imageDeleteBtn.disabled = false;
        imageFile.value = "";
        syncGenerateEnabled();
      } catch (err) {
        showImageError(err.message || String(err));
      } finally {
        imageUploadBtn.disabled = false;
      }
    });
  }

  if (imageDeleteBtn && imageSelect) {
    imageDeleteBtn.addEventListener("click", async () => {
      clearImageError();
      const name = imageSelect.value;
      if (!name) return;
      imageDeleteBtn.disabled = true;
      try {
        const res = await fetch("/api/images/" + encodeURIComponent(name), {
          method: "DELETE",
          headers: { Accept: "application/json" },
        });
        const body = await res.json().catch(() => ({}));
        if (!res.ok) {
          showImageError(body.detail || `Delete failed (${res.status})`);
          imageDeleteBtn.disabled = false;
          return;
        }
        const opt = imageSelect.querySelector('option[value="' + CSS.escape(name) + '"]');
        if (opt) opt.remove();
        if (!imageSelect.options.length) {
          const placeholder = document.createElement("option");
          placeholder.value = "";
          placeholder.disabled = true;
          placeholder.selected = true;
          placeholder.textContent = "No images — upload below";
          imageSelect.append(placeholder);
          imageDeleteBtn.disabled = true;
        } else {
          imageSelect.selectedIndex = 0;
          imageDeleteBtn.disabled = false;
        }
        syncGenerateEnabled();
      } catch (err) {
        showImageError(err.message || String(err));
        imageDeleteBtn.disabled = false;
      }
    });
  }

  const statusEl = document.getElementById("status");
  const errorEl = document.getElementById("error");
  const resultEl = document.getElementById("result");
  const player = document.getElementById("player");
  const download = document.getElementById("download");

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
      mode: currentMode,
      source_name:
        currentMode === "picture"
          ? document.getElementById("image_name").value
          : document.getElementById("source_name").value,
      story: document.getElementById("story").value,
      voice: document.getElementById("voice").value,
      pitch: Number(document.getElementById("pitch").value),
      speed: Number(document.getElementById("speed").value),
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
        generateBtn.disabled = false;
        setStatus("busy");
        showError(body.detail || "A job is already in progress");
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
