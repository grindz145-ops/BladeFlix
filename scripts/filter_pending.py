#!/usr/bin/env python3
"""Pre-review filter for the BladeFlix pending queue.

Troy's standing order (2026-11-21): before ANY review list is shown to him,
filter out vertical videos and obviously topical non-edits (videos about a
new skate, types of grinds, gear talk, tutorials, reviews, teasers, ...).

Usage: python3 scripts/filter_pending.py [--dry-run]

- Fetches width/height/duration via yt-dlp for every pending video.
- Removes: vertical (height > width), under 2 minutes, or a title matching
  NON_EDIT_RE from fetch_feed.py (the same intake filter, so the two stay
  in sync).
- Videos whose metadata can't be fetched are KEPT (can't judge) and listed
  in the output so a human can check them.
- Removed videos are logged to data/filtered-<date>.json with their reason,
  and their IDs go into data/rejected.json so the updater won't re-queue them.
"""

import argparse
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from fetch_feed import NON_EDIT_RE  # noqa: E402

DATA = HERE.parent / "data"
MIN_DURATION_S = 120  # "nothing under a minute or two" (Troy, 2026-11-19)


def fetch_metadata(video_ids):
    """Return {video_id: {width, height, duration}} via one yt-dlp call."""
    import tempfile

    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        for vid in video_ids:
            f.write(f"https://www.youtube.com/watch?v={vid}\n")
        list_path = f.name
    proc = subprocess.run(
        [
            sys.executable, "-m", "yt_dlp", "--dump-json", "--no-playlist",
            "--no-warnings", "--skip-download", "-a", list_path,
        ],
        capture_output=True, text=True, timeout=1200,
    )
    meta = {}
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        meta[d["id"]] = {
            "width": d.get("width"),
            "height": d.get("height"),
            "duration": d.get("duration"),
        }
    return meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    pending = json.loads((DATA / "pending.json").read_text())
    rejected = json.loads((DATA / "rejected.json").read_text())
    rejected_set = set(rejected)

    meta = fetch_metadata([v["video_id"] for v in pending])

    removed, kept, no_meta = [], [], []
    for v in pending:
        vid = v["video_id"]
        reasons = []
        if NON_EDIT_RE.search(v["title"]):
            reasons.append("topical/non-edit title")
        m = meta.get(vid)
        if m is None:
            no_meta.append(v)
        else:
            w, h, dur = m["width"], m["height"], m["duration"]
            if w and h and h > w:
                reasons.append(f"vertical {w}x{h}")
            if dur is not None and dur < MIN_DURATION_S:
                reasons.append(f"{dur}s (< {MIN_DURATION_S}s)")
        if reasons:
            removed.append({**v, "filter_reason": "; ".join(reasons),
                            "meta": m})
        else:
            kept.append(v)

    print(f"pending: {len(pending)} | removed: {len(removed)} "
          f"| kept: {len(kept)} | no metadata (kept): {len(no_meta)}")
    for v in removed:
        print(f"  OUT {v['video_id']} [{v['filter_reason']}] "
              f"{v['channel']} | {v['title'][:60]}")
    for v in no_meta:
        print(f"  KEEP (no metadata) {v['video_id']} "
              f"{v['channel']} | {v['title'][:60]}")

    if args.dry_run:
        print("dry run: no files changed")
        return

    log_path = DATA / f"filtered-{date.today().isoformat()}.json"
    log_path.write_text(json.dumps(removed, indent=2))
    (DATA / "pending.json").write_text(json.dumps(kept, indent=2))
    new_rejected = [v["video_id"] for v in removed
                    if v["video_id"] not in rejected_set]
    rejected.extend(new_rejected)
    (DATA / "rejected.json").write_text(json.dumps(rejected, indent=2))
    print(f"wrote {log_path.name} ({len(removed)} entries), "
          f"pending.json ({len(kept)}), rejected.json (+{len(new_rejected)})")


if __name__ == "__main__":
    main()
