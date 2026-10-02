'use strict';
/**
 * Client-side interactivity — no libraries, no page reloads.
 * Each block guards on the presence of its target element so this single
 * file can be shared across all five server-rendered pages safely.
 */

// ─── Sortable data tables (dashboard leaderboard, outliers table) ─────────
// Any <table class="sortable-table"> with <th data-sort data-type> headers
// and matching <td data-value> cells gets click-to-sort for free.
(function initSortableTables() {
  document.querySelectorAll('.sortable-table').forEach((table) => {
    const tbody = table.querySelector('tbody');
    const headers = table.querySelectorAll('th[data-sort]');

    headers.forEach((th, colIndex) => {
      th.addEventListener('click', () => {
        const type = th.dataset.type || 'string';
        const asc = !th.classList.contains('sorted-asc');

        headers.forEach((h) => h.classList.remove('sorted-asc', 'sorted-desc'));
        th.classList.add(asc ? 'sorted-asc' : 'sorted-desc');

        const rows = Array.from(tbody.querySelectorAll('tr'));
        rows.sort((rowA, rowB) => {
          const a = rowA.children[colIndex].dataset.value;
          const b = rowB.children[colIndex].dataset.value;
          const cmp = type === 'number'
            ? parseFloat(a) - parseFloat(b)
            : a.localeCompare(b);
          return asc ? cmp : -cmp;
        });

        rows.forEach((r) => tbody.appendChild(r));
      });
    });
  });
})();

// ─── Artists page: a glowing "equalizer" bar chart ────────────────────────
// Bar height is a real, comparable measurement (barPct, 0-100 relative to
// the top Z-score) — this is a chart you can actually read values off of,
// just styled like a music equalizer instead of a plain grey bar chart.
// With no genre picked, shows the top-20-overall; picking a genre swaps in
// every artist in that genre instead (regardless of overall rank).
(function initArtistEqualizer() {
  const container = document.getElementById('artist-equalizer');
  const genreFilter = document.getElementById('genre-filter');
  const data = window.__ARTIST_CONSTELLATION__;
  if (!container || !genreFilter || !data) return;

  function render(items) {
    container.innerHTML = '';
    items.forEach((a, i) => {
      const col = document.createElement('div');
      col.className = 'eq-col';
      col.style.setProperty('--i', i);
      col.title = `#${a.rank} ${a.name} — ${a.genre}: ${a.z}x more extreme than typical (top ${a.topPct}% of the genre)`;

      const value = document.createElement('span');
      value.className = 'eq-value';
      value.textContent = `+${Math.round(a.z * 10) / 10}`;

      const bar = document.createElement('div');
      bar.className = 'eq-bar';
      bar.style.setProperty('--h', `${Math.max(a.barPct, 6)}%`);

      const rank = document.createElement('span');
      rank.className = 'eq-rank';
      rank.textContent = `#${a.rank}`;

      const name = document.createElement('span');
      name.className = 'eq-name';
      name.textContent = a.name;

      col.append(value, bar, rank, name);
      container.appendChild(col);
    });
  }

  const top20 = data.filter((a) => a.rank <= 20);
  render(top20);

  genreFilter.addEventListener('change', () => {
    const value = genreFilter.value;
    render(value ? data.filter((a) => a.genre === value) : top20);
  });
})();

// ─── Mood atlas: toggle baseline overlay polygon on every radar chart ─────
(function initBaselineToggle() {
  const btn = document.getElementById('baseline-toggle');
  if (!btn) return;

  btn.addEventListener('click', () => {
    const polygons = document.querySelectorAll('.baseline-polygon');
    const showing = btn.classList.toggle('active');
    polygons.forEach((p) => p.classList.toggle('hidden', !showing));
    btn.textContent = showing ? 'Hide global baseline' : 'Compare against global baseline';
  });
})();
