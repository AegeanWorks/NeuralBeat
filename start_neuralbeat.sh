#!/usr/bin/env sh
# One-click NeuralBeat launcher (POSIX): dismiss your file manager's
# double-click prompt with "Run"/"Run in terminal", or run ./start_neuralbeat.sh
# First run creates an isolated .venv, installs the dependencies and starts the app.
set -u
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$HERE" || exit 1
VENV_PY="$HERE/.venv/bin/python"

if [ ! -x "$VENV_PY" ]; then
    echo "[NeuralBeat] First run: creating an isolated environment (.venv)..."
    if command -v python3 >/dev/null 2>&1; then
        python3 -m venv ".venv"
    fi
fi

if [ ! -x "$VENV_PY" ]; then
    echo "Why: no Python 3.10+ (python3) was found to create the environment."
    echo "Fix: install Python 3.10 or newer. On Debian/Ubuntu also run:"
    echo "     sudo apt install python3-venv"
    echo "     then run this script again."
    exit 1
fi

if ! "$VENV_PY" -c "import numpy, scipy, sounddevice, ttkbootstrap, matplotlib" 2>/dev/null; then
    echo "[NeuralBeat] Installing dependencies (first run only, needs internet)..."
    if ! "$VENV_PY" -m pip install --quiet --disable-pip-version-check \
            -r requirements.txt; then
        echo "Why: installing the dependencies failed (offline or build error)."
        echo "Fix: check your connection and the messages above, then run this"
        echo "     script again. Persistent failures:"
        echo "     https://github.com/AegeanWorks/NeuralBeat/issues"
        exit 1
    fi
fi

exec "$VENV_PY" SourceCode.py
