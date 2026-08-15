# Task 8 Report: README polish + full regression

**Branch:** `feat/generate-single-reddit`  
**Date:** 2026-08-15  
**Status:** DONE

## Summary

Updated README Generate section: three tabs (Single/Picture/Reddit), overlay 2× fit-in-frame for Single+Reddit, and corrected `OVERLAY_VIDEO` description. n8n types (`single`|`reddit`|`leni`; reject `roblox`) were already documented from Task 7.

## Regression

```text
pytest -q → 153 passed in 9.79s
```

## Commit

`docs: document Single/Reddit generate modes` — README.md only

## Final review fixes

- Normalized every reddit clip input to 1080x1920 cover-crop and `yuv420p`
  before concatenation.
- Rejected non-empty `source_name` as well as media uploads for reddit API jobs.
- Added regression coverage for both findings.

## Final verification

```text
pytest tests/test_render.py tests/web/test_api_v1.py -q → 35 passed in 2.05s
pytest -q → 154 passed in 6.14s
```
