// BladeFlix — renders everything from data/videos.json at runtime.
// No video lists are hardcoded here.

const CATEGORY_LABELS = {
  aggressive: "Aggressive",
  wizard: "Wizard",
  urban: "Urban",
  contest: "Contest",
  movies: "Movies",
  podcasts: "Podcasts",
  vlogs: "Vlogs",
};

// Categories hidden from the default "All" view (Troy, 2026-11-22):
// podcasts and vlogs only show under their own tabs, never in the main
// feed.
const HIDDEN_FROM_ALL = new Set(["podcasts", "vlogs"]);

let videos = [];
let activeCategory = "all";
let activeTags = new Set();
let searchQuery = "";

// Pagination: default 20 videos per page, remembered across visits.
let pageSize = 20;
try {
  const saved = localStorage.getItem("bladeflix-page-size");
  if (saved === "all") pageSize = Infinity;
  else if (saved && !isNaN(parseInt(saved, 10))) pageSize = parseInt(saved, 10);
} catch (e) { /* private mode — just use the default */ }
let visibleCount = pageSize;

const gridEl = document.getElementById("grid");
const tagChipsEl = document.getElementById("tag-chips");
const resultCountEl = document.getElementById("result-count");
const emptyEl = document.getElementById("empty");
const searchEl = document.getElementById("search");
const pageSizeEl = document.getElementById("page-size");
const loadMoreEl = document.getElementById("load-more");
const modalEl = document.getElementById("modal");
const playerEl = document.getElementById("player");
const modalTitleEl = document.getElementById("modal-title");
const modalMetaEl = document.getElementById("modal-meta");
const modalLinkEl = document.getElementById("modal-link");

function formatDate(iso, approx) {
  const d = new Date(iso + "T12:00:00"); // noon avoids TZ day shifts
  const s = d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
  return approx ? "~" + s : s;
}

// Effective date: the original production date when a video was backdated
// (vintage re-uploads), else the YouTube upload date. Sorting and display
// both use this, so a 2003 film sits with 2003-era content, not 2026 uploads.
function effDate(v) {
  return v.original_date || v.published;
}

// Display date: year-only when we only know the year, month+year when we
// only know the month, else the full date. Never shows a fake precise day.
function displayDate(v) {
  if (v.original_date && v.original_date_precision === "year") {
    return v.original_date.slice(0, 4);
  }
  if (v.original_date && v.original_date_precision === "month") {
    const d = new Date(v.original_date + "T12:00:00");
    return d.toLocaleDateString("en-US", { month: "short", year: "numeric" });
  }
  return formatDate(effDate(v), v.date_approx);
}

function thumbUrl(id) {
  return "https://i.ytimg.com/vi/" + id + "/mqdefault.jpg";
}

function cardHtml(v) {
  const badge = v.category === "movies"
    ? '<span class="badge movie">Full length</span>'
    : '<span class="badge">' + CATEGORY_LABELS[v.category] + "</span>";
  const duration = v.duration ? '<span class="duration">' + escapeHtml(v.duration) + "</span>" : "";
  const tags = v.tags.map(t => '<span class="tag">' + escapeHtml(t) + "</span>").join("");
  return (
    '<article class="card" tabindex="0" role="button" data-video-id="' + v.video_id + '" aria-label="Play ' + escapeHtml(v.title) + '">' +
      '<div class="thumb-wrap">' +
        '<img src="' + thumbUrl(v.video_id) + '" alt="" loading="lazy">' + badge + duration +
      "</div>" +
      '<div class="card-body">' +
        '<h3 class="card-title">' + escapeHtml(v.title) + "</h3>" +
        '<p class="card-meta">' + escapeHtml(v.channel) + " &middot; " + displayDate(v) + "</p>" +
        '<div class="card-tags">' + tags + "</div>" +
      "</div>" +
    "</article>"
  );
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function matchesFilters(v) {
  if (activeCategory !== "all" && v.category !== activeCategory) return false;
  if (activeCategory === "all" && HIDDEN_FROM_ALL.has(v.category)) return false;
  if (activeTags.size > 0 && !v.tags.some(t => activeTags.has(t))) return false;
  if (searchQuery) {
    const hay = (v.title + " " + v.channel).toLowerCase();
    if (!hay.includes(searchQuery)) return false;
  }
  return true;
}

function render() {
  const filtered = videos.filter(matchesFilters);
  const shown = filtered.slice(0, visibleCount);
  gridEl.innerHTML = shown.map(cardHtml).join("");
  emptyEl.hidden = filtered.length > 0;
  loadMoreEl.hidden = filtered.length <= visibleCount;

  // The "total" for the count line is the size of the current view: the
  // default feed (hidden categories excluded) for All, the category size
  // otherwise.
  const total = activeCategory === "all"
    ? videos.filter(v => !HIDDEN_FROM_ALL.has(v.category)).length
    : videos.filter(v => v.category === activeCategory).length;
  const label = activeCategory === "all" ? "videos" : CATEGORY_LABELS[activeCategory].toLowerCase() + " videos";
  if (filtered.length === total && shown.length === filtered.length) {
    resultCountEl.textContent = total + " " + label;
  } else if (shown.length === filtered.length) {
    resultCountEl.textContent = filtered.length + " of " + total + " " + label;
  } else {
    resultCountEl.textContent = "Showing " + shown.length + " of " + filtered.length + " " + label;
  }
}

// Any filter change starts back at the first page.
function resetAndRender() {
  visibleCount = pageSize;
  render();
}

function renderTagChips() {
  const tags = [...new Set(videos.flatMap(v => v.tags))].sort();
  tagChipsEl.innerHTML = tags.map(t =>
    '<button class="chip" data-tag="' + escapeHtml(t) + '">' + escapeHtml(t) + "</button>"
  ).join("");
}

function openModal(videoId) {
  const v = videos.find(x => x.video_id === videoId);
  if (!v) return;
  playerEl.src = "https://www.youtube.com/embed/" + videoId + "?autoplay=1&rel=0";
  modalTitleEl.textContent = v.title;
  modalMetaEl.textContent = v.channel + " · " + displayDate(v) +
    (v.duration ? " · " + v.duration : "");
  modalLinkEl.href = "https://www.youtube.com/watch?v=" + videoId;
  modalEl.hidden = false;
  document.body.style.overflow = "hidden";
}

function closeModal() {
  playerEl.src = ""; // stops playback
  modalEl.hidden = true;
  document.body.style.overflow = "";
}

// --- Events ---
document.querySelectorAll(".tab").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    activeCategory = btn.dataset.category;
    resetAndRender();
  });
});

tagChipsEl.addEventListener("click", e => {
  const chip = e.target.closest(".chip");
  if (!chip) return;
  const tag = chip.dataset.tag;
  if (activeTags.has(tag)) {
    activeTags.delete(tag);
    chip.classList.remove("active");
  } else {
    activeTags.add(tag);
    chip.classList.add("active");
  }
  resetAndRender();
});

searchEl.addEventListener("input", () => {
  searchQuery = searchEl.value.trim().toLowerCase();
  resetAndRender();
});

pageSizeEl.value = pageSize === Infinity ? "all" : String(pageSize);
pageSizeEl.addEventListener("change", () => {
  pageSize = pageSizeEl.value === "all" ? Infinity : parseInt(pageSizeEl.value, 10);
  try { localStorage.setItem("bladeflix-page-size", pageSizeEl.value); } catch (e) { /* ignore */ }
  resetAndRender();
});

loadMoreEl.addEventListener("click", () => {
  visibleCount += pageSize;
  render();
});

document.addEventListener("click", e => {
  const card = e.target.closest(".card");
  if (card) { openModal(card.dataset.videoId); return; }
  if (e.target.closest("[data-close]")) closeModal();
});

document.addEventListener("keydown", e => {
  if (e.key === "Escape" && !modalEl.hidden) closeModal();
  if (e.key === "Enter") {
    const card = e.target.closest && e.target.closest(".card");
    if (card) openModal(card.dataset.videoId);
  }
});

// --- Boot ---
fetch("data/videos.json")
  .then(r => {
    if (!r.ok) throw new Error("Failed to load videos.json: " + r.status);
    return r.json();
  })
  .then(data => {
    videos = data.slice().sort((a, b) => effDate(b).localeCompare(effDate(a)));
    renderTagChips();
    render();
  })
  .catch(err => {
    gridEl.innerHTML = "<p>Couldn’t load the video feed. Try refreshing the page.</p>";
    console.error(err);
  });
