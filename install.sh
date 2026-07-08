#!/usr/bin/env bash
# makeslideshow — one-command installer / updater / uninstaller
#
#   curl -O https://raw.githubusercontent.com/thoroftroy/Make-Slideshow-/main/install.sh
#   bash install.sh               # install or update
#   bash install.sh --uninstall   # remove everything

set -euo pipefail

REPO="https://github.com/thoroftroy/Make-Slideshow-.git"
INSTALL_DIR="$HOME/.local/bin"
CACHE_DIR="$HOME/.local/share/makeslideshow"
CMD_NAME="makeslideshow"
TARGET="$INSTALL_DIR/$CMD_NAME"

# ── uninstall ────────────────────────────────────────────────────────────────
if [ "${1:-}" = "--uninstall" ]; then
    removed=()
    if [ -f "$TARGET" ]; then
        rm "$TARGET"
        removed+=("$TARGET")
    fi
    if [ -d "$CACHE_DIR" ]; then
        rm -rf "$CACHE_DIR"
        removed+=("$CACHE_DIR")
    fi
    if [ ${#removed[@]} -gt 0 ]; then
        echo "Removed: ${removed[*]}"
    else
        echo "Nothing to remove — not installed."
    fi
    echo "Note: PATH entry in shell rc files was left alone.  Edit by hand if desired."
    exit 0
fi

# ── dependencies ─────────────────────────────────────────────────────────────
if ! command -v git &>/dev/null; then
    echo "Error: git is required.  Install it:  apt install git  /  dnf install git  …"
    exit 1
fi
if ! command -v ffmpeg &>/dev/null; then
    echo "Error: ffmpeg is required.  Install it:  apt install ffmpeg  /  dnf install ffmpeg  …"
    exit 1
fi

# ── clone or update the repo ─────────────────────────────────────────────────
if [ -d "$CACHE_DIR/.git" ]; then
    echo "▸ Updating from $REPO ..."
    git -C "$CACHE_DIR" pull --ff-only 2>&1 || {
        echo "Pull failed — trying fresh clone ..."
        rm -rf "$CACHE_DIR"
        git clone "$REPO" "$CACHE_DIR"
    }
else
    mkdir -p "$(dirname "$CACHE_DIR")"
    echo "▸ Cloning $REPO ..."
    git clone "$REPO" "$CACHE_DIR"
fi

# ── install the script ───────────────────────────────────────────────────────
mkdir -p "$INSTALL_DIR"
cp "$CACHE_DIR/makeslideshow.py" "$TARGET"
chmod +x "$TARGET"

# ── add ~/.local/bin to PATH if needed ──────────────────────────────────────
SHELL_RC=""
for rc in "$HOME/.bashrc" "$HOME/.bash_profile" "$HOME/.profile" "$HOME/.zshrc"; do
    [ -f "$rc" ] && { SHELL_RC="$rc"; break; }
done
if [ -z "$SHELL_RC" ]; then
    SHELL_RC="$HOME/.bashrc"
    touch "$SHELL_RC"
fi

if ! grep -qF "$INSTALL_DIR" "$SHELL_RC" 2>/dev/null; then
    printf '\n# added by makeslideshow installer\nexport PATH="%s:$PATH"\n' "$INSTALL_DIR" >> "$SHELL_RC"
    echo "   → added $INSTALL_DIR to $SHELL_RC"
fi

export PATH="$INSTALL_DIR:$PATH"

# ── verify ──────────────────────────────────────────────────────────────────
if "$TARGET" --help &>/dev/null; then
    echo ""
    echo "✓  makeslideshow is ready"
    echo ""
    echo "    Run it anywhere:"
    echo "      makeslideshow ~/photos/funeral/"
    echo "      makeslideshow                  (uses current directory)"
    echo ""
    echo "    Clips are saved to ~/Videos/SlideshowClips/"
    echo "    Re-run this script anytime to update."
    echo ""
    if [[ ":$PATH:" != *":$INSTALL_DIR:"* ]]; then
        echo "    Restart your terminal, or:  source $SHELL_RC"
    fi
else
    echo "Error: $TARGET --help failed — something went wrong"
    exit 1
fi
