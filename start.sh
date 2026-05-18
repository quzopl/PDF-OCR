#!/usr/bin/env bash
# Start backend (FastAPI on :8114) and frontend (Next.js on :3101) in parallel.
# Stops both cleanly on Ctrl+C.

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

API_PORT="${OCR_API_PORT:-8114}"
WEB_PORT="${FRONT_PORT:-3101}"

red()    { printf "\033[31m%s\033[0m\n" "$*"; }
green()  { printf "\033[32m%s\033[0m\n" "$*"; }
yellow() { printf "\033[33m%s\033[0m\n" "$*"; }
cyan()   { printf "\033[36m%s\033[0m\n" "$*"; }

# --- 1. system deps -----------------------------------------------------------

missing=()
for cmd in uv pnpm tesseract gs pdftoppm; do
    command -v "$cmd" >/dev/null 2>&1 || missing+=("$cmd")
done
if [ ${#missing[@]} -gt 0 ]; then
    red "missing required commands: ${missing[*]}"
    yellow "install on Manjaro/Arch:"
    yellow "  sudo pacman -S --needed uv pnpm tesseract \\"
    yellow "    tesseract-data-pol tesseract-data-eng tesseract-data-deu \\"
    yellow "    tesseract-data-fra tesseract-data-spa tesseract-data-rus \\"
    yellow "    ghostscript unpaper poppler"
    exit 1
fi

# --- 2. port check ------------------------------------------------------------

port_busy() { ss -lnt "sport = :$1" 2>/dev/null | tail -n +2 | grep -q .; }
if port_busy "$API_PORT"; then red "port $API_PORT already in use"; exit 1; fi
if port_busy "$WEB_PORT"; then red "port $WEB_PORT already in use"; exit 1; fi

# --- 3. install deps if first run --------------------------------------------

if [ ! -d backend/.venv ]; then
    cyan "first run: installing backend deps via uv (may take a few minutes)..."
    (cd backend && uv sync --extra dev)
fi
if [ ! -d frontend/node_modules ]; then
    cyan "first run: installing frontend deps via pnpm..."
    (cd frontend && pnpm install)
fi

# --- 4. start both servers ----------------------------------------------------

green "starting backend  http://127.0.0.1:$API_PORT"
green "starting frontend http://127.0.0.1:$WEB_PORT"
echo

pids=()
cleanup() {
    echo
    yellow "shutting down..."
    for pid in "${pids[@]}"; do
        kill "$pid" 2>/dev/null || true
    done
    wait 2>/dev/null || true
    exit 0
}
trap cleanup INT TERM

(
    cd backend
    uv run uvicorn app.main:app --host 127.0.0.1 --port "$API_PORT" --reload 2>&1 \
        | sed -u "s/^/$(printf '\033[36m[api]\033[0m') /"
) &
pids+=($!)

(
    cd frontend
    pnpm dev -p "$WEB_PORT" 2>&1 \
        | sed -u "s/^/$(printf '\033[35m[web]\033[0m') /"
) &
pids+=($!)

wait
