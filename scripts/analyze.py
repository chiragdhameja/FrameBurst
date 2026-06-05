"""Audio energy + scene-cut analysis to surface 'hot' moments.

Outputs (into work/<stem>/):
  peaks.json  { duration, loud_moments:[t..], scene_cuts:[t..], energy:[{t,db}..] }
  peaks.txt   human-readable digest of the loudest moments and scene changes
"""
import os
import re
import sys
import json
import subprocess

import numpy as np

import config

SR = 16000          # analysis sample rate (mono)
WIN = 0.5           # energy window, seconds


def _energy_curve(video_path):
    """Decode mono PCM via ffmpeg and compute windowed RMS in dBFS."""
    proc = subprocess.run(
        [config.FFMPEG, "-v", "error", "-i", video_path,
         "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"],
        capture_output=True)
    pcm = np.frombuffer(proc.stdout, dtype=np.int16).astype(np.float32) / 32768.0
    if pcm.size == 0:
        return [], []
    win = int(SR * WIN)
    n = pcm.size // win
    pcm = pcm[: n * win].reshape(n, win)
    rms = np.sqrt(np.mean(pcm ** 2, axis=1) + 1e-9)
    db = 20 * np.log10(rms + 1e-9)
    times = np.arange(n) * WIN
    return times, db


def _loud_moments(times, db):
    """Window centres whose loudness sits well above the running median."""
    if len(db) == 0:
        return []
    thresh = np.median(db) + 0.8 * np.std(db)
    hot = times[db >= thresh]
    # merge points within 3s into single representative moments
    moments = []
    for t in hot:
        if not moments or t - moments[-1] > 3.0:
            moments.append(float(t))
    return moments


def _scene_cuts(video_path):
    """Timestamps where the picture changes a lot (ffmpeg scene detection)."""
    proc = subprocess.run(
        [config.FFMPEG, "-v", "error", "-i", video_path,
         "-vf", "select='gt(scene,0.4)',metadata=print",
         "-an", "-f", "null", "-"],
        capture_output=True, text=True)
    cuts = []
    for m in re.finditer(r"pts_time:([0-9.]+)", proc.stderr or ""):
        cuts.append(round(float(m.group(1)), 2))
    return cuts


def _mmss(s):
    return f"{int(s // 60):02d}:{int(s % 60):02d}"


def analyze(video_path):
    video_path = config.resolve_input(video_path)
    work = os.path.join(config.WORK_DIR, config.stem(video_path))
    os.makedirs(work, exist_ok=True)

    print("[analyze] computing audio energy ...")
    times, db = _energy_curve(video_path)
    loud = _loud_moments(times, db)

    print("[analyze] detecting scene cuts ...")
    cuts = _scene_cuts(video_path)

    duration = config.probe_duration(video_path)
    energy = [{"t": round(float(t), 2), "db": round(float(d), 1)}
              for t, d in zip(times, db)]
    data = {"source": os.path.abspath(video_path), "duration": duration,
            "loud_moments": loud, "scene_cuts": cuts, "energy": energy}

    with open(os.path.join(work, "peaks.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    # readable digest: top loud moments by dB
    ranked = sorted(energy, key=lambda e: e["db"], reverse=True)[:25]
    ranked.sort(key=lambda e: e["t"])
    lines = [f"duration: {_mmss(duration)} ({duration:.0f}s)",
             f"loud moments: {len(loud)}   scene cuts: {len(cuts)}", "",
             "== Top energy windows =="]
    lines += [f"  {_mmss(e['t'])}  {e['db']:+.1f} dB" for e in ranked]
    lines += ["", "== Scene cuts =="]
    lines += [f"  {_mmss(c)}" for c in cuts[:60]]
    with open(os.path.join(work, "peaks.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"[analyze] {len(loud)} loud moments, {len(cuts)} scene cuts -> {work}")
    return data


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python analyze.py <video>")
        sys.exit(1)
    analyze(sys.argv[1])
