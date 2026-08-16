### Task 8: README + full regression

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Document Generate tabs, overlay 2×, n8n types**

- [ ] **Step 2: `pytest -q` — all PASS**

- [ ] **Step 3: Commit** `docs: document Single/Reddit generate modes`

---

## Spec coverage

| Spec item | Task |
|-----------|------|
| Overlay 2× fit | 1 |
| plan_reddit_clips | 2 |
| concat temp bg | 3 |
| Job modes + run | 4 |
| API/context | 5 |
| Generate UI | 6 |
| n8n types | 7 |
| README | 8 |

## Consistency

- Mode strings: `single`, `picture`, `reddit` only in new code
- Overlay scale string: `scale=1080:1920:force_original_aspect_ratio=decrease`
- n8n rejects `roblox`; UI may map `roblox`→`single`
