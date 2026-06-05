# VidCut launcher - runs the pipeline with the project's bundled Python venv.
# Usage:
#   .\vidcut.ps1 list
#   .\vidcut.ps1 prep   "input\myvideo.mp4"
#   .\vidcut.ps1 digest "input\myvideo.mp4"
#   .\vidcut.ps1 reels  "clips\myvideo.clips.json"
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$py = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { Write-Error "venv missing at $py"; exit 1 }
& $py (Join-Path $root "scripts\vidcut.py") @args
