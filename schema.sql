-- ============================================================
--  SPOTIFY TRACKS DATABASE — SCHEMA
--  7 tables designed for complex relational SQL queries
--  Author: [Your Name]
-- ============================================================

CREATE DATABASE IF NOT EXISTS spotify_db
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE spotify_db;

-- ============================================================
--  TABLE 1: musical_key  (Reference — 12 rows)
--  Maps Spotify's integer key (0-11) to human-readable notes.
--  Enables semantic queries like "which key is most energetic?"
-- ============================================================
CREATE TABLE musical_key (
  key_id        INT          NOT NULL,
  key_name      VARCHAR(10)  NOT NULL,
  key_notation  VARCHAR(30)  NOT NULL,
  PRIMARY KEY (key_id)
);

-- ============================================================
--  TABLE 2: mood_category  (Reference — 4 rows)
--  Classifies tracks into quadrants on the valence × energy plane.
--  Euphoric (happy+energetic), Tense (dark+energetic),
--  Melancholic (sad+calm), Peaceful (happy+calm).
--  Enables mood-based aggregation and multi-table JOINs.
-- ============================================================
CREATE TABLE mood_category (
  mood_id       INT          NOT NULL AUTO_INCREMENT,
  mood_name     VARCHAR(50)  NOT NULL,
  valence_min   FLOAT        NOT NULL,
  valence_max   FLOAT        NOT NULL,
  energy_min    FLOAT        NOT NULL,
  energy_max    FLOAT        NOT NULL,
  description   VARCHAR(255),
  PRIMARY KEY (mood_id)
);

-- ============================================================
--  TABLE 3: genre
--  One row per genre label (up to 125 genres in this dataset).
-- ============================================================
CREATE TABLE genre (
  genre_id    INT           NOT NULL AUTO_INCREMENT,
  genre_name  VARCHAR(100)  NOT NULL,
  PRIMARY KEY (genre_id),
  UNIQUE KEY uq_genre_name (genre_name)
);

-- ============================================================
--  TABLE 4: album
--  One row per unique album name.
--  total_tracks is updated after data load.
-- ============================================================
CREATE TABLE album (
  album_id      INT           NOT NULL AUTO_INCREMENT,
  album_name    VARCHAR(255)  NOT NULL,
  total_tracks  INT           NOT NULL DEFAULT 0,
  PRIMARY KEY (album_id),
  INDEX idx_album_name (album_name(100))
);

-- ============================================================
--  TABLE 5: artist
--  One row per unique artist name.
--  The raw CSV stores multiple artists as "A;;B" — splitting
--  them here is the key normalisation step that resolves
--  the 1NF violation and creates the M:N relationship.
-- ============================================================
CREATE TABLE artist (
  artist_id    INT           NOT NULL AUTO_INCREMENT,
  artist_name  VARCHAR(255)  NOT NULL,
  PRIMARY KEY (artist_id),
  UNIQUE KEY uq_artist_name (artist_name)
);

-- ============================================================
--  TABLE 6: track  (Core fact table)
--  Holds track metadata. Audio features are deliberately kept
--  in a separate 1:1 table (audio_features) so that any
--  audio-related query requires an explicit JOIN.
-- ============================================================
CREATE TABLE track (
  track_id    VARCHAR(50)   NOT NULL,
  track_name  VARCHAR(255)  NOT NULL,
  popularity  INT           CHECK (popularity BETWEEN 0 AND 100),
  duration_ms INT           NOT NULL DEFAULT 0,
  explicit    BOOLEAN       NOT NULL DEFAULT FALSE,
  album_id    INT,
  genre_id    INT,
  mood_id     INT,
  PRIMARY KEY (track_id),
  FOREIGN KEY (album_id) REFERENCES album(album_id)         ON DELETE SET NULL,
  FOREIGN KEY (genre_id) REFERENCES genre(genre_id)         ON DELETE SET NULL,
  FOREIGN KEY (mood_id)  REFERENCES mood_category(mood_id)  ON DELETE SET NULL,
  INDEX idx_track_popularity  (popularity),
  INDEX idx_track_genre       (genre_id),
  INDEX idx_track_album       (album_id),
  INDEX idx_track_mood        (mood_id),
  INDEX idx_track_explicit    (explicit)
);

-- ============================================================
--  TABLE 7: audio_features  (1:1 with track — separated)
--  Storing audio features in their own table forces a JOIN
--  for every audio-related query, enabling complex multi-table
--  SQL that would otherwise collapse to a single flat scan.
--  key_id FK links to musical_key for semantic key queries.
-- ============================================================
CREATE TABLE audio_features (
  track_id          VARCHAR(50)  NOT NULL,
  danceability      FLOAT        CHECK (danceability BETWEEN 0.0 AND 1.0),
  energy            FLOAT        CHECK (energy       BETWEEN 0.0 AND 1.0),
  key_id            INT,
  loudness          FLOAT,
  mode              TINYINT      CHECK (mode IN (0, 1)),
  speechiness       FLOAT        CHECK (speechiness       BETWEEN 0.0 AND 1.0),
  acousticness      FLOAT        CHECK (acousticness      BETWEEN 0.0 AND 1.0),
  instrumentalness  FLOAT        CHECK (instrumentalness  BETWEEN 0.0 AND 1.0),
  liveness          FLOAT        CHECK (liveness          BETWEEN 0.0 AND 1.0),
  valence           FLOAT        CHECK (valence           BETWEEN 0.0 AND 1.0),
  tempo             FLOAT,
  time_signature    INT,
  PRIMARY KEY (track_id),
  FOREIGN KEY (track_id) REFERENCES track(track_id)       ON DELETE CASCADE,
  FOREIGN KEY (key_id)   REFERENCES musical_key(key_id)   ON DELETE SET NULL,
  INDEX idx_af_energy       (energy),
  INDEX idx_af_valence      (valence),
  INDEX idx_af_danceability (danceability),
  INDEX idx_af_tempo        (tempo),
  INDEX idx_af_key          (key_id)
);

-- ============================================================
--  TABLE 8: track_artist  (M:N junction)
--  Resolves the many-to-many relationship between tracks and
--  artists (a track can have multiple artists; an artist can
--  appear on many tracks). is_primary flags the lead artist.
-- ============================================================
CREATE TABLE track_artist (
  track_id    VARCHAR(50)  NOT NULL,
  artist_id   INT          NOT NULL,
  is_primary  BOOLEAN      NOT NULL DEFAULT TRUE,
  PRIMARY KEY (track_id, artist_id),
  FOREIGN KEY (track_id)  REFERENCES track(track_id)    ON DELETE CASCADE,
  FOREIGN KEY (artist_id) REFERENCES artist(artist_id)  ON DELETE CASCADE,
  INDEX idx_ta_artist   (artist_id),
  INDEX idx_ta_primary  (is_primary)
);

-- ============================================================
--  SEED DATA: musical_key (12 rows)
-- ============================================================
INSERT INTO musical_key (key_id, key_name, key_notation) VALUES
(0,  'C',  'C Major / A Minor'),
(1,  'C#', 'C# Major / A# Minor'),
(2,  'D',  'D Major / B Minor'),
(3,  'D#', 'D# Major / C Minor'),
(4,  'E',  'E Major / C# Minor'),
(5,  'F',  'F Major / D Minor'),
(6,  'F#', 'F# Major / D# Minor'),
(7,  'G',  'G Major / E Minor'),
(8,  'G#', 'G# Major / F Minor'),
(9,  'A',  'A Major / F# Minor'),
(10, 'A#', 'A# Major / G Minor'),
(11, 'B',  'B Major / G# Minor');

-- ============================================================
--  SEED DATA: mood_category (4 rows)
--  Quadrants based on Valence (x-axis) × Energy (y-axis)
-- ============================================================
INSERT INTO mood_category (mood_name, valence_min, valence_max, energy_min, energy_max, description) VALUES
('Euphoric',    0.5, 1.0, 0.5, 1.0, 'Happy and energetic — party, pop, and dance tracks'),
('Tense',       0.0, 0.5, 0.5, 1.0, 'Dark and intense — aggressive, dramatic, or ominous'),
('Melancholic', 0.0, 0.5, 0.0, 0.5, 'Sad and calm — emotional, reflective, or ambient tracks'),
('Peaceful',    0.5, 1.0, 0.0, 0.5, 'Happy and relaxed — acoustic, folk, or easy-listening');

-- ============================================================
--  LEAST-PRIVILEGE APPLICATION USER
--  The web app connects as spotify_reader (SELECT only, never root).
--  Data loading uses root separately (not via the app).
-- ============================================================
-- Granted on both hostnames because MySQL treats 'localhost' and '127.0.0.1'
-- as different accounts, and which one a Node client resolves to varies by
-- environment (e.g. a local Mac vs. a container-based lab).
CREATE USER IF NOT EXISTS 'spotify_reader'@'localhost' IDENTIFIED BY 'spotify_secure_2024';
CREATE USER IF NOT EXISTS 'spotify_reader'@'127.0.0.1' IDENTIFIED BY 'spotify_secure_2024';
GRANT SELECT ON spotify_db.* TO 'spotify_reader'@'localhost';
GRANT SELECT ON spotify_db.* TO 'spotify_reader'@'127.0.0.1';
FLUSH PRIVILEGES;
