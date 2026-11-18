#!/usr/bin/env python3
"""Build a single-file BladeFlix preview for the in-chat widget.

Inlines styles.css, app.js (with videos.json embedded instead of fetched),
and drops the YouTube iframe player (widgets don't allow iframes — the
preview modal links out to YouTube instead). The real site is unaffected.

Usage:
    python3 scripts/build_preview.py
Output:
    ~/workspace/bladeflix-preview.html
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = Path.home() / "workspace" / "bladeflix-preview.html"

css = (ROOT / "styles.css").read_text()
js = (ROOT / "app.js").read_text()
videos = json.load(open(ROOT / "data" / "videos.json"))

boot_start = js.index("// --- Boot ---")
js = js[:boot_start] + """// --- Boot (preview: data embedded) ---
videos = VIDEOS.slice().sort((a, b) => b.published.localeCompare(a.published));
renderTagChips();
render();
"""

css = css.replace("position: sticky;", "position: relative;")
# Drop the player CSS (no iframe in the widget preview).
css = css.replace(".player-wrap iframe { position: absolute; inset: 0; width: 100%; height: 100%; }\n", "")
css = css.replace(".player-wrap { position: relative; aspect-ratio: 16 / 9; background: #000; border-radius: 4px; overflow: hidden; }\n", "")
css += """
.wordmark { font-family: 'Arial Narrow', Arial, sans-serif; font-weight: 900; font-size: 30px; letter-spacing: 1px; color: #e50914; text-decoration: none; line-height: 1; display: inline-block; transform: scaleY(1.15); }
@media (max-width: 640px) { .wordmark { font-size: 24px; } }
"""

html = """<style>""" + css + """</style>
<div class="bf-preview">
  <header class="site-header">
    <div class="header-inner">
      <a class="logo-link" href="#" aria-label="BladeFlix home"><span class="wordmark">BLADEFLIX</span></a>
      <nav class="tabs" aria-label="Categories">
        <button class="tab active" data-category="all">All</button>
        <button class="tab" data-category="aggressive">Aggressive</button>
        <button class="tab" data-category="wizard">Wizard</button>
        <button class="tab" data-category="urban">Urban</button>
        <button class="tab" data-category="contest">Contest</button>
        <button class="tab" data-category="movies">Movies</button>
      </nav>
      <div class="search-wrap">
        <input id="search" type="search" placeholder="Search videos…" aria-label="Search videos">
      </div>
    </div>
  </header>

  <main class="main">
    <section class="filters">
      <div id="tag-chips" class="tag-chips" aria-label="Filter by tag"></div>
      <p id="result-count" class="result-count"></p>
    </section>

    <section id="grid" class="grid" aria-live="polite"></section>
    <p id="empty" class="empty" hidden>No videos match these filters.</p>
  </main>

  <footer class="site-footer">
    <p>BladeFlix is a curated index of rollerblading videos. All videos are embedded from YouTube and belong to their creators.</p>
  </footer>

  <div id="modal" class="modal" hidden>
    <div class="modal-backdrop" data-close></div>
    <div class="modal-box" role="dialog" aria-modal="true" aria-labelledby="modal-title">
      <button class="modal-close" data-close aria-label="Close">&times;</button>
      <h3 id="modal-title"></h3>
      <p id="modal-meta"></p>
      <a id="modal-link" href="#" target="_blank" rel="noopener">Watch on YouTube ↗</a>
    </div>
  </div>
</div>
<script>
const VIDEOS = """ + json.dumps(videos) + """;
""" + js + """
</script>
"""
OUT.write_text(html)
print(f"preview written: {OUT} ({len(html)} bytes, {len(videos)} videos)")
