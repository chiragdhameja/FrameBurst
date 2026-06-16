# AGENTS.md — VidCut clip-making runbook

How to take a long video and ship an upload-ready 9:16 YouTube Short, start to finish.
This is the process we actually use; follow it top to bottom.

---

## 0. What this project is

VidCut is a **local, no-cloud pipeline**: long talking-head video → 1 punchy 9:16 Short
(≤60s) with burned-in word-timed captions. Everything runs on this machine via the
`.\vidcut.ps1` launcher (uses the bundled `.venv` automatically).

- `input/`  — source videos (full episodes + trimmed slices)
- `work/<name>/` — transcripts / SRT / peaks intermediates (one folder per source stem)
- `clips/<name>.clips.json` — the hot-point selection(s) you author
- `output/<name>/` — finished reels + a `.txt` sidecar (title/description/hashtags)

**Tooling:** ffmpeg + ffprobe (on PATH), Python 3.12 `.venv` with faster-whisper,
`yt-dlp` (`.venv\Scripts\python.exe -m yt_dlp`), `aria2c`
(`%LOCALAPPDATA%\Microsoft\WinGet\Links\aria2c.exe`). Shell is PowerShell.

---

## 1. Channel strategy — read this before picking anything

**Lane:** world news + bold takes from well-known people, sourced from podcasts/interviews.

**The formula that gets views (proven this far):**
1. **Arguable claim** — the clip must make a statement people *argue with* (agree/disagree).
   A comment in the first hour is the algorithm's snowball trigger. Low-stakes/funny-but-
   nothing-to-debate clips die.
2. **Universal nerve** — AI anxiety, money, war, "is X overrated", power. Not niche whimsy.
3. **Big name** — recognizable person delivers the line (Trump, Elon, Zuck, Hillary…).
4. **Hook in the first 1–2 seconds** — open ON the claim, cut all setup/ramble.
5. **Self-contained** — understandable cold, zero prior context. If *you* don't instantly
   get it, neither will a scroller. (This killed the "Brazil ranked 6th" panel clip.)
6. **Short** — aim 12–30s. 60s is a hard cap, not a target. Short = high completion = reach.
7. **Plain white captions.** Per-speaker colors are OFF.

**What does NOT work / avoid:**
- Skill-edit / gameplay montages (sports highlights etc.) — our captioning pipeline can't
  make them and match footage is a copyright minefield. We do *talking* clips only.
- Graphic / sensitive content (war footage, "genocide" debates, heavy profanity) — age-
  restriction + demonetization risk for a growing channel. Prefer punchy-but-postable.
- Dry stats/policy explainers, funny-but-low-stakes tangents.

---

## 2. Find a topic + a clippable source

Use the VidiQ MCP tools + web search. The goal is a **long talking-head source on YouTube**
featuring a well-known person making an arguable claim about a current story.

1. `WebSearch` "biggest world news this week" → what's hot right now.
2. `vidiq_outliers` (keyword = the topic, contentType `short`, publishedWithin `thisMonth`)
   → which moments/voices are already catching, and which podcasts/shows to mine.
3. `vidiq_youtube_search` (the topic + "podcast/interview", videoDuration `long`,
   order `date`) → recent full episodes you can download and clip.

Pick a source that is a clean talking format (podcast/interview), recognizable guest,
and has at least one self-contained arguable moment. Grab its **YouTube video ID**.

---

## 3. Locate the exact moment via auto-captions (no full download yet)

Pull YouTube's auto-captions (fast, ~1MB) and scan them so you only download what you need:

```powershell
.venv\Scripts\python.exe -m yt_dlp --skip-download --write-auto-subs --sub-langs en `
  --sub-format vtt --print "%(id)s | %(duration)s sec | %(title)s" `
  -o "work\_subs\%(id)s.%(ext)s" "https://www.youtube.com/watch?v=<ID>"
```

Parse the `.vtt` (strip tags, dedupe consecutive lines, keep timestamps) and grep for
opinion/conflict markers ("can't", "lie", "stronger", "disaster", "crooked"…) to find
hotspots, then read the surrounding window to choose the single best self-contained beat.
Note its approximate **timestamp** (YouTube timeline == local file timeline — verified).

---

## 4. Download the source, then trim a slice

**Download the FULL file with aria2c** (fast, reliable), then trim locally.
Do **NOT** use `--download-sections` — it routes through ffmpeg's single connection and
crawls; full aria2c + a local stream-copy trim is far faster.

```powershell
$aria = "$env:LOCALAPPDATA\Microsoft\WinGet\Links\aria2c.exe"
.venv\Scripts\python.exe -m yt_dlp -S "res:1080" `
  --downloader $aria --downloader-args "aria2c:-x16 -s16 -k1M" `
  --merge-output-format mp4 -o "input\SRC_<ID>.%(ext)s" "https://www.youtube.com/watch?v=<ID>"
```

Trim a generous slice (~moment ±30–60s) — instant stream copy:

```powershell
ffmpeg -y -ss <START_SEC> -i "input\SRC_<ID>.mp4" -t <DUR_SEC> -c copy "input\<NAME>.mp4"
```

Slices are keyframe-cut, so the slice may start a second or two early — that's fine, you
re-derive exact timing from the local transcript next.

---

## 5. Transcribe the slice (word-level timing)

```powershell
.\vidcut.ps1 prep "input\<NAME>.mp4"
```

Rate ≈ 16s per audio-minute (`small` model, CPU). Output: `work\<NAME>\transcript.json`.

Then dump word timings to pick exact in/out at clean boundaries:

```powershell
.venv\Scripts\python.exe -c "import json; d=json.load(open('work/<NAME>/transcript.json',encoding='utf-8')); w=[x for s in d['segments'] for x in s.get('words',[]) if x.get('start') is not None]; [print(f'{x[\"start\"]:.2f}-{x[\"end\"]:.2f} {x[\"word\"]!r}') for x in w]"
```

Choose `start`/`end` that:
- open ON the hook (drop "well/so/um" lead-ins where possible),
- end on a complete thought / punchy button (not mid-word — that reads as "abrupt"),
- keep it ~12–30s.

---

## 6. Author the clips.json

`clips\<NAME>.clips.json` — see `clips/EXAMPLE.clips.json`. Schema:

```json
{
  "source": "input/<NAME>.mp4",
  "clips": [
    {
      "id": "short-id",
      "start": 12.3,
      "end": 28.6,
      "reframe": "cover",
      "title": "Bold, arguable, clickable title",
      "description": "One or two lines + (Source, date).",
      "hashtags": ["#shorts", "#topic", "#bigname"]
    }
  ]
}
```

- `reframe`: **`cover`** (default) = center-crop to fill — use for a single centered
  speaker. **`fit`** = letterbox the whole 16:9 onto a blurred copy of itself — use for
  **panels / shows with on-screen graphics** so nothing is cropped and captions sit in the
  clean lower blur band. (There is no face tracking; cover is a center crop.)
- `>60s` is auto-trimmed to 60s. Output filename = `<source-stem>_clip<id>.mp4`.

---

## 7. Render + verify

```powershell
.\vidcut.ps1 reels "clips\<NAME>.clips.json"
```

Render ≈ 0.25s per clip-second (cheap). Then **always eyeball a frame**:

```powershell
ffmpeg -y -ss <SEC_INTO_CLIP> -i "output\<NAME>\<stem>_clip<id>.mp4" -frames:v 1 work\_v.png
```

Check: subject centered (switch `cover`→`fit` if a panel got cropped or captions collide
with the show's lower-thirds), captions readable/correct (fix obvious mis-transcriptions in
`transcript.json` and re-render), clean start/end.

---

## 8. Write the upload copy (engagement = reach)

The `.txt` sidecar has title/description/hashtags. Also prepare a **pinned comment** —
this is the single biggest lever for the first-hour comment that triggers the push:

- **Binary or "be honest"** question, personal ("would *you*…"), 1 line, 1 emoji, end `👇`.
- Take no side — let them argue. e.g. *"Was he right, or is this just spin? 👇"*

**Do NOT add a static "like & subscribe" end-page** — it adds dead time and breaks the
Shorts loop, tanking completion %. Use the pinned comment + a clean loop instead.

---

## 9. Post (manual, on the user's account)

1. Upload the `output\...\*.mp4`.
2. Paste title + description (from the sidecar / your copy).
3. Pin the question comment; **reply fast to the first few comments**.
4. Let it loop. Never fake engagement from alt accounts (ToS violation, risks the channel).
5. If a clip got ~0 impressions, a delete + genuinely re-cut re-upload can get a fresh
   first-test — but re-posting the *identical* file does little. Content is the real limiter.

---

## Pitfalls cheat-sheet
- ❌ `--download-sections` (slow) → ✅ full aria2c download + `ffmpeg -c copy` trim.
- ❌ insider / format-dependent reveals → ✅ self-contained, understandable cold.
- ❌ long & rambly → ✅ 12–30s, hook-first.
- ❌ funny-but-nothing-to-argue → ✅ arguable claim that pulls comments.
- ❌ static end CTA page → ✅ pinned question + clean loop.
- ❌ gameplay/skill-edit trends → ✅ talking-head podcast/interview clips only.

## Strategy memory
Deeper rationale + the running log of what's landed/flopped lives in the agent memory:
`vidcut-clip-selection`, `vidcut-captions-wip`, `vidcut-download-recipe`,
`vidcut-architecture`, `vidcut-benchmark`, `vidcut-elon-scout`.
