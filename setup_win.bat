@echo off
rem GUI (no console window). Without arguments it starts the GUI.
pyinstaller --onefile --name "FlatCAM Carvera Postprozessor" --windowed --icon=./icon/icon.ico main.py
rem Command line version (console), e.g.  "FlatCAM Carvera Postprozessor-cli.exe" --help
pyinstaller --onefile --name "FlatCAM Carvera Postprozessor-cli" --console --icon=./icon/icon.ico main.py
pause
