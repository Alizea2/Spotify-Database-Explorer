# Spotify Database Explorer

A relational **MySQL** database built from about 114,000 Spotify tracks, plus a **Node.js / Express / EJS** web app that explores the data with complex SQL: CTEs, window functions, Z-scores, multi-table joins and self-joins. Every chart is an SVG computed on the server. There are no client-side charting libraries.

Built as the final project for a Databases and Advanced Data Techniques course.

## The web app

Five server-rendered pages:

| Route | Page | SQL techniques |
|---|---|---|
| `/dashboard` | **The Genre Power Map**: genre leaderboard and the most "overproduced" genre | Multi-level CTEs, CROSS JOIN, 4× `RANK()`, a hand-computed median |
| `/artists` | **Z-Score Hall of Fame**: artists ranked by how far they stand out, plus their collaboration network | Multiple CTEs, `RANK() OVER (PARTITION BY …)`, `STDDEV` Z-scores, a self-join |
| `/mood-atlas` | **The Emotional Fingerprint of Music**: audio profiles of each mood with radar charts | 5-table JOIN, `GROUP BY` / `HAVING`, a CROSS JOIN baseline |
| `/album-journey?album_id=N` | **The Architecture of an Album**: track-by-track timeline of an album | 8 window functions together (`LAG`, `LEAD`, `ROW_NUMBER`, `AVG`, `MAX`, `MIN`, `RANK`) |
| `/outliers` | **Tracks That Should Not Exist**: statistically anomalous tracks | Derived-table subquery, 4 Z-scores, `NULLIF` guards on every division |

All SQL is kept in `queries.sql` as named blocks (`-- @name: …`), which `loadQueries.js` loads so the server can run them by name. The app connects as **`spotify_reader`**, a least-privilege user that can only run `SELECT`.

## The database

`schema.sql` creates `spotify_db` with **8 tables** in a normalised design:

| Table | Stores |
|---|---|
| `track` | Track name, popularity, duration, explicit flag. Links to album, genre and mood. |
| `audio_features` | Danceability, energy, loudness, valence, tempo and other features, one row per track |
| `artist` | Artists |
| `track_artist` | Many-to-many link between tracks and artists |
| `album` | Albums and their total track count |
| `genre` | Genres |
| `mood_category` | The 4 moods (Euphoric, Tense, Melancholic, Peaceful), defined by valence and energy ranges and seeded in the schema |
| `musical_key` | The 12 musical keys, seeded in the schema |

Foreign keys use `ON DELETE CASCADE` / `SET NULL` where appropriate. The ER diagrams are in `er_diagram_with_cardinality.png`, `er_diagram_no_cardinality.png` and `fig2_relational_mapping.png`.

## Running the App

### Quick start (one command)

**Step 1:** Run this command in the terminal first. It downloads the project from GitHub into a temporary folder, creates the database and loads all the data, installs the app and starts it:

```bash
D=$(mktemp -d) && gh repo clone Alizea2/Spotify-Database-Explorer "$D" && cd "$D" && ./setup_db.sh && cd spotify-app && npm install && npm start
```

It asks for your **MySQL root password** once. Press Enter if root has no password.

**Step 2:** Once the terminal shows the app's address, click this link to open it:

**<http://localhost:3000/dashboard>**

Keep the terminal open while you use it. When you're done, press `Ctrl + C` in the terminal to stop the server.

> This needs **MySQL 8+** running locally (`brew install mysql && brew services start mysql`), [Node.js](https://nodejs.org/) 16+, and the [GitHub CLI](https://cli.github.com/) (`gh`) signed in to an account that can access this repository.
>
> `setup_db.sh` replaces any existing `spotify_db` tables with the data in `spotify_db_dump.sql`.

### Manual setup

**Option A: load the ready-made dump (fast).**

```bash
./setup_db.sh            # runs schema.sql, then imports spotify_db_dump.sql
cd spotify-app
npm install
npm start
```

**Option B: build the data from the CSV with Python.**

```bash
mysql -u root -p < schema.sql
pip install -r requirements.txt
python load_data.py      # cleans dataset.csv and inserts it into all tables
cd spotify-app && npm install && npm start
```

In `load_data.py`, set `ROW_LIMIT = 5000` for a quick test run.

### Database credentials

| Setting | Value |
|---|---|
| Host | `127.0.0.1` |
| Database | `spotify_db` |
| App user | `spotify_reader` (SELECT only) |
| App password | `spotify_secure_2024` |

These can be overridden with the `DB_HOST`, `DB_USER`, `DB_PASS` and `DB_NAME` environment variables, and the app port with `PORT`.

## Project Structure

| File / Folder | Purpose |
|---|---|
| `schema.sql` | Database, tables, seed data and the `spotify_reader` user |
| `spotify_db_dump.sql` | Full data dump (all tables) |
| `setup_db.sh` | Runs the schema and imports the dump in one step |
| `queries.sql` | All the app's SQL queries, as named blocks |
| `load_data.py` | Cleans `dataset.csv` and loads it into MySQL |
| `dataset.csv` | Source data: the Spotify Tracks dataset (Kaggle) |
| `generate_er.py`, `generate_fig2.py` | Generate the ER and relational-mapping diagrams |
| `generate_report.py` | Generates the Word report |
| `Spotify_DB_Report.docx` | Project report |
| `spotify-app/server.js` | Express server and the five routes |
| `spotify-app/db.js` | MySQL2 connection pool |
| `spotify-app/loadQueries.js` | Loads the named queries from `queries.sql` |
| `spotify-app/helpers.js` | SVG geometry, Z-score classification and anomaly text |
| `spotify-app/views/` | EJS templates (one per page, plus the nav partial) |
| `spotify-app/public/` | CSS and front-end script |

## Built With

- [MySQL](https://www.mysql.com/)
- [Node.js](https://nodejs.org/), [Express](https://expressjs.com/), [EJS](https://ejs.co/), [mysql2](https://github.com/sidorares/node-mysql2)
- Python: [pandas](https://pandas.pydata.org/), [mysql-connector-python](https://dev.mysql.com/doc/connector-python/en/), [Matplotlib](https://matplotlib.org/), [python-docx](https://python-docx.readthedocs.io/)

## Author

[@Alizea2](https://github.com/Alizea2)
