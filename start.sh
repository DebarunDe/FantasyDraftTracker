#!/usr/bin/env bash
set -euo pipefail

# ── defaults ──────────────────────────────────────────────────────────────────
PORT=8000
FORCE_BUILD=false

# ── arg parsing ───────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        -b|--build)   FORCE_BUILD=true; shift ;;
        -p|--port)
            if [[ -z "${2:-}" || ! "$2" =~ ^[0-9]+$ ]]; then
                echo "ERROR: --port requires a numeric argument"
                exit 1
            fi
            PORT="$2"; shift 2 ;;
        *) echo "Unknown option: $1"; echo "Usage: $0 [--build] [--port <n>]"; exit 1 ;;
    esac
done

# ── resolve project root (script's directory) ─────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── check prerequisites ───────────────────────────────────────────────────────
if [[ ! -f venv/bin/python ]]; then
    echo "ERROR: venv not found. Run: python3 -m venv venv && venv/bin/pip install -r requirements.txt"
    exit 1
fi

if ! command -v npm &>/dev/null; then
    echo "ERROR: npm not found. Install Node.js to build the frontend."
    exit 1
fi

# ── build frontend if needed ──────────────────────────────────────────────────
if [[ "$FORCE_BUILD" == true || ! -d frontend/dist ]]; then
    echo "Building frontend..."
    (cd frontend && npm run build)
    echo ""
fi

# ── detect local IP ───────────────────────────────────────────────────────────
LOCAL_IP="$(ipconfig getifaddr en0 2>/dev/null || true)"
if [[ -z "$LOCAL_IP" ]]; then
    # fallback: try en1 (some Macs use en1 for WiFi)
    LOCAL_IP="$(ipconfig getifaddr en1 2>/dev/null || true)"
fi

# ── print banner ──────────────────────────────────────────────────────────────
echo "┌─────────────────────────────────────────────────┐"
echo "│         Fantasy Draft Tracker — Local Server     │"
echo "├─────────────────────────────────────────────────┤"
if [[ -n "$LOCAL_IP" ]]; then
printf "│  Local:   http://%-29s│\n" "localhost:${PORT}"
printf "│  iPhone:  http://%-29s│\n" "${LOCAL_IP}:${PORT}"
else
printf "│  Local:   http://%-29s│\n" "localhost:${PORT}"
echo "│  iPhone:  (could not detect IP — check WiFi)    │"
fi
echo "│                                                 │"
echo "│  Press Ctrl+C to stop                          │"
echo "└─────────────────────────────────────────────────┘"
echo ""

# ── clean shutdown handler ────────────────────────────────────────────────────
_shutdown() {
    echo ""
    echo "Server stopped."
}
trap _shutdown INT TERM

# ── start server ──────────────────────────────────────────────────────────────
venv/bin/python -m uvicorn src.web.app:app --host 0.0.0.0 --port "$PORT"
