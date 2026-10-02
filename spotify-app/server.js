'use strict';
/**
 * Spotify DB — Web Application
 * =============================
 * 5-page Node.js/Express app connected to the spotify_db MySQL database.
 * Each route renders a server-side EJS template; every SVG visualisation
 * is computed in Node.js (coordinates only) before reaching the template.
 * No client-side charting libraries are used anywhere in this app.
 */

const express = require('express');
const path = require('path');
const db = require('./db');
const { loadQueries } = require('./loadQueries');
const {
  polar,
  weightedAvg,
  buildRadar,
  smoothPath,
  zToPercentile,
  generateAnomalyExplanation,
} = require('./helpers');

const app = express();
const PORT = process.env.PORT || 3000;

// Every SQL query the app runs lives in ../queries.sql, not as inline
// template strings here — see loadQueries.js for the parsing format.
const queries = loadQueries(path.join(__dirname, '..', 'queries.sql'));

app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));

// Every page here is generated fresh from the database on every request, so
// tell any browser or intermediate proxy never to cache it — otherwise a
// stale copy of a page (or a half-loaded one from a moment the server was
// down) can keep getting served long after the server is fixed.
app.use((req, res, next) => {
  res.set('Cache-Control', 'no-store, no-cache, must-revalidate, proxy-revalidate');
  res.set('Pragma', 'no-cache');
  res.set('Expires', '0');
  next();
});

app.use(express.static(path.join(__dirname, 'public'), { etag: false, lastModified: false, maxAge: 0 }));

/** Wraps an async route handler so rejected promises reach the error middleware. */
const asyncRoute = (fn) => (req, res, next) => fn(req, res, next).catch(next);

// ══════════════════════════════════════════════════════════════════════════
//  ROOT — redirect into the app; there is no landing/home page.
// ══════════════════════════════════════════════════════════════════════════
app.get('/', (req, res) => res.redirect('/dashboard'));

// ══════════════════════════════════════════════════════════════════════════
//  PAGE 1 — /dashboard — "The Genre Power Map: Size vs. Dominance"
// ══════════════════════════════════════════════════════════════════════════
app.get('/dashboard', asyncRoute(async (req, res) => {
  const genres = await db.query(queries.dashboardGenreLeaderboard);

  const [{ total_genres }] = await db.query(queries.countGenres);
  const [{ total_tracks }] = await db.query(queries.countTracks);

  // The genres above are only the top 20 BY POPULARITY, so a genre that
  // truly floods Spotify with unlistened content (bad popularity rank)
  // would never appear in that list. Find the real worst offender across
  // every genre instead — the biggest catalogue-to-popularity mismatch.
  const [mostOverproducedGenre] = await db.query(queries.dashboardMostOverproducedGenre);

  const highestPopularityGenre = genres[0] || null;
  const globalMedianPopularity = genres.length ? genres[0].global_median_popularity : 0;
  const maxAvgPopularity = genres.length ? Math.max(...genres.map((g) => g.avg_popularity)) : 1;
  const top10ByPopularity = [...genres]
    .sort((a, b) => b.avg_popularity - a.avg_popularity)
    .slice(0, 10);

  // ─── Slope chart: Size Rank (left) → Popularity Rank (right).
  //     A line falling steeply = huge catalogue that still landed with a
  //     bad popularity rank (floods with content nobody listens to —
  //     "Overproduced"). A line climbing steeply = tiny catalogue that
  //     still cracked the popularity top 20 ("Hidden Gem"). The slope IS
  //     the story — no gap arithmetic required to read it. ───────────────
  const SLOPE_W = 640, SLOPE_MARGIN_TOP = 30, SLOPE_MARGIN_BOTTOM = 30;
  const SLOPE_ROW_H = 26;
  const SLOPE_H = SLOPE_MARGIN_TOP + SLOPE_MARGIN_BOTTOM + SLOPE_ROW_H * genres.length;
  const SLOPE_LEFT_X = 210, SLOPE_RIGHT_X = SLOPE_W - 210;
  const plotH = SLOPE_H - SLOPE_MARGIN_TOP - SLOPE_MARGIN_BOTTOM;

  // Both sides are positioned by ROW ORDER among these 20 genres, not by the
  // raw rank number — size_rank can be anywhere from 1 to 114 for a genre
  // that's merely in the popularity top 20, so plotting it by magnitude
  // crams several genres into the same few pixels and their numbers collide.
  // Row order guarantees every genre gets its own row on both sides.
  const yForIndex = (index) => SLOPE_MARGIN_TOP + (index / (genres.length - 1 || 1)) * plotH;
  const sizeRankOrder = [...genres].sort((a, b) => a.size_rank - b.size_rank);
  const sizeRowIndex = new Map(sizeRankOrder.map((g, i) => [g.genre_id, i]));

  const slopeLines = [...genres]
    .sort((a, b) => a.popularity_rank - b.popularity_rank)
    .map((g, i) => ({
      genre_name: g.genre_name,
      size_rank: g.size_rank,
      popularity_rank: g.popularity_rank,
      gap: g.rank_inversion_gap,
      y1: yForIndex(sizeRowIndex.get(g.genre_id)),
      y2: yForIndex(i),
      // Overproduced: huge catalogue (good/low size rank) but badly placed
      // in popularity (worse/higher popularity rank) — a big NEGATIVE gap.
      status: g.rank_inversion_gap < -15 ? 'over' : g.rank_inversion_gap > 15 ? 'gem' : 'neutral',
    }));

  res.render('dashboard', {
    activePage: 'dashboard',
    genres,
    totalGenres: total_genres,
    totalTracks: total_tracks,
    highestPopularityGenre,
    mostOverproducedGenre,
    globalMedianPopularity,
    maxAvgPopularity,
    slopeWidth: SLOPE_W,
    slopeHeight: SLOPE_H,
    slopeLeftX: SLOPE_LEFT_X,
    slopeRightX: SLOPE_RIGHT_X,
    slopeLines,
  });
}));

// ══════════════════════════════════════════════════════════════════════════
//  PAGE 2 — /artists — "Genre Outliers: The Z-Score Hall of Fame"
// ══════════════════════════════════════════════════════════════════════════
app.get('/artists', asyncRoute(async (req, res) => {
  const rows = await db.query(queries.artistZScoreRanking);

  const maxZ = Math.max(...rows.map((r) => r.popularity_zscore ?? 0), 1);

  const artists = rows.map((r, i) => {
    const z = r.popularity_zscore ?? 0;
    const percentile = zToPercentile(z);
    return {
      ...r,
      overallRank: i + 1,
      percentile: Math.round(percentile * 10) / 10,
      topPct: Math.round((100 - percentile) * 10) / 10,
      barPct: Math.round((Math.max(z, 0) / maxZ) * 100),
    };
  }).sort((a, b) => b.popularity_zscore - a.popularity_zscore);

  const genreList = [...new Set(rows.map((r) => r.genre_name))].sort();

  // Compact payload for the client-side constellation renderer — it needs
  // to re-lay-out the chart whenever the genre filter changes, which isn't
  // practical to precompute server-side for every possible genre.
  const constellationData = artists.map((a) => ({
    name: a.artist_name,
    genre: a.genre_name,
    rank: a.overallRank,
    barPct: a.barPct,
    topPct: a.topPct,
    z: a.popularity_zscore,
  }));

  // ─── Collaboration Network — self-join on track_artist + GROUP_CONCAT + HAVING ───
  const collaborations = await db.query(queries.artistCollaborationNetwork);

  // ─── Collaboration Network geometry — circular node-link layout, computed
  //     server-side. Node size = how many different partners an artist has;
  //     edge thickness = shared tracks; edge colour = how popular the
  //     collaboration ran, so the picture reads as "who works with whom,
  //     how often, and to what effect" without a single row of a table. ───
  const NET_SIZE = 640;
  const NET_CENTER = NET_SIZE / 2;
  const NET_RADIUS = NET_CENTER - 90;

  const artistNodeMap = new Map();
  collaborations.forEach((c) => {
    [c.artist_1, c.artist_2].forEach((name) => {
      if (!artistNodeMap.has(name)) artistNodeMap.set(name, { name, degree: 0 });
    });
  });
  collaborations.forEach((c) => {
    artistNodeMap.get(c.artist_1).degree += 1;
    artistNodeMap.get(c.artist_2).degree += 1;
  });

  // Nodes are shuffled into a deterministic pseudo-random order before laying
  // them around the circle — collaboration order clusters paired artists
  // next to each other, so every edge hugs the rim as a short stubby arc.
  // Decoupling position from pairing spreads edges across the middle instead,
  // which is what makes a circular network chart actually read as a network.
  const hashArtistName = (name) => {
    let h = 0;
    for (let i = 0; i < name.length; i += 1) h = (h * 31 + name.charCodeAt(i)) >>> 0;
    return h;
  };
  const networkNodes = Array.from(artistNodeMap.values())
    .sort((a, b) => hashArtistName(a.name) - hashArtistName(b.name));
  networkNodes.forEach((node, i) => {
    const angle = (i / networkNodes.length) * Math.PI * 2 - Math.PI / 2;
    node.x = NET_CENTER + NET_RADIUS * Math.cos(angle);
    node.y = NET_CENTER + NET_RADIUS * Math.sin(angle);
    node.r = 5 + Math.min(node.degree * 2.5, 16);
    node.labelX = NET_CENTER + (NET_RADIUS + 14) * Math.cos(angle);
    node.labelY = NET_CENTER + (NET_RADIUS + 14) * Math.sin(angle);
    // Labels run radially outward like spokes rather than sitting flat —
    // with 40+ artists on the circle, flat horizontal labels bunch up and
    // overlap near the top and bottom; a label pointing straight out from
    // its own node only ever competes for space with its immediate neighbours.
    const angleDeg = (angle * 180) / Math.PI;
    const onLeftSide = Math.cos(angle) < 0;
    node.labelRotation = onLeftSide ? angleDeg + 180 : angleDeg;
    node.anchor = onLeftSide ? 'end' : 'start';
  });

  const nodeByName = new Map(networkNodes.map((n) => [n.name, n]));
  const maxSharedTracks = Math.max(...collaborations.map((c) => c.shared_tracks), 1);
  const maxCollabPop = Math.max(...collaborations.map((c) => c.avg_collab_popularity), 1);
  const minCollabPop = Math.min(...collaborations.map((c) => c.avg_collab_popularity), 0);

  // Curve every chord toward the centre instead of drawing it as a straight
  // line — two chords that happen to run close to parallel as straight lines
  // still bow at different rates (the bow depends on how far apart the two
  // endpoints are), so they separate visually instead of reading as one
  // thick clump. Classic chord-diagram technique.
  const bowToward = (x1, y1, x2, y2) => {
    const midX = (x1 + x2) / 2;
    const midY = (y1 + y2) / 2;
    return {
      cx: midX + (NET_CENTER - midX) * 0.4,
      cy: midY + (NET_CENTER - midY) * 0.4,
    };
  };

  const networkEdges = collaborations.map((c) => {
    const a = nodeByName.get(c.artist_1);
    const b = nodeByName.get(c.artist_2);
    const heatT = (c.avg_collab_popularity - minCollabPop) / (maxCollabPop - minCollabPop || 1);
    const { cx, cy } = bowToward(a.x, a.y, b.x, b.y);
    return {
      x1: a.x, y1: a.y, x2: b.x, y2: b.y, cx, cy,
      width: Math.round((0.8 + (c.shared_tracks / maxSharedTracks) * 3.2) * 10) / 10,
      color: `hsl(${Math.round(heatT * 120)}, 70%, 55%)`,
      opacity: Math.round((0.35 + (c.shared_tracks / maxSharedTracks) * 0.5) * 100) / 100,
      artist_1: c.artist_1,
      artist_2: c.artist_2,
      shared_tracks: c.shared_tracks,
      avg_collab_popularity: c.avg_collab_popularity,
    };
  }).sort((a, b) => a.shared_tracks - b.shared_tracks); // draw thin edges first so thick ones sit on top

  res.render('artists', {
    activePage: 'artists',
    genreList,
    constellationData,
    networkNodes,
    networkEdges,
    netSize: NET_SIZE,
  });
}));

// ══════════════════════════════════════════════════════════════════════════
//  PAGE 3 — /mood-atlas — "The Emotional Fingerprint of Music"
// ══════════════════════════════════════════════════════════════════════════
app.get('/mood-atlas', asyncRoute(async (req, res) => {
  const rows = await db.query(queries.moodProfiles);

  // Group the mood x genre x key rows into one panel per mood.
  const moodMap = new Map();
  for (const r of rows) {
    if (!moodMap.has(r.mood_id)) {
      moodMap.set(r.mood_id, {
        mood_id: r.mood_id,
        mood_name: r.mood_name,
        description: r.description,
        rows: [],
        genreTrackCounts: new Map(),
        totalTracks: 0,
        paradox: false,
      });
    }
    const m = moodMap.get(r.mood_id);
    m.rows.push(r);
    m.totalTracks += r.track_count;
    m.genreTrackCounts.set(
      r.genre_name,
      (m.genreTrackCounts.get(r.genre_name) || 0) + r.track_count
    );
    if (r.sonic_paradox_flag === 1) m.paradox = true;
  }

  // Global (unweighted-by-mood) baselines for the comparison overlay polygon.
  const globalValues = {
    danceability: weightedAvg(rows, 'avg_danceability'),
    energy: weightedAvg(rows, 'avg_energy'),
    valence: weightedAvg(rows, 'avg_valence'),
    tempo: weightedAvg(rows, 'avg_tempo') / 200,
    acousticness: weightedAvg(rows, 'avg_acousticness'),
    speechiness: weightedAvg(rows, 'avg_speechiness'),
  };

  const RADIUS = 100;
  const CENTER = 130;
  const globalBaselineRadar = buildRadar(globalValues, CENTER, CENTER, RADIUS);

  const moods = [...moodMap.values()].map((m) => {
    const values = {
      danceability: weightedAvg(m.rows, 'avg_danceability'),
      energy: weightedAvg(m.rows, 'avg_energy'),
      valence: weightedAvg(m.rows, 'avg_valence'),
      tempo: weightedAvg(m.rows, 'avg_tempo') / 200,
      acousticness: weightedAvg(m.rows, 'avg_acousticness'),
      speechiness: weightedAvg(m.rows, 'avg_speechiness'),
    };
    const radar = buildRadar(values, CENTER, CENTER, RADIUS);

    const topGenres = [...m.genreTrackCounts.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, 3)
      .map(([genre_name, track_count]) => ({ genre_name, track_count }));

    return {
      mood_id: m.mood_id,
      mood_name: m.mood_name,
      description: m.description,
      totalTracks: m.totalTracks,
      paradox: m.paradox,
      radar,
      topGenres,
    };
  });

  // ─── Popularity Breakdown — GROUP BY genre, mood WITH ROLLUP ─────────────
  const popularityBreakdown = await db.query(queries.moodPopularityBreakdown);

  // ─── Popularity Breakdown treemap geometry — a two-level "slice" treemap
  //     built straight from the ROLLUP rows: column width = a genre's share
  //     of tracks (the genre subtotal row), cell height inside that column =
  //     a mood's share of that genre's tracks, cell colour = how popular
  //     that exact genre+mood combo runs. The hierarchy in the SQL becomes
  //     the hierarchy on screen instead of a table sorted by GROUP BY. ───
  const TREEMAP_W = 920;
  const TREEMAP_H = 460;
  const TREEMAP_LABEL_SPACE = 34;

  const genreSubtotalRows = popularityBreakdown.filter(
    (r) => r.genre !== '── ALL GENRES ──' && r.mood === '── ALL MOODS ──'
  );
  const genreMoodRows = popularityBreakdown.filter(
    (r) => r.genre !== '── ALL GENRES ──' && r.mood !== '── ALL MOODS ──'
  );
  const topGenresByVolume = [...genreSubtotalRows]
    .sort((a, b) => b.track_count - a.track_count)
    .slice(0, 12);
  const treemapTotalTracks = topGenresByVolume.reduce((sum, g) => sum + g.track_count, 0);

  const moodPopValues = genreMoodRows.map((r) => r.avg_popularity);
  const maxMoodPop = Math.max(...moodPopValues);
  const minMoodPop = Math.min(...moodPopValues);
  const heatColor = (pop) => {
    const t = (pop - minMoodPop) / (maxMoodPop - minMoodPop || 1);
    return `hsl(${Math.round(t * 120)}, 65%, 46%)`;
  };

  let treemapX = 0;
  const treemapColumns = topGenresByVolume.map((g) => {
    const colWidth = (g.track_count / treemapTotalTracks) * TREEMAP_W;
    const moodsInGenre = genreMoodRows
      .filter((r) => r.genre === g.genre)
      .sort((a, b) => b.track_count - a.track_count);

    let cellY = 0;
    const cells = moodsInGenre.map((m) => {
      const cellHeight = (m.track_count / g.track_count) * TREEMAP_H;
      const cell = {
        x: treemapX,
        y: cellY,
        width: colWidth,
        height: cellHeight,
        mood: m.mood,
        avg_popularity: m.avg_popularity,
        track_count: m.track_count,
        color: heatColor(m.avg_popularity),
      };
      cellY += cellHeight;
      return cell;
    });

    const column = {
      genre: g.genre,
      x: treemapX,
      width: colWidth,
      track_count: g.track_count,
      avg_popularity: g.avg_popularity,
      cells,
    };
    treemapX += colWidth;
    return column;
  });

  res.render('mood-atlas', {
    activePage: 'mood-atlas',
    moods,
    globalBaselineRadar,
    radarCenter: CENTER,
    radarRadius: RADIUS,
    treemapColumns,
    treemapWidth: TREEMAP_W,
    treemapHeight: TREEMAP_H,
    treemapTotalHeight: TREEMAP_H + TREEMAP_LABEL_SPACE,
    minMoodPop,
    maxMoodPop,
  });
}));

// ══════════════════════════════════════════════════════════════════════════
//  PAGE 4 — /album-journey — "The Architecture of an Album"
// ══════════════════════════════════════════════════════════════════════════
const DEFAULT_ALBUM_ID = 18709; // AM — Arctic Monkeys; a sensible non-empty default

app.get('/album-journey', asyncRoute(async (req, res) => {
  const albumId = Number.isInteger(Number(req.query.album_id)) && req.query.album_id
    ? parseInt(req.query.album_id, 10)
    : DEFAULT_ALBUM_ID;

  // ─── Album picker — a stricter track-count floor keeps this dropdown to a
  //     few hundred entries instead of 1,400+ (a giant option list balloons
  //     the page past response-size limits some proxies/hosts enforce).
  //     The currently-loaded album is always included even if it falls
  //     below the floor, so switching to it from a link never breaks the
  //     dropdown's "selected" state. ───
  const albumOptions = await db.query(queries.albumOptions, [albumId]);

  const tracks = await db.query(queries.albumTracks, [albumId]);

  // ─── Compute SVG timeline coordinates in Node.js ─────────────────────
  // cy encodes popularity (higher popularity = higher up) so the polyline
  // traces the album's actual popularity arc; the baseline <line> sits at
  // the bottom (popularity 0) and doubles as the energy-bar anchor.
  const SVG_WIDTH = 1200;
  const SVG_HEIGHT = 320;
  const MARGIN_X = 60;
  const PLOT_TOP = 40;
  const BASELINE_Y = 260;
  const PLOT_HEIGHT = BASELINE_Y - PLOT_TOP;
  const n = tracks.length;
  const usableWidth = SVG_WIDTH - MARGIN_X * 2;
  const spacing = n > 1 ? usableWidth / (n - 1) : 0;

  const COLOR = { Standout: '#1DB954', Underperformer: '#e74c3c', Consistent: '#888888' };
  const popToY = (pop) => BASELINE_Y - (Math.max(0, Math.min(100, pop)) / 100) * PLOT_HEIGHT;

  const points = tracks.map((t, i) => {
    const cx = n > 1 ? MARGIN_X + i * spacing : SVG_WIDTH / 2;
    const cy = popToY(t.popularity);
    const r = Math.max(t.popularity / 5, 6);
    const barHeight = (t.energy || 0) * 60;
    return {
      ...t,
      cx,
      cy,
      r,
      color: COLOR[t.performance_label] || '#888888',
      barX: cx - 8,
      barY: BASELINE_Y - barHeight,
      barHeight,
      barWidth: 16,
    };
  });

  const polylinePoints = points.map((p) => `${p.cx},${p.cy}`).join(' ');
  const albumAvgPopularity = tracks.length ? tracks[0].album_avg_popularity : 0;
  const dashedY = popToY(albumAvgPopularity);

  // ─── Genre-beating tracks — correlated subquery in WHERE, scoped to this album.
  //     "Standout" (above) only compares a track to its OWN album; this asks a
  //     bigger question — does it also beat the genre it belongs to by a lot? ───
  const genreBeaters = await db.query(queries.albumGenreBeatingTracks, [albumId]);

  // ─── Dumbbell chart geometry — one dot for the genre's average popularity,
  //     one dot for the track's actual popularity, joined by a line. The
  //     length of the line IS the story (how far the track flew past its
  //     genre), no arithmetic required to read it off the page. ───
  const DUMBBELL_W = 760;
  const DUMBBELL_MARGIN_LEFT = 230;
  const DUMBBELL_MARGIN_RIGHT = 70;
  const DUMBBELL_MARGIN_TOP = 20;
  const DUMBBELL_ROW_H = 32;
  const dumbbellChartWidth = DUMBBELL_W - DUMBBELL_MARGIN_LEFT - DUMBBELL_MARGIN_RIGHT;
  const dumbbellHeight = DUMBBELL_MARGIN_TOP + genreBeaters.length * DUMBBELL_ROW_H + 10;
  const xForPopularity = (val) =>
    DUMBBELL_MARGIN_LEFT + (Math.max(0, Math.min(100, val)) / 100) * dumbbellChartWidth;

  const dumbbellRows = genreBeaters.map((g, i) => ({
    ...g,
    y: DUMBBELL_MARGIN_TOP + i * DUMBBELL_ROW_H + DUMBBELL_ROW_H / 2,
    x1: xForPopularity(g.genre_avg_popularity),
    x2: xForPopularity(g.popularity),
  }));

  res.render('album-journey', {
    activePage: 'album-journey',
    albumId,
    albumOptions,
    tracks: points,
    albumName: tracks.length ? tracks[0].album_name : null,
    albumAvgPopularity,
    svgWidth: SVG_WIDTH,
    svgHeight: SVG_HEIGHT,
    baselineY: BASELINE_Y,
    marginX: MARGIN_X,
    polylinePoints,
    dashedY,
    dumbbellRows,
    dumbbellWidth: DUMBBELL_W,
    dumbbellHeight,
    dumbbellMarginLeft: DUMBBELL_MARGIN_LEFT,
  });
}));

// ══════════════════════════════════════════════════════════════════════════
//  PAGE 5 — /outliers — "Tracks That Should Not Exist"
// ══════════════════════════════════════════════════════════════════════════
app.get('/outliers', asyncRoute(async (req, res) => {
  const rows = await db.query(queries.trackAnomalyZScores);

  const MAX_SCORE = 8.0; // sum of 4 |z| rarely exceeds this — matches the spec's danger-meter scale

  const tracks = rows.map((t) => {
    const moodValenceMismatch =
      (t.mood_name === 'Euphoric' || t.mood_name === 'Peaceful') && t.valence_zscore < -1.8 ||
      (t.mood_name === 'Tense' || t.mood_name === 'Melancholic') && t.valence_zscore > 1.8;

    const pct = Math.min(t.total_anomaly_score / MAX_SCORE, 1);
    const hue = Math.round(120 - pct * 120); // green (low anomaly) -> red (high anomaly)

    return {
      ...t,
      explanation: generateAnomalyExplanation(t),
      moodMismatch: moodValenceMismatch,
      severityColor: `hsl(${hue}, 70%, 50%)`,
    };
  });

  const totalAnomalies = tracks.length;
  const avgAnomalyScore = totalAnomalies
    ? Math.round((tracks.reduce((s, t) => s + t.total_anomaly_score, 0) / totalAnomalies) * 100) / 100
    : 0;
  const genreCounts = new Map();
  tracks.forEach((t) => genreCounts.set(t.genre_name, (genreCounts.get(t.genre_name) || 0) + 1));
  const mostAnomalousGenre = [...genreCounts.entries()].sort((a, b) => b[1] - a[1])[0];

  // ─── One mini chart per Z-score dimension, each a different chart type.
  //     Each chart scales to its OWN top-6 range (not a shared global max) —
  //     these are now visually distinct chart types, not bar lengths being
  //     compared to each other, so a local scale keeps every chart legible
  //     even when one dimension's magnitudes dwarf another's.
  //
  //     Colour is per-track (not sign-based red/green) — a single cohesive
  //     6-stop gradient (Spotify green sweeping through teal into indigo),
  //     reused consistently across all four charts so the same rank
  //     position always reads as the same colour and the page reads as one
  //     theme rather than a grab-bag of rainbow hues. ───────────────────
  const DIMENSIONS = [
    { key: 'energy_zscore', label: 'Energy', type: 'dotplot' },
    { key: 'valence_zscore', label: 'Valence', type: 'line' },
    { key: 'dance_zscore', label: 'Danceability', type: 'sunburst' },
    { key: 'acoustic_zscore', label: 'Acousticness', type: 'nightingale' },
  ];

  const TRACK_PALETTE = ['#1DB954', '#1ED6A8', '#22C3E6', '#3B9EF5', '#7C6CF0', '#B366F0'];

  // Shared canvas for the Valence line chart. Track names render fully
  // vertical below the plot, so the chart's height is computed per-render
  // from the longest name actually present — long names get a taller
  // card instead of being truncated.
  const CURVE_W = 440, CURVE_MARGIN_X = 34, CURVE_MARGIN_TOP = 22, CURVE_PLOT_H_FIXED = 96;
  const curveIndexToX = (i, n) => CURVE_MARGIN_X + i * ((CURVE_W - CURVE_MARGIN_X * 2) / (n - 1 || 1));

  // Dot plot of height for Energy — dots float above a baseline by magnitude.
  // Same per-render height sizing as the line chart above.
  const DOT_W = 440, DOT_MARGIN_X = 34, DOT_MARGIN_TOP = 26, DOT_PLOT_H_FIXED = 96;

  // Estimate how tall (in viewBox units) a vertical label needs, based on
  // its character count at the fixed 10px/600-weight font used for labels.
  const LABEL_CHAR_W = 6.6, LABEL_GAP = 24, LABEL_PADDING = 14;
  const labelSpaceFor = (names) => {
    const longest = Math.max(...names.map((n) => n.length));
    return LABEL_GAP + Math.ceil(longest * LABEL_CHAR_W) + LABEL_PADDING;
  };

  // Sunburst / spline rays for Danceability — colourful spikes from a center disc
  const SUN_SIZE = 200;
  const SUN_CENTER = SUN_SIZE / 2;
  const SUN_INNER_R = 24, SUN_MIN_LEN = 18, SUN_MAX_LEN = 62, SUN_STROKE = 14;
  const SUN_RAY_ANGLE = 360 / 6;

  // Acousticness — rounded donut segments, one per track, outer radius
  // encodes magnitude, with a gap between segments so they read as a
  // ring of rounded pills rather than a plain pie chart.
  const ROSE_SIZE = 200;
  const ROSE_CENTER = ROSE_SIZE / 2;
  const ROSE_INNER_R = 34, ROSE_MAX_OUTER_R = 88;
  const ROSE_WEDGE_ANGLE = 360 / 6;
  const ROSE_GAP_DEG = 8;

  const dimensionCharts = DIMENSIONS.map((d) => {
    const topRaw = [...tracks].sort((a, b) => Math.abs(b[d.key]) - Math.abs(a[d.key])).slice(0, 6);
    const localMaxAbsZ = Math.max(...topRaw.map((t) => Math.abs(t[d.key])), 1);
    const colorOf = (i) => TRACK_PALETTE[i % TRACK_PALETTE.length];

    if (d.type === 'dotplot') {
      const marginBottom = labelSpaceFor(topRaw.map((t) => t.track_name));
      const baselineY = DOT_MARGIN_TOP + DOT_PLOT_H_FIXED;
      const height = baselineY + marginBottom;
      const rows = topRaw.map((t, i) => {
        const value = t[d.key];
        const fraction = Math.abs(value) / localMaxAbsZ;
        const x = DOT_MARGIN_X + i * ((DOT_W - DOT_MARGIN_X * 2) / (topRaw.length - 1 || 1));
        return {
          index: i,
          name: t.track_name,
          genre: t.genre_name,
          value,
          color: colorOf(i),
          x: Math.round(x * 100) / 100,
          y: Math.round((baselineY - fraction * DOT_PLOT_H_FIXED) * 100) / 100,
          r: Math.round((7 + fraction * 5) * 100) / 100,
        };
      });
      return {
        label: d.label, type: d.type, top: rows,
        width: DOT_W, height, baselineY, labelY: baselineY + 14,
      };
    }

    if (d.type === 'line') {
      const marginBottom = labelSpaceFor(topRaw.map((t) => t.track_name));
      const baselineY = CURVE_MARGIN_TOP + CURVE_PLOT_H_FIXED / 2;
      const height = CURVE_MARGIN_TOP + CURVE_PLOT_H_FIXED + marginBottom;
      const valueToY = (v) => baselineY - (v / localMaxAbsZ) * (CURVE_PLOT_H_FIXED / 2);
      // Preserve rank order left-to-right so the curve reads as a ranked profile
      const rows = topRaw.map((t, i) => {
        const value = t[d.key];
        return {
          index: i,
          name: t.track_name,
          genre: t.genre_name,
          value,
          color: colorOf(i),
          x: curveIndexToX(i, topRaw.length),
          y: valueToY(value),
        };
      });
      const linePath = smoothPath(rows);
      return {
        label: d.label, type: d.type, top: rows, linePath,
        width: CURVE_W, height, baselineY, labelY: CURVE_MARGIN_TOP + CURVE_PLOT_H_FIXED + 14,
      };
    }

    if (d.type === 'sunburst') {
      const rows = topRaw.map((t, i) => {
        const value = t[d.key];
        const fraction = Math.abs(value) / localMaxAbsZ;
        const len = Math.round((SUN_MIN_LEN + fraction * (SUN_MAX_LEN - SUN_MIN_LEN)) * 100) / 100;
        const angle = i * SUN_RAY_ANGLE;
        const p1 = polar(SUN_CENTER, SUN_CENTER, angle, SUN_INNER_R);
        const p2 = polar(SUN_CENTER, SUN_CENTER, angle, SUN_INNER_R + len);
        return {
          index: i,
          name: t.track_name,
          genre: t.genre_name,
          value,
          color: colorOf(i),
          x1: p1.x, y1: p1.y, x2: p2.x, y2: p2.y,
          length: len,
        };
      });
      return { label: d.label, type: d.type, top: rows };
    }

    // Acousticness — rounded donut segments, one per track, outer radius
    // encodes magnitude. Rescaled min-to-max across just these 6 tracks
    // (not from zero) so the ring always shows clear size variation even
    // when the values themselves are tightly clustered.
    const localMinAbsZ = Math.min(...topRaw.map((t) => Math.abs(t[d.key])));
    const rows = topRaw.map((t, i) => {
      const value = t[d.key];
      const fraction = localMaxAbsZ > localMinAbsZ
        ? (Math.abs(value) - localMinAbsZ) / (localMaxAbsZ - localMinAbsZ)
        : 1;
      const outerR = Math.round((ROSE_INNER_R + fraction * (ROSE_MAX_OUTER_R - ROSE_INNER_R)) * 100) / 100;
      const startAngle = i * ROSE_WEDGE_ANGLE + ROSE_GAP_DEG / 2;
      const endAngle = (i + 1) * ROSE_WEDGE_ANGLE - ROSE_GAP_DEG / 2;
      const outerStart = polar(ROSE_CENTER, ROSE_CENTER, startAngle, outerR);
      const outerEnd = polar(ROSE_CENTER, ROSE_CENTER, endAngle, outerR);
      const innerStart = polar(ROSE_CENTER, ROSE_CENTER, startAngle, ROSE_INNER_R);
      const innerEnd = polar(ROSE_CENTER, ROSE_CENTER, endAngle, ROSE_INNER_R);
      const path = [
        `M ${innerStart.x} ${innerStart.y}`,
        `L ${outerStart.x} ${outerStart.y}`,
        `A ${outerR} ${outerR} 0 0 1 ${outerEnd.x} ${outerEnd.y}`,
        `L ${innerEnd.x} ${innerEnd.y}`,
        `A ${ROSE_INNER_R} ${ROSE_INNER_R} 0 0 0 ${innerStart.x} ${innerStart.y}`,
        'Z',
      ].join(' ');
      return {
        index: i,
        name: t.track_name,
        genre: t.genre_name,
        value,
        color: colorOf(i),
        path,
      };
    });
    return { label: d.label, type: d.type, top: rows };
  });

  res.render('outliers', {
    activePage: 'outliers',
    tracks,
    totalAnomalies,
    avgAnomalyScore,
    mostAnomalousGenre: mostAnomalousGenre ? mostAnomalousGenre[0] : 'N/A',
    dimensionCharts,
    sunSize: SUN_SIZE,
    sunCenter: SUN_CENTER,
    sunInnerR: SUN_INNER_R,
    sunStroke: SUN_STROKE,
    roseSize: ROSE_SIZE,
    roseCenter: ROSE_CENTER,
  });
}));

// ══════════════════════════════════════════════════════════════════════════
//  404 — only the five routes above (+ redirect) exist in this application.
// ══════════════════════════════════════════════════════════════════════════
app.use((req, res) => {
  res.status(404).render('error', {
    activePage: null,
    message: `Not found. This application only has 5 pages: /dashboard, /artists, /mood-atlas, /album-journey, /outliers.`,
  });
});

// ── Error handling middleware — every SQL/route error lands here ─────────
app.use((err, req, res, next) => {
  console.error('[APP ERROR]', err);
  res.status(500).render('error', {
    activePage: null,
    message: err.message || 'An unexpected error occurred.',
  });
});

app.listen(PORT, () => {
  console.log(`\n🎵  Spotify DB — Web Application`);
  console.log(`    ➜  http://localhost:${PORT}/dashboard\n`);
});
