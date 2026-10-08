#!/usr/bin/env bash
# One-time setup on a Linux server (Ubuntu/Debian, x86_64 or ARM, e.g. a cloud VM).
# Installs system packages and a Python environment INSIDE the repo folder (.venv). No secrets are read or written.
#
# Usage:   bash scripts/setup_server.sh            # full setup with the free Kokoro voice
#          SKIP_KOKORO=1 bash scripts/setup_server.sh   # only the video tools (pipeline check without a voice model)
set -euo pipefail
cd "$(dirname "$0")/.."

SUDO=""
if [ "$(id -u)" -ne 0 ]; then SUDO="sudo"; fi

echo "[1/4] System packages (ffmpeg, espeak-ng, fonts, python venv)..."
$SUDO apt-get update -qq
$SUDO apt-get install -y -qq ffmpeg espeak-ng fonts-dejavu-core python3-venv python3-pip git

echo "[2/4] Python environment in .venv ..."
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --quiet --upgrade pip

echo "[3/4] Python packages..."
python -m pip install --quiet pillow numpy soundfile
if [ "${SKIP_KOKORO:-0}" != "1" ]; then
  # Kokoro pulls in PyTorch (large download). The voice model itself downloads on first use.
  # TORCH_CPU=1 installs the much smaller CPU-only PyTorch first (use it on machines without a GPU, e.g. GitHub Actions).
  if [ "${TORCH_CPU:-0}" = "1" ]; then
    python -m pip install --quiet torch --index-url https://download.pytorch.org/whl/cpu
  fi
  python -m pip install --quiet kokoro
fi
python -m pip install --quiet -e .

echo "[4/4] Checking tools..."
ffmpeg -version | head -1
espeak-ng --version | head -1
python -c "import PIL, numpy, soundfile; print('PIL/numpy/soundfile OK')"
if [ "${SKIP_KOKORO:-0}" != "1" ]; then python -c "import kokoro; print('kokoro OK')"; fi
echo "Setup done. Next: bash scripts/make_lessons_server.sh"
