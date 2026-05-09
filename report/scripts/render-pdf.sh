#!/usr/bin/env bash
# render-pdf.sh — Regenerate the EHI Atlas Phase 1 submission PDF from HTML source.
#
# Usage: ./report/scripts/render-pdf.sh
#
# Strategy: WeasyPrint first (pure Python, no browser header/footer injection).
# If WeasyPrint is unavailable or produces layout problems, fall back to Chrome
# headless with --no-pdf-header-footer to suppress the localhost URL and timestamp.
#
# The browser-print approach produced a URL and timestamp in every page footer
# (http://127.0.0.1:8899/... and "5/8/26, 8:25 PM"). WeasyPrint never injects
# those — it renders directly from the HTML file path.
set -euo pipefail

cd "$(dirname "$0")/../.."   # repo root

SRC="report/drafts/ehi-atlas-phase1-submission.html"
OUT="report/ehi-atlas-phase1-submission-draft-v3.pdf"

echo "Rendering: $SRC -> $OUT"

ABS_SRC="$(pwd)/$SRC"
ABS_OUT="$(pwd)/$OUT"

# Note: WeasyPrint requires libgobject (GLib/Pango) which is not available on
# stock macOS without Homebrew. Chrome headless is the reliable fallback.
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

if [ -f "$CHROME" ]; then
  echo "Using Chrome headless (no header/footer injection)..."
  "$CHROME" --headless --print-to-pdf="$ABS_OUT" \
    --no-pdf-header-footer \
    --run-all-compositor-stages-before-draw \
    "file://$ABS_SRC" 2>&1 | grep -v "^$" | grep -v "ERROR:gpu" | grep -v "SharedImage" | grep -v "Invalid mailbox" | grep "bytes written" || true
  echo "Done: $OUT"
elif uv run --with weasyprint python -c "import weasyprint" 2>/dev/null; then
  echo "Using WeasyPrint (requires libgobject/Pango on macOS: brew install pango)..."
  uv run --with weasyprint python -m weasyprint "$SRC" "$OUT"
  echo "Done: $OUT"
else
  echo "ERROR: Neither Chrome nor WeasyPrint found. Install one:"
  echo "  brew install --cask google-chrome"
  echo "  brew install pango && uv add weasyprint"
  exit 1
fi
