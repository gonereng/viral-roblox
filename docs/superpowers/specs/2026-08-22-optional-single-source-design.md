# Optional Single Source — Random Library Slice — Design

**Date:** 2026-08-22  
**Status:** Approved (conversation)  
**Builds on:** [2026-08-14-n8n-video-api-design.md](./2026-08-14-n8n-video-api-design.md), [2026-08-14-n8n-media-upload-design.md](./2026-08-14-n8n-media-upload-design.md)

## Goal

For n8n `POST /api/v1/videos` with `type=single`, make `media` and `source_name` optional. If neither is provided, pick a random clip from Library **Sources** (`media/sources/`, the 1‑minute slices) and run a normal Single job with that name.

## Product decisions

| Decision | Choice |
|----------|--------|
| Scope | API `type=single` only |
| Pool | `list_sources()` only (not Videos tab / `media/videos/`) |
| Selection | Uniform random (`random.choice`) |
| Empty pool | **400** with clear detail |
| Both `media` and `source_name` | Still **400** |
| One of the two provided | Unchanged |
| `leni` | Still requires media XOR source_name |
| `reddit` | Unchanged (rejects media/source_name) |
| GUI Generate | Unchanged (still requires an explicit source) |
| Persist choice | Chosen name stored as `JobRecord.source_name` (visible on status GET) |

## Architecture

In `create_video` (`api_v1.py`), after mode resolution:

```
if mode == "single" and not has_media and not name:
    sources = list_sources(settings)
    if not sources:
        raise HTTP 400 "No source videos available"
    name = random.choice(sources).name
# then existing create path with stored_name = name
```

No changes to `JobManager.create` / `run_job` beyond receiving a concrete library `source_name`.

## Error handling

| Case | Response |
|------|----------|
| Single, neither media nor source_name, Sources empty | 400 |
| Single, both media and source_name | 400 (existing) |
| Single, source_name not found | 400 via existing create/resolve |
| leni, neither | 400 (existing “Provide media file or source_name”) |

## Testing

- Single with neither field + one source on disk → 200; status `source_name` equals that file (or one of the files when multiple; use monkeypatched `random.choice` for determinism)
- Single with neither + empty Sources → 400
- Single with both media and source_name → still 400
- leni with neither → still 400
- README: note optional media/source_name for single; random Sources slice when omitted

## Non-goals

- Random from Videos tab
- GUI auto-pick
- Changing Picture (`leni`) or Reddit rules
- Weighted / “least recently used” selection
