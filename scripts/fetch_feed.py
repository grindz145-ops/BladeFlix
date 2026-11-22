#!/usr/bin/env python3
"""BladeFlix feed updater.

Reads data/channels.json, fetches each channel's YouTube RSS feed
(no API key needed), and appends videos that are not already in
data/videos.json, data/pending.json or data/rejected.json to
data/pending.json — the curation queue. Nothing goes live
automatically; a human moves approved items from pending.json to
videos.json with tags, and puts rejected video IDs in
data/rejected.json (a plain list of video IDs) so they are never
re-queued.

Idempotent: running it twice in a row adds nothing the second time.
Safe to run on a schedule (e.g. daily cron).

Intake filters (Troy's curation rules, 2026-11-18): the main feed is last
12 months only, so entries published before CUTOFF_DATE are skipped
unless the title looks like a full-length film (Movies library is
exempt). Entries whose titles read as tutorials, podcasts, reviews,
interviews, vlogs or unboxings are skipped — full edits only. Skipped
entries are NOT added to rejected.json, so a future rule change can
still surface them; entries Troy rejects by hand go in rejected.json
and are never re-queued.

Podcasts (Troy, 2026-11-22) live in their own category, hidden from the
default All view on the site. Channels flagged "podcast" in channels.json
post podcast episodes only — every new upload queues as podcasts, exempt
from the cutoff and the NON_EDIT_RE filter. Channels with a
"podcast_titles" regex queue matching titles as podcasts and run the
rest through the normal rules — unless "podcast_only" is set, which
skips non-matching uploads entirely (e.g. Endless Blading Co., where
only the Endless Blading Show belongs on BladeFlix).

Vlogs (Troy, 2026-11-22) work the same way in their own category,
also hidden from the default All view. Channels flagged "vlog" queue
every new upload as vlogs; "vlog_titles" regex queues matching titles
as vlogs (e.g. Hawke Trackler's Tiny series, CJ Wellsmore's Do The
Thing Diaries); "vlog_only" skips non-matching uploads entirely.

Channel IDs live in channels.json. To resolve a new @handle to its
channel ID: yt-dlp --print "%(channel_id)s" --playlist-end 1
https://www.youtube.com/<handle>/videos

Usage:
    python3 scripts/fetch_feed.py
"""

import json
import re
import sys
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

# Main feed is last 12 months only (Troy, 2026-11-18). Movies library
# is exempt — full-length films are queued whatever their date.
CUTOFF_DATE = "2025-11-19"

# Full edits only (Troy, 2026-11-18): skip tutorials, podcasts,
# reviews, interviews, vlogs, unboxings and beginner guides.
# Extended 2026-11-19 for Mushroom Blading / Flow Skate noise: gear
# revisits, commentary tracks, gear tests, lessons, manifestos.
NON_EDIT_RE = re.compile(
    r"how to|tutorial|podcast|unboxing|interview|\breviews?\b|vlog|beginner"
    r"|revisit|commentary|\btesting\b|\blesson\b|manifesto"
    r"|setups?|teaser|trailer|stream test|worth it|grind position|every grind",
    re.IGNORECASE,
)

# Contest videos get their own category (Troy, 2026-11-18). "Comp" means
# competition (Troy, 2026-11-19) — matched as a whole word so "company"
# and "compilation" don't trigger it. Compound tags like "bladingcup"
# and "skatecomp" have no word boundary, so they match as substrings.
# "Grand Prix" is Sven Boekhorst's contest series (added 2026-11-19).
# "Cash for tricks" is a contest format (added 2026-11-19).
CONTEST_RE = re.compile(
    r"\b(contest|championship|champs|invitational|classic|comp|cup|grand prix|cash for tricks)s?\b"
    r"|bladingcup|skatecomp",
    re.IGNORECASE,
)
FULL_LENGTH_RE = re.compile(
    r"full video|full-length|full length|full movie|full film|documentary",
    re.IGNORECASE,
)

ROOT = Path(__file__).resolve().parent.parent
CHANNELS_PATH = ROOT / "data" / "channels.json"
VIDEOS_PATH = ROOT / "data" / "videos.json"
PENDING_PATH = ROOT / "data" / "pending.json"
REJECTED_PATH = ROOT / "data" / "rejected.json"

RSS_URL = "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
USER_AGENT = "BladeFlix feed updater"
TIMEOUT_SECONDS = 20

ATOM_NS = "{http://www.w3.org/2005/Atom}"
YT_NS = "{http://www.youtube.com/xml/schemas/2015}"


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except json.JSONDecodeError as exc:
        print(f"ERROR: {path} is not valid JSON: {exc}", file=sys.stderr)
        raise


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def parse_feed(xml_text):
    """Parse a YouTube channel RSS (Atom) feed into a list of entries.

    Each entry: {"video_id": str, "title": str, "published": "YYYY-MM-DD"}.
    Entries missing a video ID are skipped.
    """
    entries = []
    root = ET.fromstring(xml_text)
    for entry in root.findall(f"{ATOM_NS}entry"):
        video_id_el = entry.find(f"{YT_NS}videoId")
        title_el = entry.find(f"{ATOM_NS}title")
        published_el = entry.find(f"{ATOM_NS}published")
        if video_id_el is None or not video_id_el.text:
            continue
        published = ""
        if published_el is not None and published_el.text:
            published = published_el.text[:10]  # ISO datetime -> date
        entries.append({
            "video_id": video_id_el.text.strip(),
            "title": title_el.text.strip() if title_el is not None and title_el.text else "",
            "published": published,
        })
    return entries


def fetch_channel_feed(channel_id):
    """Fetch one channel's RSS feed over HTTPS. Returns raw XML text."""
    url = RSS_URL.format(channel_id=channel_id)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
        return resp.read().decode("utf-8")


def main():
    channels = load_json(CHANNELS_PATH, [])
    videos = load_json(VIDEOS_PATH, [])
    pending = load_json(PENDING_PATH, [])
    rejected = load_json(REJECTED_PATH, [])

    known_ids = {v.get("video_id") for v in videos}
    known_ids |= {p.get("video_id") for p in pending}
    known_ids |= set(rejected)

    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    added = 0
    skipped_no_id = []
    failed = []

    for channel in channels:
        name = channel.get("name", "?")
        channel_id = channel.get("channel_id")
        if not channel_id:
            skipped_no_id.append(name)
            continue
        try:
            entries = parse_feed(fetch_channel_feed(channel_id))
        except (urllib.error.URLError, ET.ParseError, TimeoutError) as exc:
            failed.append(f"{name}: {exc}")
            continue

        for entry in entries:
            video_id = entry["video_id"]
            if video_id in known_ids:
                continue
            # Podcast handling (Troy, 2026-11-22): channels flagged
            # "podcast" post podcast episodes only — every new upload
            # queues as podcasts, exempt from the cutoff and the
            # NON_EDIT_RE filter (podcasts are topical by nature).
            # Channels with "podcast_titles" queue matching titles as
            # podcasts and run the rest through the normal rules —
            # unless "podcast_only" is set, which skips non-matching
            # uploads entirely.
            title = entry["title"]
            is_podcast_channel = channel.get("podcast") is True
            podcast_titles_re = channel.get("podcast_titles")
            is_podcast_title = bool(podcast_titles_re) and bool(
                re.search(podcast_titles_re, title, re.IGNORECASE))
            is_vlog_channel = channel.get("vlog") is True
            vlog_titles_re = channel.get("vlog_titles")
            is_vlog_title = bool(vlog_titles_re) and bool(
                re.search(vlog_titles_re, title, re.IGNORECASE))
            if is_podcast_channel or is_podcast_title:
                suggested_category = "podcasts"
            elif channel.get("podcast_only") is True:
                continue
            elif is_vlog_channel or is_vlog_title:
                suggested_category = "vlogs"
            elif channel.get("vlog_only") is True:
                continue
            else:
                # Intake filters (Troy's curation rules): last 12 months
                # only, unless it looks like a full-length film; no
                # tutorials, podcasts, reviews, interviews or vlogs.
                published = entry.get("published", "")
                if published and published < CUTOFF_DATE and not FULL_LENGTH_RE.search(title):
                    continue
                if NON_EDIT_RE.search(title):
                    continue
                # Contest videos get their own category (Troy, 2026-11-18).
                if CONTEST_RE.search(title):
                    suggested_category = "contest"
                else:
                    suggested_category = channel.get("default_category", "aggressive")
            pending.append({
                "video_id": video_id,
                "title": entry["title"],
                "channel": name,
                "channel_handle": channel.get("handle"),
                "published": entry["published"],
                "suggested_category": suggested_category,
                "tags": [],
                "fetched_at": fetched_at,
            })
            known_ids.add(video_id)
            added += 1

    # Newest first, so the queue reads like a feed.
    pending.sort(key=lambda p: p.get("published", ""), reverse=True)
    save_json(PENDING_PATH, pending)

    print(f"Channels checked: {len(channels) - len(skipped_no_id) - len(failed)}")
    if skipped_no_id:
        print(f"Skipped (no channel_id in channels.json): {', '.join(skipped_no_id)}")
    if failed:
        print(f"Failed to fetch: {'; '.join(failed)}")
    print(f"New videos queued in pending.json: {added}")
    print(f"Pending queue size: {len(pending)}")


if __name__ == "__main__":
    main()
