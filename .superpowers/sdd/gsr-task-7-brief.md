### Task 7: n8n API types

**Files:**
- Modify: `src/roblox_viral/web/api_v1.py`
- Modify: `tests/web/test_api_v1.py`
- Modify: `README.md` / `scripts/test-n8n-api.ps1`

**Interfaces:**

```python
def _mode_from_type(video_type: str) -> str:
    t = (video_type or "").strip().lower()
    if t == "single":
        return "single"
    if t == "reddit":
        return "reddit"
    if t == "leni":
        return "picture"
    if t == "roblox":
        raise ValueError("type 'roblox' is removed; use 'single'")
    raise ValueError("type must be 'single', 'reddit', or 'leni'")
```

For `reddit`:
- Do not require `source_name` or `media`
- Reject if both provided or if media provided (background not accepted)
- `mgr.create(..., source_name="", mode="reddit", ...)`

For `single`: same as former roblox (media XOR source_name).

- [ ] **Step 1: Tests** — single works; reddit with only story/voice/type; roblox → 400; leni ok

- [ ] **Step 2–4: Implement**

- [ ] **Step 5: Commit** `feat(api): n8n types single and reddit; reject roblox`

---

