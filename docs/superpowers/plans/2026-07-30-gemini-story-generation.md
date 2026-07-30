# Gemini Story Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Prompt page for an editable persistent Gemini prompt, and a Generate-page button that calls Gemini and fills the story textarea.

**Architecture:** Persist the prompt at `MEDIA_ROOT/prompt.txt`. Call Gemini `generateContent` over REST with `httpx` and `GEMINI_API_KEY`. Keep story generation separate from the video job pipeline — the button only fills `#story`.

**Tech Stack:** Python 3.10+, FastAPI, Jinja2, httpx, pytest, Gemini REST (`generativelanguage.googleapis.com`)

## Global Constraints

- Prompt file: `{MEDIA_ROOT}/prompt.txt` (not in repo)
- One-sentence-per-line is only in the editable default prompt text — do not append a hard-coded format instruction server-side
- API key: `GEMINI_API_KEY` via env → `Settings.gemini_api_key`
- Model: `gemini-2.5-flash` (spec mentioned `gemini-2.0-flash`, which is shut down; use 2.5)
- Auth: all new routes require the same session login as Generate/Library
- Generate story does not start a video job
- No Google SDK — use existing `httpx`
- Out of scope: streaming, prompt history, multiple prompts, model picker UI

## File map

| File | Responsibility |
|------|----------------|
| `src/roblox_viral/web/config.py` | Add `gemini_api_key`, `prompt_path` |
| `src/roblox_viral/web/prompt.py` | Default prompt, load/save `prompt.txt` |
| `src/roblox_viral/web/gemini.py` | Async Gemini REST generate call |
| `src/roblox_viral/web/app.py` | `/prompt` + `POST /api/generate-story` routes |
| `src/roblox_viral/web/templates/base.html` | Prompt nav link |
| `src/roblox_viral/web/templates/prompt.html` | Prompt editor page |
| `src/roblox_viral/web/templates/generate.html` | Generate story button + error slot |
| `src/roblox_viral/web/static/app.js` | Button handler to fill `#story` |
| `src/roblox_viral/web/static/app.css` | Minor styles if needed |
| `docker-compose.yml` | Pass `GEMINI_API_KEY` |
| `README.md` | Document env var + Prompt page |
| `tests/web/test_prompt.py` | Prompt persistence + auth |
| `tests/web/test_gemini_api.py` | Generate-story API (mocked httpx) |
| `tests/web/test_config.py` | `gemini_api_key` / `prompt_path` |

---

### Task 1: Config + prompt file helpers

**Files:**
- Modify: `src/roblox_viral/web/config.py`
- Create: `src/roblox_viral/web/prompt.py`
- Modify: `tests/web/test_config.py`
- Create: `tests/web/test_prompt.py`

**Interfaces:**
- Produces:
  - `Settings.gemini_api_key: str`
  - `Settings.prompt_path: Path` → `media_root / "prompt.txt"`
  - `DEFAULT_PROMPT: str` in `prompt.py`
  - `load_prompt(settings: Settings) -> str` — read file; if missing, write `DEFAULT_PROMPT` and return it
  - `save_prompt(settings: Settings, text: str) -> None` — write trimmed text; raise `ValueError` if empty after strip

- [ ] **Step 1: Write failing config test**

Add to `tests/web/test_config.py`:

```python
def test_gemini_settings_and_prompt_path(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("APP_PASSWORD", "secret")
    monkeypatch.setenv("APP_SECRET", "dev-secret-key-at-least-32-chars!!")
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    settings = Settings.from_env()
    assert settings.gemini_api_key == "test-gemini-key"
    assert settings.prompt_path == settings.media_root / "prompt.txt"
```

- [ ] **Step 2: Write failing prompt helper tests**

```python
# tests/web/test_prompt.py
from pathlib import Path

from roblox_viral.web.config import Settings
from roblox_viral.web.prompt import DEFAULT_PROMPT, load_prompt, save_prompt


def _settings(tmp_path: Path, monkeypatch) -> Settings:
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("APP_PASSWORD", "secret")
    monkeypatch.setenv("APP_SECRET", "dev-secret-key-at-least-32-chars!!")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    s = Settings.from_env()
    s.ensure_media_dirs()
    return s


def test_load_prompt_seeds_default(tmp_path, monkeypatch):
    s = _settings(tmp_path, monkeypatch)
    assert not s.prompt_path.exists()
    text = load_prompt(s)
    assert text == DEFAULT_PROMPT
    assert s.prompt_path.read_text(encoding="utf-8") == DEFAULT_PROMPT


def test_save_and_load_prompt(tmp_path, monkeypatch):
    s = _settings(tmp_path, monkeypatch)
    save_prompt(s, "Custom prompt.\nWrite one sentence per line.")
    assert load_prompt(s) == "Custom prompt.\nWrite one sentence per line."


def test_save_prompt_rejects_empty(tmp_path, monkeypatch):
    s = _settings(tmp_path, monkeypatch)
    try:
        save_prompt(s, "   \n  ")
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "empty" in str(exc).lower()
```

- [ ] **Step 3: Run tests — expect fail**

Run: `pytest tests/web/test_config.py::test_gemini_settings_and_prompt_path tests/web/test_prompt.py -v`  
Expected: FAIL (missing attribute / module)

- [ ] **Step 4: Implement config changes**

In `Settings` dataclass add field `gemini_api_key: str = ""`.

Add property:

```python
@property
def prompt_path(self) -> Path:
    return self.media_root / "prompt.txt"
```

In `from_env`:

```python
gemini_api_key = os.environ.get("GEMINI_API_KEY", "")
return cls(
    media_root=media,
    app_password=password,
    app_secret=secret,
    require_password=require,
    gemini_api_key=gemini_api_key,
)
```

- [ ] **Step 5: Implement `prompt.py`**

```python
from __future__ import annotations

from roblox_viral.web.config import Settings

DEFAULT_PROMPT = """Write a short Roblox horror storytime script for a vertical TikTok-style video.

Requirements:
- First-person narrator discovering something scary in a Roblox game
- 8 to 14 sentences
- Exactly one sentence per line
- No blank lines
- No title, preamble, or markdown — only the story lines
"""


def load_prompt(settings: Settings) -> str:
    path = settings.prompt_path
    if not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(DEFAULT_PROMPT, encoding="utf-8")
        return DEFAULT_PROMPT
    return path.read_text(encoding="utf-8")


def save_prompt(settings: Settings, text: str) -> None:
    cleaned = text.strip()
    if not cleaned:
        raise ValueError("Prompt cannot be empty")
    path = settings.prompt_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(cleaned + "\n", encoding="utf-8")
```

Note: `load_prompt` after save should return content that matches what was saved for the test — either strip trailing newline in `load_prompt` when comparing, or adjust `save_prompt` / test so `load_prompt` returns `cleaned` without forcing a mismatch. Prefer: `load_prompt` returns `path.read_text(encoding="utf-8").rstrip("\n")` so round-trip equals the saved cleaned text; and after seeding, write `DEFAULT_PROMPT` and return `DEFAULT_PROMPT.rstrip("\n")` if needed — keep `DEFAULT_PROMPT` without a trailing newline so seed equality holds.

Revised helpers for clean round-trip:

```python
def load_prompt(settings: Settings) -> str:
    path = settings.prompt_path
    if not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(DEFAULT_PROMPT, encoding="utf-8")
        return DEFAULT_PROMPT
    return path.read_text(encoding="utf-8").rstrip("\n")


def save_prompt(settings: Settings, text: str) -> None:
    cleaned = text.strip()
    if not cleaned:
        raise ValueError("Prompt cannot be empty")
    path = settings.prompt_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(cleaned + "\n", encoding="utf-8")
```

- [ ] **Step 6: Run tests — expect pass**

Run: `pytest tests/web/test_config.py::test_gemini_settings_and_prompt_path tests/web/test_prompt.py -v`  
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/roblox_viral/web/config.py src/roblox_viral/web/prompt.py tests/web/test_config.py tests/web/test_prompt.py
git commit -m "feat(web): add Gemini prompt file helpers and config"
```

---

### Task 2: Gemini REST client

**Files:**
- Create: `src/roblox_viral/web/gemini.py`
- Create: `tests/web/test_gemini.py`

**Interfaces:**
- Consumes: `Settings.gemini_api_key`
- Produces:
  - `GEMINI_MODEL = "gemini-2.5-flash"`
  - `async def generate_story(api_key: str, prompt: str) -> str`
  - Raises `ValueError` if `api_key` empty or `prompt` empty after strip
  - Raises `RuntimeError` on HTTP/API/empty-response failures (message suitable for 502 detail)

- [ ] **Step 1: Write failing tests**

```python
# tests/web/test_gemini.py
import httpx
import pytest

from roblox_viral.web.gemini import GEMINI_MODEL, generate_story


@pytest.mark.asyncio
async def test_generate_story_success(monkeypatch):
    async def fake_post(self, url, **kwargs):
        assert GEMINI_MODEL in url
        assert kwargs["headers"]["x-goog-api-key"] == "k"
        assert kwargs["json"]["contents"][0]["parts"][0]["text"] == "Do the thing"
        request = httpx.Request("POST", url)
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {"content": {"parts": [{"text": "I joined a game.\nIt was dark.\n"}]}}
                ]
            },
            request=request,
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    story = await generate_story("k", "Do the thing")
    assert story == "I joined a game.\nIt was dark."


@pytest.mark.asyncio
async def test_generate_story_requires_api_key():
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        await generate_story("", "prompt")


@pytest.mark.asyncio
async def test_generate_story_http_error(monkeypatch):
    async def fake_post(self, url, **kwargs):
        request = httpx.Request("POST", url)
        return httpx.Response(403, json={"error": {"message": "nope"}}, request=request)

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    with pytest.raises(RuntimeError, match="Gemini"):
        await generate_story("k", "prompt")
```

- [ ] **Step 2: Run tests — expect fail**

Run: `pytest tests/web/test_gemini.py -v`  
Expected: FAIL (module not found)

- [ ] **Step 3: Implement `gemini.py`**

```python
from __future__ import annotations

import httpx

GEMINI_MODEL = "gemini-2.5-flash"
_GEMINI_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent"
)


async def generate_story(api_key: str, prompt: str) -> str:
    key = (api_key or "").strip()
    text = (prompt or "").strip()
    if not key:
        raise ValueError("GEMINI_API_KEY is not configured")
    if not text:
        raise ValueError("Prompt cannot be empty")

    payload = {"contents": [{"parts": [{"text": text}]}]}
    headers = {
        "x-goog-api-key": key,
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(_GEMINI_URL, headers=headers, json=payload)
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Gemini request failed: {exc}") from exc

    if response.status_code >= 400:
        detail = response.text[:300]
        try:
            body = response.json()
            detail = body.get("error", {}).get("message", detail)
        except Exception:
            pass
        raise RuntimeError(f"Gemini API error ({response.status_code}): {detail}")

    data = response.json()
    try:
        parts = data["candidates"][0]["content"]["parts"]
        story = "".join(p.get("text", "") for p in parts).strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("Gemini returned an unexpected response") from exc
    if not story:
        raise RuntimeError("Gemini returned an empty story")
    return story
```

- [ ] **Step 4: Run tests — expect pass**

Run: `pytest tests/web/test_gemini.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/roblox_viral/web/gemini.py tests/web/test_gemini.py
git commit -m "feat(web): add Gemini REST story client"
```

---

### Task 3: Prompt page routes + template

**Files:**
- Create: `src/roblox_viral/web/templates/prompt.html`
- Modify: `src/roblox_viral/web/templates/base.html`
- Modify: `src/roblox_viral/web/app.py`
- Create: `tests/web/test_prompt_routes.py`

**Interfaces:**
- Consumes: `load_prompt`, `save_prompt`
- Produces:
  - `GET /prompt` → HTML editor (auth)
  - `POST /prompt` form field `prompt` → save, re-render with message or error

- [ ] **Step 1: Write failing route tests**

```python
# tests/web/test_prompt_routes.py
from fastapi.testclient import TestClient

from roblox_viral.web.app import create_app
from roblox_viral.web.config import Settings
from roblox_viral.web.prompt import DEFAULT_PROMPT, load_prompt


def _client(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("APP_PASSWORD", "s3cret")
    monkeypatch.setenv("APP_SECRET", "dev-secret-key-at-least-32-chars!!")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    return TestClient(create_app(Settings.from_env()))


def _login(c: TestClient) -> None:
    r = c.post("/login", data={"password": "s3cret"}, follow_redirects=False)
    assert r.status_code in (302, 303)


def test_prompt_requires_auth(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    assert c.get("/prompt").status_code == 401


def test_prompt_get_shows_default(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    _login(c)
    r = c.get("/prompt")
    assert r.status_code == 200
    assert "Prompt" in r.text
    assert "Write a short Roblox" in r.text or DEFAULT_PROMPT.split("\n")[0] in r.text


def test_prompt_save_persists(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    _login(c)
    r = c.post(
        "/prompt",
        data={"prompt": "Only this prompt.\nOne sentence per line."},
    )
    assert r.status_code == 200
    assert "saved" in r.text.lower()
    settings = c.app.state.settings
    assert load_prompt(settings) == "Only this prompt.\nOne sentence per line."
```

Note: existing auth may redirect to login (302/303) instead of 401 for HTML pages — match the pattern used by Generate/Library tests (`test_auth_routes.py`). If Generate returns redirect when unauthenticated, assert the same status for `/prompt`.

- [ ] **Step 2: Run tests — expect fail**

Run: `pytest tests/web/test_prompt_routes.py -v`  
Expected: FAIL (404)

- [ ] **Step 3: Update `base.html` nav**

```html
<nav>
  <a href="/">Generate</a>
  <a href="/library">Library</a>
  <a href="/prompt">Prompt</a>
  <form class="logout" method="post" action="/logout">
    <button type="submit">Logout</button>
  </form>
</nav>
```

- [ ] **Step 4: Create `prompt.html`**

```html
{% extends "base.html" %}
{% block title %}Prompt — Roblox Viral{% endblock %}
{% block content %}
  <h1>Prompt</h1>
  <p class="lede">
    Edit the Gemini prompt used by <strong>Generate story</strong> on the Generate page.
    Saved to the media folder and kept across restarts.
  </p>

  {% if error %}
  <p class="error">{{ error }}</p>
  {% endif %}
  {% if message %}
  <p class="ok">{{ message }}</p>
  {% endif %}

  <form class="prompt-form" method="post" action="/prompt">
    <label>
      Gemini prompt
      <textarea id="prompt" name="prompt" rows="16" required>{{ prompt }}</textarea>
    </label>
    <button type="submit">Save prompt</button>
  </form>
{% endblock %}
```

- [ ] **Step 5: Add routes in `app.py`**

Import:

```python
from roblox_viral.web.prompt import load_prompt, save_prompt
```

Add after library routes (before `/api/jobs`):

```python
@app.get("/prompt", response_class=HTMLResponse)
def prompt_page(
    request: Request,
    _: None = Depends(require_login),
) -> HTMLResponse:
    settings = request.app.state.settings
    return templates.TemplateResponse(
        request,
        "prompt.html",
        {
            "prompt": load_prompt(settings),
            "error": None,
            "message": None,
        },
    )


@app.post("/prompt", response_model=None)
async def prompt_save(
    request: Request,
    prompt: str = Form(...),
    _: None = Depends(require_login),
) -> Response:
    settings = request.app.state.settings
    try:
        save_prompt(settings, prompt)
    except ValueError as exc:
        return templates.TemplateResponse(
            request,
            "prompt.html",
            {
                "prompt": prompt,
                "error": str(exc),
                "message": None,
            },
            status_code=400,
        )
    return templates.TemplateResponse(
        request,
        "prompt.html",
        {
            "prompt": load_prompt(settings),
            "error": None,
            "message": "Prompt saved.",
        },
    )
```

- [ ] **Step 6: Align auth assertion with existing behavior**

Check `tests/web/test_auth_routes.py` for unauthenticated Generate status; update `test_prompt_requires_auth` to match (401 vs redirect).

- [ ] **Step 7: Run tests — expect pass**

Run: `pytest tests/web/test_prompt_routes.py tests/web/test_auth_routes.py -v`  
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add src/roblox_viral/web/app.py src/roblox_viral/web/templates/base.html src/roblox_viral/web/templates/prompt.html tests/web/test_prompt_routes.py
git commit -m "feat(web): add editable Prompt page"
```

---

### Task 4: Generate-story API + Generate page button

**Files:**
- Modify: `src/roblox_viral/web/app.py`
- Modify: `src/roblox_viral/web/templates/generate.html`
- Modify: `src/roblox_viral/web/static/app.js`
- Modify: `src/roblox_viral/web/static/app.css` (only if needed for button row)
- Create: `tests/web/test_gemini_api.py`
- Modify: `docker-compose.yml`
- Modify: `README.md`

**Interfaces:**
- Consumes: `load_prompt`, `generate_story`, `Settings.gemini_api_key`
- Produces: `POST /api/generate-story` → `{ "story": "..." }` with status mapping:
  - missing key → 503
  - empty prompt / `ValueError` with "empty" → 400
  - `RuntimeError` from Gemini → 502
  - other `ValueError` (e.g. missing key message) → 503 if message mentions `GEMINI_API_KEY`, else 400

- [ ] **Step 1: Write failing API tests**

```python
# tests/web/test_gemini_api.py
from fastapi.testclient import TestClient

from roblox_viral.web.app import create_app
from roblox_viral.web.config import Settings
from roblox_viral.web.prompt import save_prompt


def _client(tmp_path, monkeypatch, gemini_key: str = "fake-key"):
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("APP_PASSWORD", "s3cret")
    monkeypatch.setenv("APP_SECRET", "dev-secret-key-at-least-32-chars!!")
    if gemini_key is None:
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    else:
        monkeypatch.setenv("GEMINI_API_KEY", gemini_key)
    return TestClient(create_app(Settings.from_env()))


def _login(c: TestClient) -> None:
    r = c.post("/login", data={"password": "s3cret"}, follow_redirects=False)
    assert r.status_code in (302, 303)


def test_generate_story_requires_auth(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    assert c.post("/api/generate-story").status_code == 401


def test_generate_story_missing_key(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch, gemini_key=None)
    _login(c)
    r = c.post("/api/generate-story")
    assert r.status_code == 503
    assert "GEMINI_API_KEY" in r.json()["detail"]


def test_generate_story_success(tmp_path, monkeypatch):
    async def fake_generate(api_key: str, prompt: str) -> str:
        assert api_key == "fake-key"
        assert "Custom" in prompt
        return "I joined a scary game.\nThen the lights went out."

    monkeypatch.setattr(
        "roblox_viral.web.app.generate_story",
        fake_generate,
    )
    c = _client(tmp_path, monkeypatch)
    _login(c)
    save_prompt(c.app.state.settings, "Custom prompt for tests.")
    r = c.post("/api/generate-story")
    assert r.status_code == 200
    assert r.json()["story"] == "I joined a scary game.\nThen the lights went out."


def test_generate_story_empty_prompt(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    _login(c)
    # Write empty file bypassing save_prompt validation
    path = c.app.state.settings.prompt_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("   \n", encoding="utf-8")
    r = c.post("/api/generate-story")
    assert r.status_code == 400
```

- [ ] **Step 2: Run tests — expect fail**

Run: `pytest tests/web/test_gemini_api.py -v`  
Expected: FAIL (404)

- [ ] **Step 3: Add API route in `app.py`**

```python
from roblox_viral.web.gemini import generate_story
```

```python
@app.post("/api/generate-story")
async def api_generate_story(
    request: Request,
    _: None = Depends(require_login),
) -> dict:
    settings = request.app.state.settings
    if not settings.gemini_api_key.strip():
        raise HTTPException(
            status_code=503,
            detail="GEMINI_API_KEY is not configured",
        )
    prompt = load_prompt(settings).strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt cannot be empty")
    try:
        story = await generate_story(settings.gemini_api_key, prompt)
    except ValueError as exc:
        msg = str(exc)
        status = 503 if "GEMINI_API_KEY" in msg else 400
        raise HTTPException(status_code=status, detail=msg) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"story": story}
```

- [ ] **Step 4: Update `generate.html` story label area**

Replace the Story label block with:

```html
    <label>
      Story
      <textarea id="story" name="story" rows="10" required placeholder="One sentence per line."></textarea>
    </label>
    <div class="story-actions">
      <button id="generate-story-btn" type="button">Generate story</button>
      <p id="story-gen-error" class="error" hidden></p>
    </div>
```

- [ ] **Step 5: Update `app.js`**

Refactor so the IIFE does not return early before wiring the story button. Structure:

```javascript
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

  // ... existing job polling code unchanged ...
})();
```

- [ ] **Step 6: Minimal CSS**

```css
.story-actions {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.5rem;
  margin: -0.5rem 0 1rem;
}
```

- [ ] **Step 7: Docker + README**

`docker-compose.yml` environment:

```yaml
    environment:
      APP_PASSWORD: password
      APP_SECRET: fjdisofhdsuifhdsuifhdsiufhdsifhdu
      MEDIA_ROOT: /app/media
      GEMINI_API_KEY: ${GEMINI_API_KEY:-}
```

README optional env table: add `GEMINI_API_KEY` — used by Generate story. Mention Prompt page in the web app blurb. Link the new design spec.

- [ ] **Step 8: Run full web tests**

Run: `pytest tests/web -v`  
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add src/roblox_viral/web/app.py src/roblox_viral/web/templates/generate.html src/roblox_viral/web/static/app.js src/roblox_viral/web/static/app.css docker-compose.yml README.md tests/web/test_gemini_api.py
git commit -m "feat(web): generate story via Gemini and fill textarea"
```

---

## Spec coverage checklist

| Spec requirement | Task |
|------------------|------|
| `GEMINI_API_KEY` env / Settings | Task 1, 4 |
| `MEDIA_ROOT/prompt.txt` persistent editable prompt | Task 1, 3 |
| Default prompt with one sentence per line | Task 1 |
| Format not server-enforced | Task 1 (no append in gemini/app) |
| Header Prompt link | Task 3 |
| `/prompt` GET/POST | Task 3 |
| Generate story button fills textarea | Task 4 |
| `POST /api/generate-story` | Task 4 |
| Auth on new routes | Task 3, 4 |
| Error mapping 400/503/502 | Task 4 |
| httpx REST, no SDK | Task 2 |
| Docker/README docs | Task 4 |
| Tests with mocked Gemini | Task 2, 4 |

**Model note:** Spec said `gemini-2.0-flash`; plan uses `gemini-2.5-flash` because 2.0 Flash is shut down. Update the design spec model line when implementing if desired.
