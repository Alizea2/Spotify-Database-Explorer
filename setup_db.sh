#!/usr/bin/env bash
# Creates spotify_db and the read-only spotify_reader user (schema.sql),
# then loads all the data from spotify_db_dump.sql.
#
# Usage:  ./setup_db.sh                 (connects as root and asks for the password)
#         ./setup_db.sh -u admin -p     (any other mysql connection options)
#
# Note: this replaces any existing spotify_db tables with the data from the dump.
set -e
cd "$(dirname "$0")"

if [ $# -eq 0 ]; then
  set -- -u root -p
  echo "Enter your MySQL root password (press Enter if it has none):"
fi

# The GTID line is removed because it only applies to the server the dump was made on.
{ cat schema.sql; echo "USE spotify_db;"; grep -v "GTID_PURGED" spotify_db_dump.sql; } | mysql "$@"

echo "✓ spotify_db is ready"
