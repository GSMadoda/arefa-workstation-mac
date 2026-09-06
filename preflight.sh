#!/bin/bash
# Reports whether this Mac can run AREFA, and whether the exact model is present.
# Read-only: installs nothing, changes nothing.
set -uo pipefail
EXPECTED_MODEL="qwen2.5:7b"
EXPECTED_ID="845dbda0ea48"
bar(){ printf '%s\n' "----------------------------------------------------------------------"; }
echo "AREFA macOS preflight"; bar
printf "%-22s %s\n" "python3" "$(command -v python3 || echo 'MISSING — xcode-select --install')"
printf "%-22s %s\n" "python3 version" "$(python3 --version 2>&1 || true)"
printf "%-22s %s\n" "ollama" "$(command -v ollama || echo 'MISSING — brew install ollama')"
bar
if command -v ollama >/dev/null 2>&1; then
  LINE="$(ollama list 2>/dev/null | awk '$1=="'"$EXPECTED_MODEL"'"{print;exit}')"
  if [ -n "$LINE" ]; then
    ID="$(awk '{print $2}' <<<"$LINE")"
    printf "%-22s %s\n" "model" "$LINE"
    if [ "$ID" = "$EXPECTED_ID" ]; then
      printf "%-22s %s\n" "model identity" "PASS ($ID)"
    else
      printf "%-22s %s\n" "model identity" "DIVERGENCE expected=$EXPECTED_ID measured=$ID"
      echo "  Do not substitute another model; re-pull qwen2.5:7b."
    fi
  else
    printf "%-22s %s\n" "model" "NOT INSTALLED — run: ollama pull $EXPECTED_MODEL"
  fi
else
  echo "Ollama not installed. Conversation stays offline until it is; the UI and"
  echo "VID3 process mining work regardless."
fi
bar
echo "When ready:  double-click 'AREFA (double-click me).command'  or  open AREFA.app"
