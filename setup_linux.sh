#!/usr/bin/env bash
# Build one-file binaries with PyInstaller (pip install pyinstaller).
# Without arguments the binary starts the GUI, with arguments it is the command line tool.
set -e
cd "$(dirname "$0")"
pyinstaller --onefile --name "FlatCAM Carvera Postprozessor" --icon=./icon/icon.ico main.py
