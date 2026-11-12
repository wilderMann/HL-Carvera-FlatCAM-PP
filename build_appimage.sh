#!/usr/bin/env bash
# Build a Linux AppImage: GUI without arguments, command line tool with arguments.
#   ./build_appimage.sh            -> dist/FlatCAM.Carvera.Postprozessor.v<version>-x86_64.AppImage
# Needs: python3 with tkinter, pip install pyinstaller, curl. appimagetool is downloaded if missing.
# Build on an old distro (CI: ubuntu-22.04) so the AppImage runs on newer ones (glibc).
set -euo pipefail
cd "$(dirname "$0")"
VERSION=$(python3 -c "import carvera_pp; print(carvera_pp.VERSION)")
NAME=carvera-pp
APPDIR=build/AppDir
OUT="dist/FlatCAM.Carvera.Postprozessor.v${VERSION}-x86_64.AppImage"

rm -rf build/appimage "$APPDIR" dist/$NAME
python3 -m PyInstaller --noconfirm --onedir --name "$NAME" --workpath build/appimage --distpath dist main.py

mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/share/applications" "$APPDIR/usr/share/icons/hicolor/256x256/apps"
cp -r "dist/$NAME" "$APPDIR/usr/bin/"
cp icon/icon256.png "$APPDIR/$NAME.png"
cp icon/icon256.png "$APPDIR/usr/share/icons/hicolor/256x256/apps/$NAME.png"
cat > "$APPDIR/$NAME.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=FlatCAM Carvera Postprozessor
Comment=FlatCAM/pcb2gcode G-code -> Makera Carvera job
Exec=$NAME
Icon=$NAME
Categories=Development;Engineering;
Terminal=false
EOF
cp "$APPDIR/$NAME.desktop" "$APPDIR/usr/share/applications/"
cat > "$APPDIR/AppRun" <<'EOF'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/bin/carvera-pp/carvera-pp" "$@"
EOF
chmod +x "$APPDIR/AppRun"

TOOL=${APPIMAGETOOL:-build/appimagetool-x86_64.AppImage}
if [ ! -x "$TOOL" ]; then
  curl -fsSL -o "$TOOL" https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage
  chmod +x "$TOOL"
fi
mkdir -p dist
ARCH=x86_64 APPIMAGE_EXTRACT_AND_RUN=1 "$TOOL" --no-appstream "$APPDIR" "$OUT"
echo "Built: $OUT"
