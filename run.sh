#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── System dependencies ───────────────────────────────────────────────────────
check_sys_dep() {
    dpkg -s "$1" &>/dev/null 2>&1
}

MISSING_DEPS=()
for pkg in python3 python3-venv libgtk-3-0 libgl1; do
    if ! check_sys_dep "$pkg"; then
        MISSING_DEPS+=("$pkg")
    fi
done

if [ ${#MISSING_DEPS[@]} -gt 0 ]; then
    echo "Installing missing system packages: ${MISSING_DEPS[*]}"
    sudo apt-get update -qq
    sudo apt-get install -y "${MISSING_DEPS[@]}"
fi

# ── Python virtual environment ────────────────────────────────────────────────
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

source .venv/bin/activate

# ── Python dependencies ───────────────────────────────────────────────────────
echo "Checking Python dependencies..."
pip install -r requirements.txt --quiet --disable-pip-version-check

# ── Desktop shortcut (first run only) ────────────────────────────────────────
DESKTOP_DIR="$HOME/.local/share/applications"
DESKTOP_FILE="$DESKTOP_DIR/StudyFlow.desktop"
if [ ! -f "$DESKTOP_FILE" ]; then
    mkdir -p "$DESKTOP_DIR"
    cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=StudyFlow
Comment=Spaced Repetition MCQ App
Exec=bash $SCRIPT_DIR/run.sh
Icon=$SCRIPT_DIR/assets/icon.png
Terminal=false
Categories=Education;
StartupWMClass=studyflow
EOF
    echo "Desktop shortcut added to app menu."
fi

# ── Launch ────────────────────────────────────────────────────────────────────
echo "Starting StudyFlow..."
python main.py
