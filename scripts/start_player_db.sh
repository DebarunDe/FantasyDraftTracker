#!/usr/bin/env bash
# Start a standalone DistributedDatabaseSystem node for FantasyDraftTracker.
#
# Port 8090 avoids collision with the FastAPI app (8080) and Vite dev server (5173).
#
# Prerequisites:
#   1. Build the server binary from https://github.com/DebarunDe/DistributedDatabaseSystem:
#        git clone https://github.com/DebarunDe/DistributedDatabaseSystem /tmp/distdb
#        cd /tmp/distdb && go build -o server ./cmd/server
#   2. Copy or symlink the binary somewhere on your PATH, or set PLAYER_DB_BINARY
#      to the full path:
#        export PLAYER_DB_BINARY=/tmp/distdb/server
#
# Environment variables (all optional):
#   PLAYER_DB_BINARY   Path to the compiled server binary   (default: ./server)
#   PLAYER_DB_DATA_DIR Directory for the .bin database file (default: data/playerdb)
#   PLAYER_DB_API_KEY  Bearer token for API authentication  (default: fantasy-draft-key)
#   PLAYER_DB_PORT     HTTP port to listen on               (default: 8090)

set -euo pipefail

DB_BINARY="${PLAYER_DB_BINARY:-./server}"
DATA_DIR="${PLAYER_DB_DATA_DIR:-data/playerdb}"
API_KEY="${PLAYER_DB_API_KEY:-fantasy-draft-key}"
HTTP_PORT="${PLAYER_DB_PORT:-8090}"

if [[ ! -x "$DB_BINARY" ]]; then
  echo "ERROR: server binary not found at '$DB_BINARY'."
  echo "Build it from https://github.com/DebarunDe/DistributedDatabaseSystem:"
  echo "  go build -o server ./cmd/server"
  echo "Then set PLAYER_DB_BINARY=/path/to/server or copy it here."
  exit 1
fi

mkdir -p "$DATA_DIR"

echo "Starting player DB on http://localhost:${HTTP_PORT}  (data: ${DATA_DIR}/players.bin)"
exec "$DB_BINARY" \
  -db        "${DATA_DIR}/players.bin" \
  -http-port "${HTTP_PORT}" \
  -api-keys  "${API_KEY}"
