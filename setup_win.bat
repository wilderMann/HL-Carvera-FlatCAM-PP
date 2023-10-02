@echo off

pyinstaller --onefile --name "FlatCAM Carvera Postprozessor" --windowed --icon=./icon/icon.ico main.py

pause
