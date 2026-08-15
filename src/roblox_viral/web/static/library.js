(() => {
  const tabs = [...document.querySelectorAll('[role="tab"]')];

  function selectTab(selected, moveFocus = false) {
    for (const tab of tabs) {
      const active = tab === selected;
      tab.setAttribute("aria-selected", String(active));
      tab.tabIndex = active ? 0 : -1;
      document.getElementById(tab.getAttribute("aria-controls")).hidden = !active;
    }
    if (moveFocus) selected.focus();
  }

  for (const tab of tabs) {
    tab.addEventListener("click", () => selectTab(tab));
    tab.addEventListener("keydown", (event) => {
      if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
      event.preventDefault();
      const current = tabs.indexOf(tab);
      const next =
        event.key === "Home" ? 0 :
        event.key === "End" ? tabs.length - 1 :
        event.key === "ArrowRight" ? (current + 1) % tabs.length :
        (current - 1 + tabs.length) % tabs.length;
      selectTab(tabs[next], true);
    });
  }

  const status = document.getElementById("image-status");
  const uploadForm = document.getElementById("image-upload-form");

  async function responseError(response) {
    try {
      const body = await response.json();
      return body.detail || "Request failed.";
    } catch {
      return "Request failed.";
    }
  }

  uploadForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = uploadForm.querySelector('button[type="submit"]');
    button.disabled = true;
    status.textContent = "Uploading image…";
    try {
      const response = await fetch("/api/images", {
        method: "POST",
        body: new FormData(uploadForm),
      });
      if (!response.ok) throw new Error(await responseError(response));
      window.location.assign("/library?tab=images");
    } catch (error) {
      status.textContent = error instanceof Error ? error.message : "Request failed.";
      button.disabled = false;
    }
  });

  for (const button of document.querySelectorAll(".image-delete")) {
    button.addEventListener("click", async () => {
      button.disabled = true;
      status.textContent = `Deleting ${button.dataset.name}…`;
      try {
        const response = await fetch(
          `/api/images/${encodeURIComponent(button.dataset.name)}`,
          { method: "DELETE" },
        );
        if (!response.ok) throw new Error(await responseError(response));
        window.location.assign("/library?tab=images");
      } catch (error) {
        status.textContent = error instanceof Error ? error.message : "Request failed.";
        button.disabled = false;
      }
    });
  }
})();
