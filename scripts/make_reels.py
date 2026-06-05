"""Turn a clips selection into upload-ready vertical reels.

Input: a clips json (see clips/EXAMPLE.clips.json), e.g.
  {
    "source": "input/talk.mp4",
    "clips": [
      {"id": "01", "start": 132.0, "end": 178.5,
       "title": "The one habit that changed everything",
       "description": "...", "hashtags": ["#shorts", "#motivation"]}
    ]
  }

For each clip it: trims, reframes to 1080x1920 (scale-to-cover + center crop),
burns word-timed captions, caps length at 60s, and writes a sidecar .txt with
the suggested title / description / hashtags for upload.
"""
import os
import sys
import json
import subprocess

import config


def _ass_ts(s):
    s = max(0.0, s)
    h = int(s // 3600); m = int((s % 3600) // 60); sec = s % 60
    return f"{h:d}:{m:02d}:{sec:05.2f}"


def _load_words(source):
    """All words (absolute timestamps) from the transcript of `source`."""
    tj = os.path.join(config.WORK_DIR, config.stem(source), "transcript.json")
    if not os.path.isfile(tj):
        return []
    data = json.load(open(tj, encoding="utf-8"))
    words = []
    for seg in data.get("segments", []):
        for w in seg.get("words", []):
            if w.get("start") is None:
                continue
            words.append(w)
    return words


# --- Caption look ---------------------------------------------------------
# Captions are pinned to a single fixed point in the bottom band of the frame
# (\an5 = centre-anchored at \pos) so they never drift up/down between cues.
# Text stays white; each speaker gets a subtle accent on the outline.
CAP_FONTSIZE = 58
CAP_POS = (config.REEL_W // 2, int(config.REEL_H * 0.81))  # fixed, bottom ~30%

# ASS outline colours, &HBBGGRR. Mostly-white text with a hint of speaker colour.
ACCENT = {
    "host":  "&H008CFF&",   # orange
    "guest": "&HFF8C28&",   # blue  (default guest)
    "guest_green": "&H5AC83C&",
}

_ASS_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Arial,{fs},&H00FFFFFF,&H000000FF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,3,2,5,60,60,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _role_at(t, speakers):
    """Which speaker role is talking at time `t` (absolute source seconds)."""
    for sp in (speakers or []):
        if sp.get("start", 0) <= t < sp.get("end", 0):
            return sp.get("role", "guest")
    return "guest"


def _caption_ass(words, start, end, out_path, speakers,
                 max_words=5, max_dur=2.2):
    """Build a clip-local ASS file: short cues, fixed position, speaker colour."""
    sel = [w for w in words if w["end"] > start and w["start"] < end]
    cues, cur = [], []
    for w in sel:
        cur.append(w)
        span = cur[-1]["end"] - cur[0]["start"]
        ends_phrase = w["word"].strip().endswith((".", "!", "?", ","))
        if len(cur) >= max_words or span >= max_dur or ends_phrase:
            cues.append(cur); cur = []
    if cur:
        cues.append(cur)

    x, y = CAP_POS
    out = [_ASS_HEADER.format(w=config.REEL_W, h=config.REEL_H, fs=CAP_FONTSIZE)]
    for cue in cues:
        a = max(0.0, cue[0]["start"] - start)
        b = max(a + 0.3, cue[-1]["end"] - start)
        mid = (cue[0]["start"] + cue[-1]["end"]) / 2.0
        accent = ACCENT.get(_role_at(mid, speakers), ACCENT["guest"])
        text = "".join(w["word"] for w in cue).strip().upper().replace("\n", " ")
        ov = "{\\an5\\pos(%d,%d)\\3c%s}" % (x, y, accent)
        out.append(f"Dialogue: 0,{_ass_ts(a)},{_ass_ts(b)},Cap,,0,0,0,,{ov}{text}")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    return len(cues)


def build_clip(source_abs, clip, work, outdir):
    cid = str(clip.get("id", "01"))
    start = float(clip["start"])
    end = float(clip["end"])
    dur = min(end - start, config.MAX_CLIP_SECONDS)
    if end - start > config.MAX_CLIP_SECONDS:
        print(f"  [clip {cid}] {end-start:.1f}s > 60s cap -> trimmed to 60s")

    sub_name = f"sub_{cid}.ass"
    words = _load_words(source_abs)
    speakers = clip.get("speakers", [])
    n_cues = _caption_ass(words, start, start + dur,
                          os.path.join(work, sub_name), speakers) if words else 0

    vf = (f"scale={config.REEL_W}:{config.REEL_H}:"
          f"force_original_aspect_ratio=increase,"
          f"crop={config.REEL_W}:{config.REEL_H}")
    if n_cues:
        vf += f",ass={sub_name}"

    out_name = f"{config.stem(source_abs)}_clip{cid}.mp4"
    out_path = os.path.join(outdir, out_name)
    cmd = [config.FFMPEG, "-y", "-ss", f"{start}", "-i", source_abs,
           "-t", f"{dur}", "-vf", vf,
           "-c:v", "libx264", "-preset", "medium", "-crf", "20",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
           "-movflags", "+faststart", out_path]
    print(f"  [clip {cid}] {start:.1f}-{start+dur:.1f}s "
          f"({dur:.1f}s, {n_cues} caption cues) -> {out_name}")
    # cwd=work so the subtitles filter finds the .srt without path escaping
    r = subprocess.run(cmd, cwd=work, capture_output=True, text=True)
    if r.returncode != 0:
        print("  ffmpeg error:\n" + (r.stderr or "")[-1500:])
        return None

    # upload sidecar
    title = clip.get("title", f"{config.stem(source_abs)} - clip {cid}")
    desc = clip.get("description", "")
    tags = clip.get("hashtags", ["#shorts"])
    side = os.path.splitext(out_path)[0] + ".txt"
    with open(side, "w", encoding="utf-8") as f:
        f.write(f"TITLE:\n{title}\n\nDESCRIPTION:\n{desc}\n\n"
                f"HASHTAGS:\n{' '.join(tags)}\n")
    return out_path


def run(clips_json):
    if not os.path.isfile(clips_json):
        alt = os.path.join(config.ROOT, clips_json)
        if os.path.isfile(alt):
            clips_json = alt
    spec = json.load(open(clips_json, encoding="utf-8"))
    source = spec["source"]
    if not os.path.isabs(source):
        source = os.path.join(config.ROOT, source)
    source = os.path.abspath(source)
    if not os.path.isfile(source):
        print(f"source video not found: {source}")
        sys.exit(1)

    work = os.path.join(config.WORK_DIR, config.stem(source))
    outdir = os.path.join(config.OUTPUT_DIR, config.stem(source))
    os.makedirs(work, exist_ok=True)
    os.makedirs(outdir, exist_ok=True)

    print(f"[reels] {len(spec['clips'])} clips from {os.path.basename(source)}")
    made = []
    for clip in spec["clips"]:
        p = build_clip(source, clip, work, outdir)
        if p:
            made.append(p)
    print(f"[reels] done: {len(made)} reels in {outdir}")
    return made


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python make_reels.py <clips.json>")
        sys.exit(1)
    run(sys.argv[1])
