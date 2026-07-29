#!/bin/bash
# Deja el cerebro local (Ollama) corriendo solo: arranca al encender el Mac y se
# reinicia si truena. Así no tienes que dejar una terminal con `ollama serve`
# abierta — si la cierras por error, el cerebro no se cae.
#
#   bash scripts/install-ollama-service.sh          instalar
#   bash scripts/install-ollama-service.sh stop     parar y desinstalar
#
set -euo pipefail

PLIST="$HOME/Library/LaunchAgents/com.hydra.ollama.plist"
LABEL="com.hydra.ollama"
LOGS="$HOME/Library/Logs"

if [ "${1:-}" = "stop" ]; then
  launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
  rm -f "$PLIST"
  echo "✅ Ollama desinstalado del arranque automático."
  exit 0
fi

# Busca el binario donde pueda haber quedado según cómo se instalara
OLLAMA="$(command -v ollama 2>/dev/null || true)"
for c in /usr/local/bin/ollama /opt/homebrew/bin/ollama \
         /Applications/Ollama.app/Contents/Resources/ollama; do
  [ -n "$OLLAMA" ] && break
  [ -x "$c" ] && OLLAMA="$c"
done

if [ -z "$OLLAMA" ]; then
  echo "❌ No encuentro Ollama. Instálalo primero:"
  echo "     https://ollama.com/download   (o:  brew install ollama)"
  exit 1
fi

# Si tienes la app de macOS, ella ya arranca sola al iniciar sesión y además
# pone el icono en la barra. En ese caso el LaunchAgent sobra.
if [ -d "/Applications/Ollama.app" ]; then
  echo "ℹ️  Tienes /Applications/Ollama.app instalada."
  echo "   Ábrela una vez y activa «Launch at login» en sus ajustes:"
  echo "   con eso el cerebro ya queda encendido siempre, sin terminal."
  echo
  echo "   Si aun así quieres el servicio en paralelo, sigue leyendo — pero"
  echo "   normalmente NO hace falta y pueden pelearse por el puerto 11434."
  read -r -p "   ¿Instalo el servicio de todos modos? [s/N] " ans
  case "$ans" in s|S|y|Y) ;; *) echo "   Ok, no instalo nada."; exit 0 ;; esac
fi

mkdir -p "$HOME/Library/LaunchAgents" "$LOGS"

cat > "$PLIST" <<PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>$LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>$OLLAMA</string>
        <string>serve</string>
    </array>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><true/>
    <key>StandardOutPath</key><string>$LOGS/hydra-ollama.log</string>
    <key>StandardErrorPath</key><string>$LOGS/hydra-ollama.err</string>
</dict>
</plist>
PLISTEOF

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"

echo "✅ Ollama quedó instalado como servicio ($OLLAMA)."
echo "   Arranca solo al encender el Mac y se reinicia si falla."
echo
echo "   Probar:  curl -s http://127.0.0.1:11434/api/tags | head -c 120"
echo "   Logs:    tail -f $LOGS/hydra-ollama.log"
echo "   Parar:   bash scripts/install-ollama-service.sh stop"
