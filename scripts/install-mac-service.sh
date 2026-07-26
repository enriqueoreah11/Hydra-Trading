#!/bin/bash
# Deja Hydra corriendo sola en tu Mac: arranca al encender y se reinicia si truena.
# Así no tienes que dejar una terminal abierta.
#
#   bash scripts/install-mac-service.sh          instalar
#   bash scripts/install-mac-service.sh stop     parar y desinstalar
#
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLIST="$HOME/Library/LaunchAgents/com.hydra.trading.plist"
LABEL="com.hydra.trading"

if [ "${1:-}" = "stop" ]; then
  launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
  rm -f "$PLIST"
  echo "✅ Hydra desinstalada del arranque automático."
  exit 0
fi

PY="$DIR/.venv/bin/python"
if [ ! -x "$PY" ]; then
  echo "❌ No encuentro el entorno virtual en $DIR/.venv"
  echo "   Créalo primero:"
  echo "     cd $DIR && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi

mkdir -p "$HOME/Library/LaunchAgents" "$DIR/logs"

cat > "$PLIST" <<PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>$LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PY</string>
        <string>$DIR/run.py</string>
    </array>
    <key>WorkingDirectory</key><string>$DIR</string>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><true/>
    <key>StandardOutPath</key><string>$DIR/logs/hydra.log</string>
    <key>StandardErrorPath</key><string>$DIR/logs/hydra.err</string>
</dict>
</plist>
PLISTEOF

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"

echo "✅ Hydra quedó instalada como servicio."
echo "   Arranca sola al encender la Mac y se reinicia si falla."
echo
echo "   Ver:      http://localhost:8000"
echo "   Logs:     tail -f $DIR/logs/hydra.log"
echo "   Parar:    bash scripts/install-mac-service.sh stop"
