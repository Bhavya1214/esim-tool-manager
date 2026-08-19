#!/bin/bash
# bootstrap_linux.sh - One-line installer for eSim Tool Manager on Linux
# Usage: curl -fsSL https://raw.githubusercontent.com/<USER>/esim-tool-manager/main/scripts/install_linux.sh | bash

set -e

REPO_URL="https://github.com/<YOUR_GITHUB_USERNAME>/esim-tool-manager.git"
INSTALL_DIR="$HOME/.local/share/esim-tool-manager"
BIN_DIR="$HOME/.local/bin"
ENTRY_POINT="esim-tool"

echo "Installing eSim Tool Manager..."

# 1. Install System Dependencies
echo "Checking system dependencies..."
if ! command -v python3 &> /dev/null; then
    echo "Installing python3..."
    sudo apt update && sudo apt install -y python3 python3-venv git
fi

# 2. Clone / Update Repo
if [ -d "$INSTALL_DIR" ]; then
    echo "Updating existing installation..."
    cd "$INSTALL_DIR" && git pull
else
    echo "Cloning repository..."
    git clone "$REPO_URL" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

# 3. Create Virtual Environment & Install
echo "Setting up Python environment..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -e .

mkdir -p "$BIN_DIR"
ln -sf "$INSTALL_DIR/venv/bin/$ENTRY_POINT" "$BIN_DIR/$ENTRY_POINT"

if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    echo "$BIN_DIR is not in your PATH."
    echo "Add this to your ~/.bashrc or ~/.profile:"
    echo "export PATH=\"\$HOME/.local/bin:\$PATH\""
fi

echo "Installation complete!"
echo "Run '$ENTRY_POINT --help' to start."
echo "Note: You may need to restart your terminal or run 'source ~/.bashrc'."
