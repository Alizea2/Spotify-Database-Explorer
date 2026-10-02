"""
Spotify Tracks Dataset — MySQL Data Loader
==========================================
Downloads (or reads locally) the Spotify Tracks CSV, cleans it,
and inserts all records into the spotify_db MySQL schema.

Requirements:
    pip install pandas mysql-connector-python kagglehub

Usage:
    python load_data.py
"""

import os
import sys
import time
import pandas as pd

# ─── Configuration ────────────────────────────────────────────────────────────
# Reads from environment variables set by lab_setup.sh.
# Override any of these before running:
#   MYSQL_HOST=127.0.0.1 MYSQL_ROOT_USER=root MYSQL_ROOT_PASS='' python load_data.py
DB_CONFIG = {
    "host":     os.environ.get("MYSQL_HOST",      "127.0.0.1"),
    "user":     os.environ.get("MYSQL_ROOT_USER", "root"),
    "password": os.environ.get("MYSQL_ROOT_PASS", ""),
    "database": "spotify_db",
    "charset":  "utf8mb4",
}

KAGGLE_DATASET   = "maharshipandya/-spotify-tracks-dataset"
LOCAL_CSV_PATH   = "dataset.csv"   # Relative to this script — present in project folder
ROW_LIMIT        = None             # Set to e.g. 10000 for a quick test; None = load all
BATCH_SIZE       = 500              # Rows per commit
ARTIST_SEPARATOR = ";"              # Real separator in this CSV (NOT ;;)

# ─── Step 1: Get the CSV ──────────────────────────────────────────────────────
def get_csv_path():
    """
    Resolution order:
    1. dataset.csv in the same directory as this script
    2. kagglehub auto-download
    3. Manual path prompt
    """
    # 1. Local file (already in project folder)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    local = os.path.join(script_dir, LOCAL_CSV_PATH)
    if os.path.exists(local):
        print(f"📂 Using local dataset: {local}")
        return local

    # 2. Try kagglehub
    try:
        import kagglehub
        print("⬇  Downloading dataset via kagglehub...")
        path = kagglehub.dataset_download(KAGGLE_DATASET)
        for root, _, files in os.walk(path):
            for f in files:
                if f.endswith(".csv"):
                    full = os.path.join(root, f)
                    print(f"✅ Found CSV: {full}")
                    return full
        raise FileNotFoundError("No CSV found in downloaded path")
    except Exception as e:
        print(f"⚠  kagglehub failed: {e}")

    # 3. Manual entry
    path = input("Enter absolute path to the Spotify tracks CSV: ").strip()
    if not os.path.exists(path):
        print("❌ File not found. Exiting.")
        sys.exit(1)
    return path

# ─── Step 2: Clean the DataFrame ─────────────────────────────────────────────
def clean_df(df):
    """
    Clean and standardise the dataframe.

    KEY FACTS about this CSV:
    - Artist separator is ';' (single semicolon), NOT ';;'
    - The same track_id appears in multiple rows with different track_genre
      (same track listed under multiple genres — this is intentional in the dataset).
      We keep ALL rows and use (track_id, genre_id) as the effective compound key.
    - The 'key' column is renamed to 'musical_key' to avoid MySQL reserved-word clash.
    """
    # Drop the unnamed index column
    df = df.loc[:, ~df.columns.str.startswith("Unnamed")]

    # Normalise column names
    df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")

    # Rename MySQL reserved word
    if "key" in df.columns:
        df = df.rename(columns={"key": "musical_key"})

    required = ["track_id", "track_name", "artists", "album_name", "track_genre"]
    for col in required:
        if col not in df.columns:
            print(f"⚠  Missing expected column: {col}")

    df = df.dropna(subset=["track_id", "track_name"])
    df["artists"]    = df["artists"].fillna("Unknown Artist")
    df["album_name"] = df["album_name"].fillna("Unknown Album")
    df["explicit"]   = df["explicit"].astype(bool)

    # Keep ALL rows (including track_id duplicates in different genres)
    # De-duplicate on (track_id, track_genre) to avoid identical rows
    before = len(df)
    df = df.drop_duplicates(subset=["track_id", "track_genre"])
    print(f"📊 {len(df):,} rows after de-duplication (removed {before-len(df)} exact dupes)")

    if ROW_LIMIT:
        df = df.head(ROW_LIMIT)
        print(f"ℹ  ROW_LIMIT active — loading first {ROW_LIMIT:,} rows only")

    print(f"    Unique track_ids : {df['track_id'].nunique():,}")
    print(f"    Unique genres    : {df['track_genre'].nunique():,}")
    return df

# ─── Step 3: Assign Mood ──────────────────────────────────────────────────────
MOOD_MAP = {
    "Euphoric":    (0.5, 1.0, 0.5, 1.0),  # mood_id = 1
    "Tense":       (0.0, 0.5, 0.5, 1.0),  # mood_id = 2
    "Melancholic": (0.0, 0.5, 0.0, 0.5),  # mood_id = 3
    "Peaceful":    (0.5, 1.0, 0.0, 0.5),  # mood_id = 4
}

def get_mood_id(valence, energy):
    try:
        v, e = float(valence), float(energy)
    except (TypeError, ValueError):
        return None
    if v >= 0.5 and e >= 0.5:
        return 1  # Euphoric
    if v < 0.5 and e >= 0.5:
        return 2  # Tense
    if v < 0.5 and e < 0.5:
        return 3  # Melancholic
    return 4      # Peaceful

# ─── Step 4: Build lookup maps ────────────────────────────────────────────────
def build_maps(df, cursor, conn):
    """Insert genres, albums, artists; return id-lookup dicts."""

    # ── Genres ──────────────────────────────
    print("  → Genres...")
    genre_map = {}
    for g in df["track_genre"].dropna().unique():
        cursor.execute(
            "INSERT IGNORE INTO genre (genre_name) VALUES (%s)", (str(g)[:100],)
        )
    conn.commit()
    cursor.execute("SELECT genre_id, genre_name FROM genre")
    genre_map = {row[1]: row[0] for row in cursor.fetchall()}

    # ── Albums ──────────────────────────────
    print("  → Albums...")
    for a in df["album_name"].dropna().unique():
        cursor.execute(
            "INSERT IGNORE INTO album (album_name) VALUES (%s)", (str(a)[:255],)
        )
    conn.commit()
    cursor.execute("SELECT album_id, album_name FROM album")
    album_map = {row[1]: row[0] for row in cursor.fetchall()}

    # ── Artists ─────────────────────────────
    print("  → Artists (separator: ';')...")
    all_artists = set()
    # Build all artists using the REAL separator (single semicolon)
    for raw in df["artists"].dropna():
        for name in str(raw).split(ARTIST_SEPARATOR):
            name = name.strip()
            if name:
                all_artists.add(name)

    for name in all_artists:
        cursor.execute(
            "INSERT IGNORE INTO artist (artist_name) VALUES (%s)", (name[:255],)
        )
    conn.commit()
    cursor.execute("SELECT artist_id, artist_name FROM artist")
    artist_map = {row[1]: row[0] for row in cursor.fetchall()}

    print(f"     {len(genre_map)} genres, {len(album_map)} albums, {len(artist_map)} artists")
    return genre_map, album_map, artist_map

# ─── Step 5: Insert tracks ────────────────────────────────────────────────────
def insert_tracks(df, cursor, conn, genre_map, album_map, artist_map):
    inserted = 0
    skipped  = 0
    t0       = time.time()

    for _, row in df.iterrows():
        try:
            tid        = str(row["track_id"])
            genre_id   = genre_map.get(str(row.get("track_genre", "")))
            album_id   = album_map.get(str(row.get("album_name",  "")))
            mood_id    = get_mood_id(row.get("valence"), row.get("energy"))

            def safe_float(val):
                try:    return float(val) if pd.notna(val) else None
                except: return None

            def safe_int(val):
                try:    return int(val) if pd.notna(val) else None
                except: return None

            # ── track ──────────────────────────
            cursor.execute("""
                INSERT IGNORE INTO track
                  (track_id, track_name, popularity, duration_ms, explicit,
                   album_id, genre_id, mood_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                tid,
                str(row["track_name"])[:255],
                safe_int(row.get("popularity")),
                safe_int(row.get("duration_ms")) or 0,
                bool(row.get("explicit", False)),
                album_id,
                genre_id,
                mood_id,
            ))

            # ── audio_features ──────────────────
            raw_key = safe_int(row.get("musical_key", row.get("key")))
            key_id  = raw_key if raw_key is not None and 0 <= raw_key <= 11 else None

            cursor.execute("""
                INSERT IGNORE INTO audio_features
                  (track_id, danceability, energy, key_id, loudness, mode,
                   speechiness, acousticness, instrumentalness, liveness,
                   valence, tempo, time_signature)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                tid,
                safe_float(row.get("danceability")),
                safe_float(row.get("energy")),
                key_id,
                safe_float(row.get("loudness")),
                safe_int(row.get("mode")),
                safe_float(row.get("speechiness")),
                safe_float(row.get("acousticness")),
                safe_float(row.get("instrumentalness")),
                safe_float(row.get("liveness")),
                safe_float(row.get("valence")),
                safe_float(row.get("tempo")),
                safe_int(row.get("time_signature")),
            ))

            # ── track_artist ────────────────────
            # Use the REAL separator (single semicolon)
            raw_artists = str(row.get("artists", ""))
            names = [n.strip() for n in raw_artists.split(ARTIST_SEPARATOR) if n.strip()]
            for i, name in enumerate(names):
                artist_id = artist_map.get(name)
                if artist_id:
                    cursor.execute("""
                        INSERT IGNORE INTO track_artist
                          (track_id, artist_id, is_primary)
                        VALUES (%s, %s, %s)
                    """, (tid, artist_id, i == 0))

            inserted += 1
            if inserted % BATCH_SIZE == 0:
                conn.commit()
                elapsed = time.time() - t0
                rate    = inserted / elapsed
                remaining = (len(df) - inserted) / rate if rate > 0 else 0
                print(f"  [{inserted:>6,} / {len(df):,}] "
                      f"{rate:.0f} rows/s — ~{remaining:.0f}s remaining")

        except Exception as e:
            skipped += 1
            if skipped <= 5:
                print(f"  ⚠ Skipped track {row.get('track_id')}: {e}")

    conn.commit()
    print(f"\n✅ Inserted {inserted:,} tracks  ({skipped} skipped)  "
          f"in {time.time()-t0:.1f}s")

# ─── Step 6: Post-load cleanup ────────────────────────────────────────────────
def post_load(cursor, conn):
    print("🔧 Updating album.total_tracks...")
    cursor.execute("""
        UPDATE album a
        SET total_tracks = (
            SELECT COUNT(*) FROM track t WHERE t.album_id = a.album_id
        )
    """)
    conn.commit()
    print("✅ album.total_tracks updated")

# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    try:
        import mysql.connector
    except ImportError:
        print("❌ mysql-connector-python not installed.")
        print("   Run: pip install mysql-connector-python")
        sys.exit(1)

    # If password wasn't supplied via env var, prompt interactively
    if "MYSQL_ROOT_PASS" not in os.environ and not DB_CONFIG["password"]:
        DB_CONFIG["password"] = input("MySQL root password (leave blank if none): ").strip()

    csv_path = get_csv_path()
    print(f"\n📂 Loading CSV...")
    df = pd.read_csv(csv_path, low_memory=False)
    df = clean_df(df)

    print(f"\n🔌 Connecting to MySQL...")
    conn   = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()

    print("🏗  Building lookup maps...")
    genre_map, album_map, artist_map = build_maps(df, cursor, conn)

    print("\n🚀 Inserting tracks...")
    insert_tracks(df, cursor, conn, genre_map, album_map, artist_map)

    post_load(cursor, conn)

    cursor.close()
    conn.close()
    print("\n🎵 Database loaded successfully. Ready to run the web app!")

if __name__ == "__main__":
    main()
