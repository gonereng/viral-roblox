### Task 3: README + PowerShell example

**Files:**
- Modify: `README.md`

**Interfaces:** docs only

- [ ] **Step 1: Update n8n API section**

Replace JSON create docs with form-data:

```markdown
### n8n API

Set `API_KEY` in `.env`. Header: `X-API-Key`.

**Create** — `POST /api/v1/videos` as `multipart/form-data`:

- `voice`, `story`, `type` (`roblox`|`leni`)
- either file field `media` **or** text field `source_name` (Library name)

Then poll `GET /api/v1/videos/{id}` and download `GET /api/v1/videos/{id}/download`.

PowerShell (upload):

```powershell
$headers = @{ "X-API-Key" = "your-key" }
$form = @{
  voice = "en-US-EmmaNeural"
  story = "Hello.`nWorld."
  type  = "roblox"
  media = Get-Item "C:\path\to\clip.mp4"
}
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/v1/videos" -Headers $headers -Form $form
```

PowerShell (Library name):

```powershell
$form = @{
  voice = "en-US-EmmaNeural"
  story = "Hello.`nWorld."
  type  = "roblox"
  source_name = "gameplay-1.mp4"
}
```
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: n8n multipart upload examples"
```

---

## Self-review (plan vs spec)

| Spec | Task |
|------|------|
| Multipart + XOR media/source_name | Task 2 |
| Ephemeral job-local input, as-is roblox | Task 1–2 |
| leni image upload | Task 2 |
| Size limits | Task 2 |
| README examples | Task 3 |
| Status/download unchanged | Honored |

No placeholders. `ephemeral: bool` naming consistent across tasks.
