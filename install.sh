#!/usr/bin/env bash
# Install makeslideshow as a global terminal command.
#
#   ./install.sh           — install to ~/.local/bin/
#   ./install.sh --uninstall  — remove it
#
# After install you can run:  makeslideshow ~/photos/

set -euo pipefail

INSTALL_DIR="$HOME/.local/bin"
CMD_NAME="makeslideshow"
TARGET="$INSTALL_DIR/$CMD_NAME"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SOURCE="$SCRIPT_DIR/makeslideshow.py"

# ── uninstall ────────────────────────────────────────────────────────────
if [ "${1:-}" = "--uninstall" ]; then
    if [ -f "$TARGET" ]; then
        rm "$TARGET"
        echo "Removed $TARGET"
        echo "Note: the PATH entry in .bashrc (if any) was left alone — edit by hand or ignore."
    else
        echo "Not installed — $TARGET does not exist"
    fi
    exit 0
fi

# ── checks ───────────────────────────────────────────────────────────────
if [ ! -f "$SOURCE" ]; then
    echo "Error: cannot find $SOURCE — run this script from the same folder as makeslideshow.py"
    exit 1
fi

if ! command -v ffmpeg &>/dev/null; then
    echo "Error: ffmpeg is not installed.  Install it first (apt install ffmpeg / dnf install ffmpeg …)"
    exit 1
fi

# ── install ──────────────────────────────────────────────────────────────
mkdir -p "$INSTALL_DIR"
cp "$SOURCE" "$TARGET"
chmod +x "$TARGET"

# make sure ~/.local/bin is on PATH
SHELL_RC=""
for rc in "$HOME/.bashrc" "$HOME/.bash_profile" "$HOME/.profile" "$HOME/.zshrc"; do
    if [ -f "$rc" ]; then
        SHELL_RC="$rc"
        break
    fi
done

if [ -z "$SHELL_RC" ]; then
    SHELL_RC="$HOME/.bashrc"
    touch "$SHELL_RC"
fi

if ! grep -qF "$INSTALL_DIR" "$SHELL_RC" 2>/dev/null; then
    echo "" >> "$SHELL_RC"
    echo "# added by makeslideshow installer" >> "$SHELL_RC"
    echo "export PATH=\"$INSTALL_DIR:\$PATH\"" >> "$SHELL_RC"
    echo "  → added $INSTALL_DIR to $SHELL_RC"
fi

# reload PATH for this session
export PATH="$INSTALL_DIR:$PATH"

# verify
if "$TARGET" --help &>/dev/null; then
    echo ""
    echo "✓  makeslideshow is installed"
    echo ""
    echo "    Run it from anywhere:"
    echo "      makeslideshow ~/photos/funeral/"
    echo ""
    echo "    Clips are saved to ~/Videos/SlideshowClips/"
    echo "    You may need to restart your terminal or:  source $SHELL_RC"
else
    echo "Warning: $TARGET --help failed — something may be wrong"
fi
