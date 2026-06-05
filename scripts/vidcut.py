"""VidCut orchestrator.

  prep   <video> [model]   transcribe + analyze a full-length video
  reels  <clips.json>      render upload-ready reels from a selection
  digest <video>           print transcript + hot-point digest (for picking)
  list                     list videos in input/ and their prep status
"""
import os
import sys

import config


def cmd_prep(video, model=None):
    import transcribe, analyze
    transcribe.transcribe(video, model)
    analyze.analyze(video)
    print("\nNext: open the digest, choose hot points, write a clips json, then:")
    print(f'  vidcut reels clips\\{config.stem(video)}.clips.json')


def cmd_digest(video):
    work = os.path.join(config.WORK_DIR, config.stem(config.resolve_input(video)))
    for fn in ("peaks.txt", "transcript.txt"):
        p = os.path.join(work, fn)
        print(f"\n===== {fn} =====")
        if os.path.isfile(p):
            print(open(p, encoding="utf-8").read())
        else:
            print(f"(missing - run: vidcut prep {video})")


def cmd_reels(clips_json):
    import make_reels
    make_reels.run(clips_json)


def cmd_list():
    vids = [f for f in os.listdir(config.INPUT_DIR)
            if f.lower().endswith((".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"))]
    if not vids:
        print(f"(no videos in {config.INPUT_DIR})")
        return
    for v in vids:
        work = os.path.join(config.WORK_DIR, config.stem(v))
        prepped = os.path.isfile(os.path.join(work, "transcript.json"))
        print(f"  {'[prepped]' if prepped else '[   new ]'}  {v}")


def main(argv):
    if not argv:
        print(__doc__)
        return
    cmd, rest = argv[0], argv[1:]
    if cmd == "prep":
        cmd_prep(rest[0], rest[1] if len(rest) > 1 else None)
    elif cmd == "digest":
        cmd_digest(rest[0])
    elif cmd == "reels":
        cmd_reels(rest[0])
    elif cmd == "list":
        cmd_list()
    else:
        print(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
