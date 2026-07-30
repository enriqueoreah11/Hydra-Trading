"""Abre Voicebox si no está abierta, para que la voz elegida se use de verdad.

El servidor de Voicebox vive DENTRO de la app: si la app está cerrada, no hay a
quién pedirle voz. Hydra entonces cae a la voz genérica del navegador, y desde
fuera parece que la configuración no se aplicó — cuando lo único que faltaba era
abrir la app.

Esto es la red de seguridad: al arrancar, y cuando se pulse el botón, se intenta
abrirla. Para que esté siempre lista al encender el Mac, Voicebox se puede añadir
en Ajustes → General → Elementos de inicio.
"""
from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

log = logging.getLogger("voicebox")

# Sitios donde macOS instala una app: la global y la del usuario.
_CANDIDATES = ("/Applications/Voicebox.app",
               str(Path.home() / "Applications" / "Voicebox.app"))

# Estado del último intento, para explicarlo en la UI sin adivinar.
state: dict = {"tried": False, "ok": False, "error": ""}


def app_bundle() -> str | None:
    """Ruta de la app, o None si no está instalada."""
    for c in _CANDIDATES:
        if Path(c).is_dir():
            return c
    return None


def start() -> tuple[bool, str]:
    """Abre Voicebox en segundo plano, sin robar el foco.

    Devuelve (se lanzó, mensaje). No espera a que el servidor responda: eso lo
    comprueba quien llama, que ya sabe pedirle los perfiles.
    """
    state["tried"] = True
    if sys.platform != "darwin":
        state.update(ok=False, error="Voicebox solo existe para macOS")
        return False, state["error"]
    bundle = app_bundle()
    if not bundle:
        state.update(ok=False, error="no encuentro Voicebox.app en /Applications")
        return False, state["error"]
    try:
        # -g: en segundo plano, sin quitarte el foco de lo que estés haciendo.
        subprocess.run(["/usr/bin/open", "-g", "-a", bundle],
                       check=True, capture_output=True, timeout=20)
    except Exception as exc:  # noqa: BLE001
        state.update(ok=False, error=f"{type(exc).__name__}: {str(exc)[:160]}")
        return False, state["error"]
    state.update(ok=True, error="")
    log.info("voicebox: abierta la app (%s)", bundle)
    return True, "abrí la app de Voicebox"
