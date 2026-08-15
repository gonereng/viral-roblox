# n8n / local API test (Windows PowerShell 5.1 + curl.exe)
$apiKey = "your-key-from-.env"   # paste API_KEY from .env
$base   = "http://127.0.0.1:8000"
$video  = "C:\path\to\your.mp4"  # change this

$createJson = curl.exe -s -X POST "$base/api/v1/videos" `
  -H "X-API-Key: $apiKey" `
  -F "voice=en-US-EmmaNeural" `
  -F "story=Hello from n8n.`nThis is a test." `
  -F "type=single" `
  -F "pitch=15" `
  -F "speed=130" `
  -F "video_speed=100" `
  -F "media=@$video"

Write-Host "create: $createJson"
$create = $createJson | ConvertFrom-Json
if (-not $create.id) { throw "Create failed: $createJson" }
$id = $create.id
Write-Host "id=$id"

do {
  Start-Sleep -Seconds 2
  $status = curl.exe -s "$base/api/v1/videos/$id" -H "X-API-Key: $apiKey" | ConvertFrom-Json
  Write-Host "status=$($status.status)"
} while ($status.status -notin @("done", "error"))

if ($status.status -eq "error") { throw $status.error }

$out = Join-Path $PWD "out-$id.mp4"
curl.exe -s -L "$base/api/v1/videos/$id/download" -H "X-API-Key: $apiKey" -o $out
Write-Host "saved $out"
