"""Transcribe a video with faster-whisper -> word-level timestamps.

Outputs (into work/<stem>/):
  transcript.json  full structured result (segments + words)
  full.srt         standard subtitles for the whole video
  transcript.txt   compact "[mm:ss] text" lines for human/AI skimming
"""
import os
import sys
import json

import config


def _ts(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _mmss(seconds):
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m:02d}:{s:02d}"


def transcribe(video_path, model_size=None):
    from faster_whisper import WhisperModel

    model_size = model_size or config.DEFAULT_WHISPER_MODEL
    video_path = config.resolve_input(video_path)
    work = os.path.join(config.WORK_DIR, config.stem(video_path))
    os.makedirs(work, exist_ok=True)

    print(f"[transcribe] loading model '{model_size}' (CPU, int8)...")
    model = WhisperModel(model_size, device="cpu", compute_type="int8")

    print(f"[transcribe] transcribing {os.path.basename(video_path)} ...")
    segments, info = model.transcribe(
        video_path, word_timestamps=True, vad_filter=True)

    seg_list = []
    srt_lines = []
    txt_lines = []
    idx = 0
    for seg in segments:
        idx += 1
        words = [{"start": w.start, "end": w.end, "word": w.word}
                 for w in (seg.words or [])]
        seg_list.append({
            "id": idx, "start": seg.start, "end": seg.end,
            "text": seg.text.strip(), "words": words,
        })
        srt_lines.append(
            f"{idx}\n{_ts(seg.start)} --> {_ts(seg.end)}\n{seg.text.strip()}\n")
        txt_lines.append(f"[{_mmss(seg.start)}] {seg.text.strip()}")
        if idx % 25 == 0:
            print(f"  ...{idx} segments")

    result = {
        "source": os.path.abspath(video_path),
        "language": info.language,
        "duration": info.duration,
        "model": model_size,
        "segments": seg_list,
    }

    with open(os.path.join(work, "transcript.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    with open(os.path.join(work, "full.srt"), "w", encoding="utf-8") as f:
        f.write("\n".join(srt_lines))
    with open(os.path.join(work, "transcript.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(txt_lines))

    print(f"[transcribe] {idx} segments, lang={info.language}, "
          f"dur={info.duration:.0f}s -> {work}")
    return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python transcribe.py <video> [model_size]")
        sys.exit(1)
    transcribe(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
