### Task 6: Generate frontend three tabs

**Files:**
- Modify: `src/roblox_viral/web/templates/generate.html`
- Modify: `src/roblox_viral/web/static/app.js`
- Modify: `tests/web/test_api.py` (HTML assertions)

**Interfaces:**
- Tabs: `#tab-single` label "Single background video"; `#tab-picture`; `#tab-reddit` "Reddit"
- Single block: `#source_name` from slices only
- Reddit block: short note “Uses random clips from Library → Videos”; no select
- `data-mode` / `currentMode`: `single|picture|reddit`
- Video speed visible for single+reddit; hidden for picture
- Generate disabled: single if no sources; picture if no images; reddit if no videos (pass `has_videos` boolean from template)
- POST `mode`, `source_name` (empty string for reddit)

- [ ] **Step 1: Update HTML/JS + page tests asserting tab ids and absence of Roblox label**

- [ ] **Step 2: Commit** `feat(web): Generate tabs for Single, Picture, and Reddit`

---

