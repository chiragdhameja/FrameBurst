"""Shared configuration + tool resolution for the VidCut pipeline."""
import os
import shutil
import glob

# ---- Project directories -------------------------------------------------
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPTS_DIR)

INPUT_DIR  = os.path.join(ROOT, "input")    # drop full-length videos here
WORK_DIR   = os.path.join(ROOT, "work")     # transcripts / srt / peaks (intermediate)
OUTPUT_DIR = os.path.join(ROOT, "output")   # finished reels
CLIPS_DIR  = os.path.join(ROOT, "clips")    # hot-point selections (clips json)

for _d in (INPUT_DIR, WORK_DIR, OUTPUT_DIR, CLIPS_DIR):
    os.makedirs(_d, exist_ok=True)


def _resolve(name):
    """Find an ffmpeg-family executable robustly on this machine."""
    # 1) on PATH
    p = shutil.which(name)
    if p:
        return p
    # 2) winget Links shim
    local = os.environ.get("LOCALAPPDATA", "")
    shim = os.path.join(local, "Microsoft", "WinGet", "Links", name + ".exe")
    if os.path.isfile(shim):
        return shim
    # 3) winget package install dir (version-agnostic glob)
    pat = os.path.join(local, "Microsoft", "WinGet", "Packages",
                       "Gyan.FFmpeg*", "**", name + ".exe")
    hits = glob.glob(pat, recursive=True)
    if hits:
        return hits[0]
    raise FileNotFoundError(
        f"Could not locate '{name}'. Install ffmpeg or add it to PATH.")


FFMPEG  = _resolve("ffmpeg")
FFPROBE = _resolve("ffprobe")

# ---- Reel output defaults ------------------------------------------------
REEL_W = 1080
REEL_H = 1920
MAX_CLIP_SECONDS = 60          # YouTube Shorts hard cap
DEFAULT_WHISPER_MODEL = "small"  # tiny | base | small | medium | large-v3


def probe_duration(path):
    """Return media duration in seconds (float) via ffprobe."""
    import subprocess
    out = subprocess.run(
        [FFPROBE, "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True)
    try:
        return float(out.stdout.strip())
    except ValueError:
        return 0.0


def stem(path):
    """Filename without directory or extension."""
    return os.path.splitext(os.path.basename(path))[0]


def resolve_input(path):
    """Turn a user-supplied (possibly relative) path into a real abspath.

    Tries it as-is, then relative to the project root, then input/."""
    cands = [path, os.path.join(ROOT, path), os.path.join(INPUT_DIR, os.path.basename(path))]
    for c in cands:
        if os.path.isfile(c):
            return os.path.abspath(c)
    return os.path.abspath(path)  # let the caller raise a clear error
