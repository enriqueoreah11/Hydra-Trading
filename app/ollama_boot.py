"""Enciende el cerebro local (Ollama) sin depender de una terminal abierta.

Si Hydra corre como servicio pero Ollama se lanzó a mano con `ollama serve`,
cerrar esa terminal mata el cerebro local y los agentes que lo usan empiezan a
fallar. Este módulo detecta el binario y lo levanta desacoplado del proceso de
Hydra, para que sobreviva aunque Hydra se reinicie.

Para que arranque solo al encender el Mac, usa scripts/install-ollama-service.sh
(un LaunchAgent con KeepAlive). Esto de aquí es la red de seguridad.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

log = logging.getLogger("ollama")

# Rutas donde acaba el binario según cómo se instalara (app oficial, Homebrew
# Intel, Homebrew Apple Silicon, instalación manual).
_CANDIDATES = (
    "/usr/local/bin/ollama",
    "/opt/homebrew/bin/ollama",
    "/Applications/Ollama.app/Contents/Resources/ollama",
    "/Applications/Ollama.app/Contents/MacOS/ollama",
)

# Estado del último intento, para poder explicarlo en la UI sin adivinar.
state: dict = {"tried": False, "ok": False, "error": "", "pid": None}


def binary() -> str | None:
    """Ruta del ejecutable de Ollama, o None si no está instalado."""
    found = shutil.which("ollama")
    if found:
        return found
    for c in _CANDIDATES:
        if os.access(c, os.X_OK):
            return c
    return None


def app_bundle() -> str | None:
    """La app de menú de macOS, que además del servidor trae el icono."""
    p = Path("/Applications/Ollama.app")
    return str(p) if p.is_dir() else None


def start() -> tuple[bool, str]:
    """Lanza `ollama serve` en segundo plano, desacoplado de Hydra.

    Devuelve (arrancó, mensaje). No espera a que el servidor responda: eso lo
    comprueba quien llama, que ya sabe hacer ping a /api/tags.
    """
    state["tried"] = True
    if sys.platform not in ("darwin", "linux"):
        state.update(ok=False, error="solo se puede arrancar en macOS o Linux")
        return False, state["error"]

    # En macOS, si está la app preferimos abrirla: deja el icono en la barra y
    # el usuario ve que el cerebro está encendido.
    if sys.platform == "darwin" and app_bundle():
        try:
            subprocess.run(["/usr/bin/open", "-g", "-a", "Ollama"],
                           check=True, capture_output=True, timeout=15)
            state.update(ok=True, error="", pid=None)
            log.info("ollama: abierta la app de macOS")
            return True, "abrí la app de Ollama"
        except Exception as exc:  # noqa: BLE001 - caemos al binario suelto
            log.warning("ollama: no pude abrir la app (%s), pruebo con el binario", exc)

    exe = binary()
    if not exe:
        state.update(ok=False, error="Ollama no está instalado (no encuentro el binario)")
        return False, state["error"]
    try:
        # start_new_session: se va a su propio grupo de procesos, así no muere
        # cuando launchd reinicie Hydra ni cuando se cierre esta terminal.
        proc = subprocess.Popen(
            [exe, "serve"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL, start_new_session=True)
    except Exception as exc:  # noqa: BLE001
        state.update(ok=False, error=f"{type(exc).__name__}: {str(exc)[:160]}")
        return False, state["error"]
    state.update(ok=True, error="", pid=proc.pid)
    log.info("ollama: arrancado (pid %s)", proc.pid)
    return True, f"arranqué ollama serve (pid {proc.pid})"
