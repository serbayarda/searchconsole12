#!/usr/bin/env bash
# One-shot setup script for the Search Console AI Agent.
# Safe to re-run.

set -e

cd "$(dirname "$0")"

GREEN="\033[0;32m"; YELLOW="\033[0;33m"; RED="\033[0;31m"; NC="\033[0m"
say()  { echo -e "${GREEN}==>${NC} $*"; }
warn() { echo -e "${YELLOW}!!${NC}  $*"; }
err()  { echo -e "${RED}xx${NC}  $*"; }

# --- 1. Python --------------------------------------------------------------
if ! command -v python3 >/dev/null 2>&1; then
  err "python3 is not installed. Install Python 3.10+ first."
  exit 1
fi
PYVER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
say "Found Python $PYVER"

# --- 2. Virtualenv ----------------------------------------------------------
if [ ! -d ".venv" ]; then
  say "Creating virtualenv at .venv"
  python3 -m venv .venv
else
  say "Reusing existing .venv"
fi

# shellcheck disable=SC1091
source .venv/bin/activate

# --- 3. Dependencies --------------------------------------------------------
say "Installing dependencies (this can take a minute)..."
pip install --upgrade pip >/dev/null
pip install -r requirements.txt

# --- 4. .env ----------------------------------------------------------------
if [ ! -f ".env" ]; then
  cp .env.example .env
  warn "Created .env from template. You MUST edit it and set ANTHROPIC_API_KEY."
  warn "  -> Get a key at https://console.anthropic.com/settings/keys"
else
  if grep -q "sk-ant-\.\.\." .env 2>/dev/null; then
    warn ".env still has the placeholder ANTHROPIC_API_KEY. Edit it before running."
  else
    say ".env present"
  fi
fi

# --- 5. client_secret.json --------------------------------------------------
if [ ! -f "client_secret.json" ]; then
  warn "client_secret.json is missing. You need to download it from Google."
  warn "  See SETUP.md (section 'Get your Google OAuth client') for steps."
else
  say "client_secret.json present"
fi

echo
say "Setup complete. To run the agent:"
echo "    source .venv/bin/activate"
echo "    python -m src.cli"
echo
say "First-run details are in SETUP.md."
