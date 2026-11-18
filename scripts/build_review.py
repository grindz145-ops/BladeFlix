#!/usr/bin/env python3
"""Build the BladeFlix review-queue widget page.

Reads data/pending.json and emits a single self-contained HTML file with an
approve/reject checklist (25 items per page, newest first). Troy taps In/Out
on each item; decisions persist in the widget state bridge, and the parent
agent reads them back with widget.state to publish the approved ones.

Usage:
    python3 scripts/build_review.py
Output:
    ~/workspace/bladeflix-review.html
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = Path.home() / "workspace" / "bladeflix-review.html"

pending = json.load(open(ROOT / "data" / "pending.json"))
items = [
    {
        "id": p["video_id"],
        "title": p.get("title", ""),
        "channel": p.get("channel", ""),
        "published": p.get("published", ""),
        "category": p.get("suggested_category") or "aggressive",
        "tags": p.get("tags") or [],
        "source": p.get("source", ""),
    }
    for p in pending
]

html = """<style>
* { box-sizing: border-box; }
.bf-review { font-family: -apple-system, "Segoe UI", Roboto, sans-serif; color: var(--hatch-widget-text); max-width: 640px; margin: 0 auto; padding: 12px; }
.bf-review h2 { font-size: 18px; margin: 0 0 4px; }
.bf-review .sub { color: var(--hatch-widget-muted); font-size: 13px; margin: 0 0 12px; }
.bf-review .counts { display: flex; gap: 8px; margin-bottom: 12px; font-size: 13px; }
.bf-review .counts span { background: var(--hatch-widget-surface-muted); border: 1px solid var(--hatch-widget-border); border-radius: 999px; padding: 4px 10px; }
.bf-review .counts .in { color: #2e9e5b; }
.bf-review .counts .out { color: #d33; }
.bf-review .row { display: flex; gap: 8px; align-items: flex-start; padding: 10px 8px; border-bottom: 1px solid var(--hatch-widget-border); }
.bf-review .row .info { flex: 1; min-width: 0; }
.bf-review .row .title { font-size: 14px; line-height: 1.3; }
.bf-review .row .title a { color: var(--hatch-widget-text); text-decoration: none; }
.bf-review .row .title a:hover { text-decoration: underline; }
.bf-review .row .meta { font-size: 12px; color: var(--hatch-widget-muted); margin-top: 3px; }
.bf-review .badge { display: inline-block; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.4px; color: var(--hatch-widget-accent); border: 1px solid var(--hatch-widget-accent); border-radius: 3px; padding: 1px 5px; margin-left: 6px; vertical-align: 1px; }
.bf-review .btns { display: flex; flex-direction: column; gap: 6px; flex-shrink: 0; }
.bf-review button { font-family: inherit; cursor: pointer; border-radius: 6px; border: 1px solid var(--hatch-widget-border); background: var(--hatch-widget-surface); color: var(--hatch-widget-text); }
.bf-review .btns button { width: 52px; padding: 6px 0; font-size: 13px; font-weight: 700; }
.bf-review .btns button.on-in { background: #2e9e5b; border-color: #2e9e5b; color: #fff; }
.bf-review .btns button.on-out { background: #d33; border-color: #d33; color: #fff; }
.bf-review .pager { display: flex; justify-content: space-between; align-items: center; margin-top: 14px; }
.bf-review .pager button { padding: 8px 16px; font-size: 14px; }
.bf-review .pager button:disabled { opacity: 0.4; cursor: default; }
.bf-review .pager .pg { font-size: 13px; color: var(--hatch-widget-muted); }
.bf-review .foot { font-size: 12px; color: var(--hatch-widget-muted); margin-top: 10px; }
</style>
<div class="bf-review">
  <h2>Review queue</h2>
  <p class="sub">Newest first. Tap <b>In</b> to publish a video to the feed, <b>Out</b> to reject it. Tap again to clear. When you're done, tell me and I'll publish the approved ones.</p>
  <div class="counts"><span class="in" id="c-in">In: 0</span><span class="out" id="c-out">Out: 0</span><span id="c-left"></span></div>
  <div id="rows"></div>
  <div class="pager">
    <button id="prev" type="button">&larr; Prev</button>
    <span class="pg" id="pg"></span>
    <button id="next" type="button">Next &rarr;</button>
  </div>
  <p class="foot">Titles link out to YouTube so you can watch before deciding. Your taps are saved as you go.</p>
</div>
<script>
const ITEMS = """ + json.dumps(items) + """;
const PAGE_SIZE = 25;
const TOTAL_PAGES = Math.max(1, Math.ceil(ITEMS.length / PAGE_SIZE));
let state = window.hatchWidget.getState({ decisions: {}, page: 0 });
if (state.page >= TOTAL_PAGES) state.page = 0;

function esc(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function render() {
  const d = state.decisions || {};
  let nIn = 0, nOut = 0;
  for (const k in d) { if (d[k] === "in") nIn++; else if (d[k] === "out") nOut++; }
  document.getElementById("c-in").textContent = "In: " + nIn;
  document.getElementById("c-out").textContent = "Out: " + nOut;
  document.getElementById("c-left").textContent = "Left: " + (ITEMS.length - nIn - nOut) + " of " + ITEMS.length;
  document.getElementById("pg").textContent = "Page " + (state.page + 1) + " of " + TOTAL_PAGES;
  document.getElementById("prev").disabled = state.page <= 0;
  document.getElementById("next").disabled = state.page >= TOTAL_PAGES - 1;

  const slice = ITEMS.slice(state.page * PAGE_SIZE, (state.page + 1) * PAGE_SIZE);
  document.getElementById("rows").innerHTML = slice.map(it => {
    const dec = d[it.id] || "";
    const tags = it.tags.length ? " &middot; " + it.tags.map(esc).join(", ") : "";
    return '<div class="row"><div class="info"><div class="title"><a href="https://www.youtube.com/watch?v=' + esc(it.id) + '" target="_blank" rel="noopener">' + esc(it.title) + '</a><span class="badge">' + esc(it.category) + '</span></div>' +
      '<div class="meta">' + esc(it.channel) + " &middot; " + esc(it.published) + tags + '</div></div>' +
      '<div class="btns"><button type="button" data-id="' + esc(it.id) + '" data-v="in" class="' + (dec === "in" ? "on-in" : "") + '">In</button>' +
      '<button type="button" data-id="' + esc(it.id) + '" data-v="out" class="' + (dec === "out" ? "on-out" : "") + '">Out</button></div></div>';
  }).join("");
}

document.getElementById("rows").addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-id]");
  if (!btn) return;
  const id = btn.getAttribute("data-id"), v = btn.getAttribute("data-v");
  const d = Object.assign({}, state.decisions || {});
  if (d[id] === v) delete d[id]; else d[id] = v;
  state = { decisions: d, page: state.page };
  window.hatchWidget.setState(state);
  render();
});
document.getElementById("prev").addEventListener("click", () => {
  if (state.page > 0) { state = { decisions: state.decisions || {}, page: state.page - 1 }; window.hatchWidget.setState(state); render(); }
});
document.getElementById("next").addEventListener("click", () => {
  if (state.page < TOTAL_PAGES - 1) { state = { decisions: state.decisions || {}, page: state.page + 1 }; window.hatchWidget.setState(state); render(); }
});
window.addEventListener("hatch-widget-state", (e) => { if (e.detail && e.detail.state) { state = e.detail.state; render(); } });
render();
</script>
"""
OUT.write_text(html)
print(f"review widget written: {OUT} ({len(html)} bytes, {len(items)} items)")
