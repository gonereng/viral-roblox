### Task 5: README + full suite

**Files:**
- Modify: `README.md` — one short note under Generate/Reddit: title card with first line until sentence ends; no subscribe overlay yet

- [ ] **Step 1: Update README**

- [ ] **Step 2: `pytest -q` — all PASS**

- [ ] **Step 3: Commit** `docs: mention Reddit title card overlay`

---

## Spec coverage

| Spec item | Task |
|-----------|------|
| Pillow + avatar | 1 |
| Card PNG + first-sentence timing | 2 |
| ffmpeg title overlay | 3 |
| Reddit job wiring; no greenscreen | 4 |
| Docs | 5 |

## Consistency

- Overlay expression: `overlay=(W-w)/2:(H/2-h):enable='lte(t,{T:.3f})'`
- Card width 972; username fixed constant
- Reddit: `overlay_path=None` always when title card used
