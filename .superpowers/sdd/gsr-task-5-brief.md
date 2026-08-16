### Task 5: UI jobs API + Generate page context

**Files:**
- Modify: `src/roblox_viral/web/app.py`
- Modify: `tests/web/test_api.py`

**Interfaces:**
- `CreateJobBody.mode` default `"single"`
- Pass `list_sources` + `list_videos` (count or list) + `list_images` to template (not `list_roblox_sources`)
- Validate mode; 400 on bad mode

- [ ] **Step 1: Tests** — POST mode=single/reddit/picture; reject mode=roblox or accept only if you map (prefer reject on UI API for clarity, or map — **map roblox→single** on UI for soft compat; n8n still hard-rejects)

Plan choice: UI API **maps** `roblox`→`single`; n8n **rejects** `roblox`.

- [ ] **Step 2–4: Implement**

- [ ] **Step 5: Commit** `feat(web): API and generate context for single/reddit modes`

---

