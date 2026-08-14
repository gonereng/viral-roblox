# Task 3 Report: README + PowerShell example for n8n multipart upload

## Status
**Complete**

## Commits
- `docs: n8n multipart upload examples` — README n8n section: multipart/form-data fields, media vs source_name, PowerShell upload + Library examples

## What changed
- Replaced JSON create docs with `multipart/form-data` field list (`voice`, `story`, `type`, `media` XOR `source_name`)
- Added PowerShell `Invoke-RestMethod -Form` upload example with `X-API-Key` header
- Added PowerShell Library-name form example
- Poll/download steps preserved in prose

## Test summary
Docs-only task; no tests run.

## Concerns
- Library-name PowerShell snippet omits `$headers` and `Invoke-RestMethod` (per brief); users may need the upload example’s header/invoke lines copied over.
