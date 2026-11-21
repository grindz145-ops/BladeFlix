#!/usr/bin/env python3
"""Apply Troy's review-queue decisions to the BladeFlix data files.

Usage:
    python3 scripts/apply_review.py <decisions.json>

decisions.json: {"<video_id>": "in"|"out", ...} — from the review widget's
durable state (widget.state / runtime.widgets.state_bundle_json).

- "in":  move the pending entry to videos.json (category = suggested_category)
- "out": add the video_id to rejected.json (flat list of IDs)
- undecided items stay in pending.json

Prints counts and any decision IDs not found in pending.json.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

decisions = json.load(open(sys.argv[1]))
videos = json.load(open(DATA / "videos.json"))
pending = json.load(open(DATA / "pending.json"))
rejected = json.load(open(DATA / "rejected.json"))

live_ids = {v["video_id"] for v in videos}
rejected_set = set(rejected)
by_id = {p["video_id"]: p for p in pending}

added, dropped, unknown, already_live = [], [], [], []
for vid, choice in decisions.items():
    if vid not in by_id:
        unknown.append(vid)
        continue
    if choice == "in":
        if vid in live_ids:
            already_live.append(vid)
            continue
        p = by_id[vid]
        entry = {
            "category": p.get("suggested_category") or "aggressive",
            "channel": p.get("channel", ""),
            "published": p.get("published", ""),
            "tags": p.get("tags") or [],
            "title": p.get("title", ""),
            "video_id": vid,
        }
        if p.get("channel_handle"):
            entry["channel_handle"] = p["channel_handle"]
        videos.append(entry)
        live_ids.add(vid)
        added.append(vid)
    elif choice == "out":
        if vid not in rejected_set:
            rejected.append(vid)
            rejected_set.add(vid)
        dropped.append(vid)

decided = set(decisions)
remaining = [p for p in pending if p["video_id"] not in decided]

# Keep live feed newest-first by effective date (original_date when
# backdated, else published).
videos.sort(key=lambda v: v.get("original_date") or v.get("published", ""), reverse=True)

json.dump(videos, open(DATA / "videos.json", "w"), indent=1)
json.dump(remaining, open(DATA / "pending.json", "w"), indent=1)
json.dump(rejected, open(DATA / "rejected.json", "w"), indent=1)

print(f"decisions: {len(decisions)} (in: {len(added)}, out: {len(dropped)})")
print(f"live: {len(videos)}, pending: {len(remaining)}, rejected: {len(rejected)}")
if unknown:
    print(f"UNKNOWN IDs (not in pending): {unknown}")
if already_live:
    print(f"already live, skipped: {already_live}")
