-- ============================================================
--  SPOTIFY DB — SQL QUERIES
--  Every query below is the exact SQL spotify-app/server.js runs.
--  server.js loads this file at startup (see spotify-app/loadQueries.js)
--  and looks queries up by name — nothing here is duplicated as an
--  inline template string in server.js.
--
--  Format: each block starts with a `-- @name: <identifier>` marker
--  and runs until the next marker (or end of file). `?` is a
--  parameter placeholder bound by mysql2 at call time.
--
--  To run any one of these yourself: paste it into a MySQL client
--  connected to spotify_db, replacing any `?` with a literal value.
-- ============================================================

USE spotify_db;

-- @name: dashboardGenreLeaderboard
-- Technique: CTE + multiple window functions (RANK OVER ORDER BY).
-- Research question: which genres dominate Spotify by popularity,
-- danceability, and audience size? Extended with a global_stats CTE
-- (mean/median) and rank_inversion_gap, which power the Genre
-- Rankings page's KPI cards and "Rank Reality Check" slope chart.
WITH genre_stats AS (
  SELECT g.genre_id, g.genre_name,
    COUNT(DISTINCT t.track_id) AS track_count,
    COUNT(DISTINCT ta.artist_id) AS unique_artists,
    ROUND(AVG(t.popularity), 2) AS avg_popularity,
    MAX(t.popularity) AS max_popularity,
    ROUND(AVG(af.danceability), 3) AS avg_danceability,
    ROUND(AVG(af.energy), 3) AS avg_energy,
    SUM(CASE WHEN t.explicit THEN 1 ELSE 0 END) AS explicit_count
  FROM genre g
  JOIN track t ON t.genre_id = g.genre_id
  JOIN audio_features af ON af.track_id = t.track_id
  JOIN track_artist ta ON ta.track_id = t.track_id
  GROUP BY g.genre_id, g.genre_name
),
ranked_genres AS (
  SELECT *,
    RANK() OVER (ORDER BY avg_popularity DESC) AS popularity_rank,
    RANK() OVER (ORDER BY track_count DESC) AS size_rank,
    RANK() OVER (ORDER BY avg_danceability DESC) AS danceability_rank,
    RANK() OVER (ORDER BY avg_energy DESC) AS energy_rank,
    ROUND(explicit_count * 100.0 / NULLIF(track_count, 0), 1) AS explicit_pct
  FROM genre_stats
),
global_stats AS (
  SELECT
    AVG(avg_popularity) AS global_mean_popularity,
    MAX(avg_popularity) - MIN(avg_popularity) AS popularity_range,
    (SELECT AVG(avg_popularity) FROM (
      SELECT avg_popularity,
        ROW_NUMBER() OVER (ORDER BY avg_popularity) AS rn,
        COUNT(*) OVER () AS total
      FROM genre_stats
    ) med WHERE rn IN (FLOOR((total + 1) / 2), CEIL((total + 1) / 2))
    ) AS global_median_popularity
  FROM genre_stats
)
SELECT r.*, g.global_mean_popularity, g.global_median_popularity,
  (CAST(r.size_rank AS SIGNED) - CAST(r.popularity_rank AS SIGNED)) AS rank_inversion_gap
FROM ranked_genres r
CROSS JOIN global_stats g
ORDER BY r.avg_popularity DESC
LIMIT 20;


-- @name: countGenres
SELECT COUNT(*) AS total_genres FROM genre;


-- @name: countTracks
SELECT COUNT(*) AS total_tracks FROM track;


-- @name: dashboardMostOverproducedGenre
-- The genre leaderboard above only covers the top 20 BY POPULARITY, so a
-- genre that truly floods Spotify with unlistened content (bad popularity
-- rank) would never appear there. This scans every genre to find the real
-- worst catalogue-to-popularity mismatch, for the "Most Overproduced
-- Genre" KPI card.
WITH genre_stats AS (
  SELECT g.genre_id, g.genre_name,
    COUNT(DISTINCT t.track_id) AS track_count,
    ROUND(AVG(t.popularity), 2) AS avg_popularity
  FROM genre g
  JOIN track t ON t.genre_id = g.genre_id
  GROUP BY g.genre_id, g.genre_name
),
ranked_genres AS (
  SELECT *,
    RANK() OVER (ORDER BY avg_popularity DESC) AS popularity_rank,
    RANK() OVER (ORDER BY track_count DESC) AS size_rank
  FROM genre_stats
)
SELECT genre_name, track_count, avg_popularity, size_rank, popularity_rank,
  (CAST(size_rank AS SIGNED) - CAST(popularity_rank AS SIGNED)) AS rank_inversion_gap
FROM ranked_genres
ORDER BY rank_inversion_gap ASC
LIMIT 1;


-- @name: artistZScoreRanking
-- Technique: multi-level CTE + RANK() OVER (PARTITION BY genre_id) +
-- STDDEV window function for Z-score. Research question: which artists
-- are statistically exceptional within their genre (not just overall)?
-- Extended with an energy_zscore column (same pattern as
-- popularity_zscore) for the Top Artists page's equalizer chart.
WITH artist_genre_stats AS (
  SELECT a.artist_id, a.artist_name,
    g.genre_id, g.genre_name,
    COUNT(DISTINCT t.track_id) AS track_count,
    ROUND(AVG(t.popularity), 2) AS avg_popularity,
    MAX(t.popularity) AS peak_popularity,
    ROUND(AVG(af.danceability), 3) AS avg_danceability,
    ROUND(AVG(af.energy), 3) AS avg_energy,
    ROUND(AVG(af.valence), 3) AS avg_valence,
    COUNT(DISTINCT ta2.artist_id) AS collaborator_count
  FROM artist a
  JOIN track_artist ta ON ta.artist_id = a.artist_id AND ta.is_primary = 1
  JOIN track t ON t.track_id = ta.track_id
  JOIN audio_features af ON af.track_id = t.track_id
  JOIN genre g ON g.genre_id = t.genre_id
  LEFT JOIN track_artist ta2
    ON ta2.track_id = t.track_id
    AND ta2.artist_id != a.artist_id
  WHERE t.popularity IS NOT NULL
  GROUP BY a.artist_id, a.artist_name, g.genre_id, g.genre_name
  HAVING track_count >= 3
),
ranked_artists AS (
  SELECT *,
    RANK() OVER (PARTITION BY genre_id ORDER BY avg_popularity DESC) AS rank_in_genre,
    RANK() OVER (PARTITION BY genre_id ORDER BY track_count DESC) AS volume_rank,
    ROUND(
      (avg_popularity - AVG(avg_popularity) OVER (PARTITION BY genre_id))
      / NULLIF(STDDEV(avg_popularity) OVER (PARTITION BY genre_id), 0),
    2) AS popularity_zscore,
    ROUND(
      (avg_energy - AVG(avg_energy) OVER (PARTITION BY genre_id))
      / NULLIF(STDDEV(avg_energy) OVER (PARTITION BY genre_id), 0),
    2) AS energy_zscore
  FROM artist_genre_stats
)
SELECT artist_name, genre_name, track_count, avg_popularity,
  peak_popularity, avg_energy, avg_danceability, avg_valence,
  collaborator_count, rank_in_genre, popularity_zscore, energy_zscore
FROM ranked_artists
WHERE rank_in_genre <= 5
ORDER BY popularity_zscore DESC
LIMIT 200;


-- @name: artistCollaborationNetwork
-- Technique: self-join on track_artist (same table joined twice) +
-- GROUP_CONCAT + HAVING. Research question: which pairs of artists most
-- frequently collaborate, and how popular are their shared tracks? Powers
-- the Top Artists page's circular collaboration network chart.
WITH collaborations AS (
  SELECT
    ta1.artist_id                   AS artist1_id,
    ta2.artist_id                   AS artist2_id,
    COUNT(DISTINCT ta1.track_id)    AS shared_tracks,
    ROUND(AVG(t.popularity), 2)     AS avg_collab_popularity,
    MAX(t.popularity)               AS peak_popularity,
    GROUP_CONCAT(
      DISTINCT g.genre_name
      ORDER BY g.genre_name
      SEPARATOR ', '
    )                               AS shared_genres,
    COUNT(DISTINCT g.genre_id)      AS genre_diversity
  FROM track_artist ta1
  JOIN track_artist ta2 ON ta1.track_id  = ta2.track_id
                        AND ta1.artist_id < ta2.artist_id
  JOIN track        t   ON t.track_id    = ta1.track_id
  JOIN genre        g   ON g.genre_id    = t.genre_id
  GROUP BY ta1.artist_id, ta2.artist_id
  HAVING shared_tracks >= 2
)
SELECT
  a1.artist_name  AS artist_1,
  a2.artist_name  AS artist_2,
  c.shared_tracks,
  c.avg_collab_popularity,
  c.peak_popularity,
  c.genre_diversity,
  c.shared_genres
FROM collaborations c
JOIN artist a1 ON a1.artist_id = c.artist1_id
JOIN artist a2 ON a2.artist_id = c.artist2_id
ORDER BY c.shared_tracks DESC, c.avg_collab_popularity DESC
LIMIT 30;


-- @name: moodProfiles
-- Technique: full 5-table JOIN with GROUP BY aggregation. Research
-- question: how do audio characteristics differ across mood categories
-- and genres? Extended with a global_mood_baseline CTE + a
-- sonic_paradox_flag column, which drives the "Sonic Paradox Detected"
-- banner on the Mood Breakdown page.
WITH mood_profiles AS (
  SELECT mc.mood_id, mc.mood_name, mc.description,
    g.genre_id, g.genre_name,
    mk.key_name, mk.key_notation,
    COUNT(t.track_id) AS track_count,
    ROUND(AVG(t.popularity), 2) AS avg_popularity,
    ROUND(AVG(af.tempo), 1) AS avg_tempo,
    ROUND(AVG(af.loudness), 2) AS avg_loudness,
    ROUND(AVG(af.danceability), 3) AS avg_danceability,
    ROUND(AVG(af.valence), 3) AS avg_valence,
    ROUND(AVG(af.energy), 3) AS avg_energy,
    ROUND(AVG(af.speechiness), 3) AS avg_speechiness,
    ROUND(AVG(af.acousticness), 3) AS avg_acousticness,
    ROUND(AVG(af.instrumentalness), 3) AS avg_instrumentalness
  FROM mood_category mc
  JOIN track t ON t.mood_id = mc.mood_id
  JOIN audio_features af ON af.track_id = t.track_id
  JOIN genre g ON g.genre_id = t.genre_id
  LEFT JOIN musical_key mk ON mk.key_id = af.key_id
  GROUP BY mc.mood_id, mc.mood_name, mc.description,
    g.genre_id, g.genre_name,
    mk.key_id, mk.key_name, mk.key_notation
  HAVING track_count >= 10
),
global_mood_baseline AS (
  SELECT
    AVG(avg_tempo) AS baseline_tempo,
    AVG(avg_energy) AS baseline_energy,
    AVG(avg_valence) AS baseline_valence,
    AVG(avg_danceability) AS baseline_danceability
  FROM mood_profiles
)
SELECT mp.*, gb.baseline_tempo, gb.baseline_energy,
  CASE
    WHEN mp.avg_tempo < gb.baseline_tempo
    AND mp.mood_name = 'Euphoric' THEN 1
    ELSE 0
  END AS sonic_paradox_flag
FROM mood_profiles mp
CROSS JOIN global_mood_baseline gb
ORDER BY mp.mood_id, mp.track_count DESC;


-- @name: moodPopularityBreakdown
-- Technique: GROUP BY ... WITH ROLLUP for subtotals. Research question:
-- what is the popularity breakdown by genre and mood, with subtotals for
-- each genre? Powers the Mood Breakdown page's treemap.
SELECT
  COALESCE(g.genre_name, '── ALL GENRES ──')    AS genre,
  COALESCE(mc.mood_name, '── ALL MOODS ──')     AS mood,
  COUNT(t.track_id)                              AS track_count,
  ROUND(AVG(t.popularity), 2)                   AS avg_popularity,
  MAX(t.popularity)                              AS max_popularity,
  MIN(t.popularity)                              AS min_popularity,
  ROUND(STDDEV(t.popularity), 2)                AS stddev_popularity
FROM track           t
JOIN genre           g  ON g.genre_id  = t.genre_id
JOIN mood_category   mc ON mc.mood_id  = t.mood_id
WHERE t.popularity IS NOT NULL
GROUP BY g.genre_name, mc.mood_name WITH ROLLUP
ORDER BY g.genre_name, mc.mood_name;


-- @name: albumOptions
-- Album picker for the Album Tracks page's dropdown. A track-count floor
-- keeps the option list to a few hundred entries instead of 1,400+ (a
-- giant list balloons the page past response-size limits some hosts
-- enforce); ? (album_id) is always included even below the floor so the
-- currently loaded album never disappears from its own dropdown.
SELECT album_id, album_name
FROM album
WHERE total_tracks >= 20 OR album_id = ?
ORDER BY album_name;


-- @name: albumTracks
-- Technique: window functions — LAG, LEAD, ROW_NUMBER, AVG/MAX/MIN OVER
-- (PARTITION BY album_id), RANK OVER. Research question: how does track
-- popularity vary across an album, and which tracks stand out above the
-- album average? Parameterised by ? (album_id).
WITH album_tracks AS (
  SELECT
    t.track_id, t.track_name, t.popularity,
    ROUND(t.duration_ms / 60000.0, 2) AS duration_min,
    t.explicit,
    ROUND(af.danceability, 3) AS danceability,
    ROUND(af.energy, 3) AS energy,
    ROUND(af.valence, 3) AS valence,
    ROUND(af.tempo, 1) AS tempo,
    mk.key_name, mc.mood_name, al.album_name,
    ROW_NUMBER() OVER (PARTITION BY t.album_id ORDER BY t.track_id) AS track_position,
    LAG(t.popularity) OVER (PARTITION BY t.album_id ORDER BY t.track_id) AS prev_popularity,
    LEAD(t.popularity) OVER (PARTITION BY t.album_id ORDER BY t.track_id) AS next_popularity,
    ROUND(AVG(t.popularity) OVER (PARTITION BY t.album_id), 1) AS album_avg_popularity,
    ROUND(AVG(af.energy) OVER (PARTITION BY t.album_id), 3) AS album_avg_energy,
    MAX(t.popularity) OVER (PARTITION BY t.album_id) AS album_peak_popularity,
    MIN(t.popularity) OVER (PARTITION BY t.album_id) AS album_min_popularity,
    RANK() OVER (PARTITION BY t.album_id ORDER BY t.popularity DESC) AS popularity_rank_in_album
  FROM track t
  JOIN audio_features af ON af.track_id = t.track_id
  JOIN album al ON al.album_id = t.album_id
  LEFT JOIN musical_key mk ON mk.key_id = af.key_id
  LEFT JOIN mood_category mc ON mc.mood_id = t.mood_id
  WHERE t.album_id = ?
)
SELECT *,
  ROUND(popularity - COALESCE(prev_popularity, popularity), 0) AS popularity_delta,
  CASE
    WHEN popularity >= album_avg_popularity + 10 THEN 'Standout'
    WHEN popularity <= album_avg_popularity - 10 THEN 'Underperformer'
    ELSE 'Consistent'
  END AS performance_label
FROM album_tracks
ORDER BY track_position;


-- @name: albumGenreBeatingTracks
-- Technique: correlated subquery in the WHERE clause. Research question:
-- which tracks are more popular than their genre's average? Scoped to a
-- single album via ? (album_id) — the app's "Standout" label elsewhere on
-- this page only compares a track to its own album; this asks the bigger
-- question of whether it also beats the genre it belongs to by 20+ points.
SELECT
  t.track_name,
  g.genre_name,
  t.popularity,
  ROUND(af.danceability, 3) AS danceability,
  ROUND(af.energy, 3) AS energy,
  mc.mood_name,
  ROUND((
    SELECT AVG(t2.popularity)
    FROM track t2
    WHERE t2.genre_id = t.genre_id
  ), 2) AS genre_avg_popularity,
  ROUND(t.popularity - (
    SELECT AVG(t2.popularity)
    FROM track t2
    WHERE t2.genre_id = t.genre_id
  ), 2) AS above_genre_avg
FROM track           t
JOIN audio_features  af ON af.track_id = t.track_id
JOIN genre           g  ON g.genre_id  = t.genre_id
JOIN mood_category   mc ON mc.mood_id  = t.mood_id
WHERE t.album_id = ?
  AND t.popularity > (
    SELECT AVG(t2.popularity) + 20
    FROM track t2
    WHERE t2.genre_id = t.genre_id
  )
ORDER BY above_genre_avg DESC
LIMIT 50;


-- @name: trackAnomalyZScores
-- Technique: derived-table subquery + STDDEV + Z-score. Research
-- question: which tracks are statistically anomalous in energy, valence,
-- or danceability within their genre? Extended from 3 dimensions to 4 by
-- adding a full acousticness dimension throughout, for the Track
-- Anomalies page's 4 dimension charts.
WITH track_zscores AS (
  SELECT
    t.track_id, t.track_name, t.popularity,
    g.genre_name, mc.mood_name,
    ROUND(af.energy, 3) AS energy,
    ROUND(af.valence, 3) AS valence,
    ROUND(af.danceability, 3) AS danceability,
    ROUND(af.acousticness, 3) AS acousticness,
    ROUND(af.tempo, 1) AS tempo,
    ROUND((af.energy - ga.avg_energy) / NULLIF(ga.sd_energy, 0), 2) AS energy_zscore,
    ROUND((af.valence - ga.avg_valence) / NULLIF(ga.sd_valence, 0), 2) AS valence_zscore,
    ROUND((af.danceability - ga.avg_dance) / NULLIF(ga.sd_dance, 0), 2) AS dance_zscore,
    ROUND((af.acousticness - ga.avg_acoustic) / NULLIF(ga.sd_acoustic, 0), 2) AS acoustic_zscore,
    ROUND(
      ABS((af.energy - ga.avg_energy) / NULLIF(ga.sd_energy, 0)) +
      ABS((af.valence - ga.avg_valence) / NULLIF(ga.sd_valence, 0)) +
      ABS((af.danceability - ga.avg_dance) / NULLIF(ga.sd_dance, 0)) +
      ABS((af.acousticness - ga.avg_acoustic) / NULLIF(ga.sd_acoustic, 0)),
    2) AS total_anomaly_score
  FROM track t
  JOIN audio_features af ON af.track_id = t.track_id
  JOIN genre g ON g.genre_id = t.genre_id
  JOIN mood_category mc ON mc.mood_id = t.mood_id
  JOIN (
    SELECT t2.genre_id,
      AVG(af2.energy) AS avg_energy, STDDEV(af2.energy) AS sd_energy,
      AVG(af2.valence) AS avg_valence, STDDEV(af2.valence) AS sd_valence,
      AVG(af2.danceability) AS avg_dance, STDDEV(af2.danceability) AS sd_dance,
      AVG(af2.acousticness) AS avg_acoustic, STDDEV(af2.acousticness) AS sd_acoustic
    FROM track t2
    JOIN audio_features af2 ON af2.track_id = t2.track_id
    GROUP BY t2.genre_id
  ) ga ON ga.genre_id = t.genre_id
  WHERE
    ABS((af.energy - ga.avg_energy) / NULLIF(ga.sd_energy, 0)) > 1.8
    OR ABS((af.valence - ga.avg_valence) / NULLIF(ga.sd_valence, 0)) > 1.8
    OR ABS((af.danceability - ga.avg_dance) / NULLIF(ga.sd_dance, 0)) > 1.8
    OR ABS((af.acousticness - ga.avg_acoustic) / NULLIF(ga.sd_acoustic, 0)) > 1.8
)
SELECT * FROM track_zscores
ORDER BY total_anomaly_score DESC
LIMIT 50;
