#!/usr/bin/env bash
# Runs every practice query against the app's SQLite database.
# Usage: ./sql/run-all.sh [path/to/loadboard.db]
# Needs the sqlite3 CLI (https://sqlite.org/download.html, or `apt install sqlite3`,
# `brew install sqlite`, `winget install SQLite.SQLite`).
set -euo pipefail
DB="${1:-$(dirname "$0")/../src/MiniLoadBoard.Api/loadboard.db}"
if [ ! -f "$DB" ]; then
  echo "Database not found at $DB - start the app once to create it." >&2
  exit 1
fi
for file in "$(dirname "$0")"/0*.sql; do
  echo
  echo "=================== $(basename "$file") ==================="
  sqlite3 -header -column "$DB" < "$file"
done
