### Task 1: Pillow dependency + avatar asset

**Files:**
- Modify: `pyproject.toml`
- Create: `src/roblox_viral/assets/reddit_avatar.png` (small circular-ready PNG; can be a simple generated placeholder if no artist asset — e.g. write a tiny PNG via a one-off script or ship a minimal Snoo-like circle)

**Interfaces:**
- Produces: `Pillow` in project dependencies; avatar path resolvable as `Path(__file__).parent / "assets" / "reddit_avatar.png"`
- `package-data` already includes `assets/*`

- [ ] **Step 1: Add dependency**

```toml
  "Pillow>=10.0.0",
```

- [ ] **Step 2: Create avatar PNG** under `src/roblox_viral/assets/reddit_avatar.png` (at least 128×128 RGBA). Acceptable: solid circle with simple face marks matching dark Reddit look.

- [ ] **Step 3: `pip install -e ".[dev]" -q` and verify import**

```bash
python -c "from PIL import Image; print(Image.__version__)"
```

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml src/roblox_viral/assets/reddit_avatar.png
git commit -m "chore: add Pillow and reddit avatar asset"
```

---

