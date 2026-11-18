# BladeFlix

A curated aggregator of the newest aggressive rollerblading videos — plus wizard
and urban skating — primarily free videos on YouTube, with a full-length movie
library. Static site, no build step, GitHub Pages-ready.

## Layout

```
index.html          Site shell: header, category tabs, search, grid, player modal
styles.css          Dark Netflix-style theme (#141414 bg, #E50914 accent)
app.js              Renders everything from data/videos.json at runtime
images/
  logo.png          BladeFlix wordmark (header)
  favicon.png       Square favicon (cropped "B")
data/
  channels.json     Channels to aggregate [{name, handle, channel_id, default_category, notes}]
  sources.json      Every channel referenced by the roundup shows (and direct
                    requests), with first-reference info and reference counts
  videos.json       Curated live feed [{video_id, title, channel, channel_handle,
                    published, category, tags[], duration?}]
  pending.json      Curation queue — new uploads waiting for approval
  rejected.json     Video IDs Troy rejected; the updater never re-queues these
scripts/
  fetch_feed.py     Updater: pulls new uploads from YouTube RSS into pending.json
```

## Categories & tags

Categories: `aggressive`, `wizard`, `urban`, `contest`, `movies` (full-length
films). Contest coverage has its own category (Troy, 2026-11-18); do not use
the `contest` tag — the category covers it.

Tags: `street`, `park`, `vert`, `mushroom`, `big-wheel`, `documentary`,
`edit`. (`vlog`, `review`, `tutorial` are retired — those videos are excluded
by the full-edits-only rule.)

## The curation flow

**Rule (Troy, 2026-11-18): the main feed is last 12 months only.** Aggressive /
wizard / urban videos older than 12 months do not belong in `videos.json` or
`pending.json`. The Movies library is exempt — classics are the point of it.
Troy curates personally until the feed is well defined: high signal-to-noise,
nothing goes live without his approval. **Full edits only** — no vlogs,
tutorials/how-tos, reviews, podcasts, or topical/discussion videos about
rollerblading, at least for now. Contest coverage is kept (Troy, 2026-11-18);
documentaries are still undecided. Other borderline categories get run by
Troy for a yes/no.

1. **Fetch.** Run the updater (or let the schedule run it):
   ```
   python3 scripts/fetch_feed.py
   ```
   It reads `data/channels.json`, fetches each channel's YouTube RSS feed
   (no API key needed), and appends videos not already in `videos.json`,
   `pending.json` or `rejected.json` to `pending.json`, with a suggested
   category (the channel's default) and empty tags. It is idempotent —
   running it twice adds nothing the second time. Channels with
   `channel_id: null` are skipped; the RSS endpoint needs the channel ID,
   not the @handle. Add the ID to `channels.json` and the channel is picked
   up on the next run. The `bladeflix-feed-watch` cron runs this daily
   (~09:45 local) and reports new queue items to Troy; it stays silent
   when nothing new appears.

2. **Review.** Look through `data/pending.json`. For each video, decide the
   category (fix the suggestion if it's wrong) and add tags.

3. **Approve.** Move approved items into `data/videos.json` with their final
   category and tags, and remove them from `pending.json`. For rejected
   items, delete them from `pending.json` AND add their video IDs to
   `data/rejected.json` (a plain list) — the updater skips rejected IDs, so
   they are never re-queued.

4. **Publish.** Commit and push; GitHub Pages serves the static files as-is.

## Adding a channel

Add an entry to `data/channels.json` with the verified @handle and the
channel ID. To resolve a @handle to its channel ID:
```
yt-dlp --print "%(channel_id)s" --playlist-end 1 https://www.youtube.com/<handle>/videos
```
Without an ID the channel is listed but the updater skips it.

## Sources database (`data/sources.json`)

Every channel referenced by the roundup shows (This Week in Blade, Tom
Moyse's channel — "Spotty Dog" — and direct requests like Bacemint) is
recorded here: name, handle, channel ID, default category, which show and
episode first referenced it, when it was first seen, and how many of its
videos were referenced. The list is sorted by reference count, highest
first. Every source channel is also in `data/channels.json` so the daily
updater checks it for new edits — with one deliberate exception: VICE
Sports (source of the "Who Killed Rollerblading?" documentary) is a
general sports channel, so adding it would flood the queue with
non-blading videos; it stays in `sources.json` only. The two roundup shows
themselves are not in `channels.json`: their uploads are news roundups,
not edits, so the updater would only queue items Troy would reject.

## Notes

- Dates marked `date_approx: true` in `videos.json` were derived from
  relative times ("3 weeks ago") or article dates rather than an exact
  publish date; the site shows them with a `~` prefix.
- All videos are embedded from YouTube and belong to their creators. The
  footer on the site says so, and every card links out to the original.
