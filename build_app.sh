#!/bin/bash
# Builds AREFA.app on this Mac: refreshes the bundled code, generates an icon
# from a source PNG if one is supplied, and ad-hoc code-signs so Gatekeeper
# lets it open. Run:  ./build_app.sh  [optional-path-to-1024px.png]
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"
APP="AREFA.app"

echo "Refreshing bundled application code…"
cp arefa_workstation.py "$APP/Contents/Resources/arefa_workstation.py"
chmod +x "$APP/Contents/MacOS/AREFA"

ICON_SRC="${1:-}"
if [ -n "$ICON_SRC" ] && [ -f "$ICON_SRC" ]; then
  echo "Generating icon from $ICON_SRC…"
  ICONSET="$(mktemp -d)/AREFA.iconset"; mkdir -p "$ICONSET"
  for s in 16 32 128 256 512; do
    sips -z $s $s     "$ICON_SRC" --out "$ICONSET/icon_${s}x${s}.png"      >/dev/null
    sips -z $((s*2)) $((s*2)) "$ICON_SRC" --out "$ICONSET/icon_${s}x${s}@2x.png" >/dev/null
  done
  iconutil -c icns "$ICONSET" -o "$APP/Contents/Resources/AREFA.icns"
  echo "Icon installed."
else
  echo "No icon PNG supplied — the app will use the generic icon."
  echo "To add one later: ./build_app.sh /path/to/1024x1024.png"
fi

echo "Ad-hoc code-signing so macOS will open it…"
codesign --force --deep --sign - "$APP" 2>/dev/null || \
  echo "  (codesign unavailable; first launch: right-click AREFA.app → Open)"

echo
echo "Done.  AREFA.app is ready in: $HERE"
echo "Move it to /Applications if you like, then double-click to launch."
