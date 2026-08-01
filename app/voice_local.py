"""Voz JARVIS generada por la propia Hydra: sin otra app abierta y sin API.

La diferencia con Voicebox no es la calidad, es la DEPENDENCIA. Voicebox es una app
aparte: si está cerrada, no hay voz. Aquí el audio lo genera el mismo proceso de
Hydra llamando a un programa de línea de comandos, y se devuelve al navegador como
un archivo. No hace falta internet, ni clave, ni tener nada abierto.

Hay dos motores, y se prueban en este orden:

  1. **Piper** — red neuronal local (~60 MB por voz). Suena a persona. Es la opción
     buena y solo hay que instalarla una vez.
  2. **`say` de macOS** — ya viene en el Mac, cero instalación. Con una voz británica
     "Enhanced" o "Premium" da el pego; con la voz de serie suena a robot de 2005.

Lo que convierte una voz británica en JARVIS no es el motor, es lo de después: un
poco de compresión para que no suba y baje, un realce en presencia, y un eco muy
corto que da sensación de sala. Eso lo hace ffmpeg si está; si no está, se devuelve
la voz limpia, que sigue funcionando.

Nada de esto reproduce sonido en el Mac por su cuenta: devuelve los bytes y toca el
navegador. Si sonara aquí Y en el navegador, se oiría doble — es el fallo que ya
tuvimos con Voicebox.
"""
from __future__ import annotations

import asyncio
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from .config import settings

log = logging.getLogger("voice_local")

# Voces de `say` que valen para JARVIS, mejor primero. Son británicas masculinas: el
# acento es la mitad del personaje. Las "(Enhanced)" y "(Premium)" hay que bajarlas a
# mano una vez desde Ajustes del Sistema; las de serie suenan claramente sintéticas.
SAY_VOICES = ("Daniel (Enhanced)", "Daniel (Premium)", "Oliver (Enhanced)",
              "Oliver (Premium)", "Arthur", "Daniel", "Oliver")

# Modelos de Piper que sirven, mejor primero. `alan` es un locutor británico grave y
# tranquilo — es el que más se parece.
PIPER_VOICES = ("en_GB-alan-medium", "en_GB-northern_english_male-medium",
                "en_GB-alba-medium", "es_ES-carlfm-x_low")

PIPER_BASE = ("https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_GB/"
              "alan/medium/")

# El sonido JARVIS. Cada eslabón hace una cosa concreta:
#   highpass    quita el retumbe grave que ensucia en altavoces pequeños
#   equalizer   -2 dB en 250 Hz (menos barro), +3 dB en 2.8 kHz (más claridad)
#   lowpass     recorta el brillo digital de arriba: suena a intercomunicador
#   acompressor iguala el volumen; una voz que no sube ni baja suena serena y segura
#   aecho       22 ms de eco: la sala. Es EL detalle que lo hace sonar a JARVIS
#   alimiter    techo, para que ningún pico sature
FX_JARVIS = ("highpass=f=85,"
             "equalizer=f=250:t=q:w=1.2:g=-2,"
             "equalizer=f=2800:t=q:w=1.4:g=3,"
             "lowpass=f=11000,"
             "acompressor=threshold=-18dB:ratio=3:attack=8:release=180,"
             "aecho=0.85:0.75:22:0.18,"
             "alimiter=limit=0.95")

# Sin sala ni recorte de brillo: la voz tal cual, solo emparejada de volumen.
FX_LIMPIO = ("highpass=f=85,"
             "acompressor=threshold=-18dB:ratio=2.5:attack=10:release=200,"
             "alimiter=limit=0.95")

FX = {"jarvis": FX_JARVIS, "limpio": FX_LIMPIO, "": ""}

_last_error: str = ""


def last_error() -> str:
    return _last_error


# ------------------------------------------------------------------ detección

def _piper_cmd() -> list[str] | None:
    """Cómo invocar Piper: binario suelto o módulo de Python. Cualquiera vale."""
    exe = shutil.which("piper")
    if exe:
        return [exe]
    try:
        import piper  # noqa: F401
        import sys
        return [sys.executable, "-m", "piper"]
    except ImportError:
        return None


def piper_models() -> list[Path]:
    """Los modelos .onnx que haya en la carpeta de voces, ordenados por preferencia."""
    d = Path(settings.data_dir) / "voices"
    if not d.is_dir():
        return []
    found = sorted(d.glob("*.onnx"))
    rank = {n: i for i, n in enumerate(PIPER_VOICES)}
    return sorted(found, key=lambda p: (rank.get(p.stem, 99), p.name))


def pick_model() -> Path | None:
    """El modelo a usar: el que digan los ajustes, o el mejor disponible."""
    want = (settings.local_voice or "").strip()
    models = piper_models()
    if want:
        for m in models:
            if m.stem == want or m.name == want:
                return m
        p = Path(want).expanduser()
        if p.is_file():
            return p
    return models[0] if models else None


def say_voices() -> list[str]:
    """Las voces instaladas en el Mac. Lista vacía fuera de macOS."""
    if not shutil.which("say"):
        return []
    try:
        out = subprocess.run(["say", "-v", "?"], capture_output=True, text=True,
                             timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    names = []
    for line in out.splitlines():
        # "Daniel (Enhanced)   en_GB    # Hello, my name is Daniel."
        name = line.split("  ")[0].strip()
        if name:
            names.append(name)
    return names


def pick_say_voice() -> str:
    """La mejor voz británica que esté REALMENTE instalada."""
    want = (settings.local_voice or "").strip()
    have = say_voices()
    if want and want in have:
        return want
    for v in SAY_VOICES:
        if v in have:
            return v
    return have[0] if have else ""


def engines() -> dict:
    """Qué hay instalado ahora mismo y qué se usaría."""
    piper = _piper_cmd()
    models = piper_models()
    say_v = pick_say_voice()
    if piper and models:
        active = "piper"
    elif say_v:
        active = "say"
    else:
        active = ""
    return {
        "activo": active,
        "piper": {"instalado": bool(piper), "modelos": [m.stem for m in models],
                  "usaria": (pick_model().stem if pick_model() else "")},
        "say": {"instalado": bool(shutil.which("say")), "usaria": say_v,
                "buenas_instaladas": [v for v in SAY_VOICES if v in say_voices()]},
        "ffmpeg": bool(shutil.which("ffmpeg")),
        "efecto": settings.voice_fx,
    }


def available() -> bool:
    e = engines()
    return bool(e["activo"])


# ------------------------------------------------------------------ síntesis

def _fx_args(out: Path, src: Path) -> list[str]:
    """La orden de ffmpeg que convierte la voz cruda en la voz de la app.

    Se hace en un solo paso: efectos + tempo + mp3. Encadenar procesos intermedios
    solo añade sitios donde fallar.
    """
    chain = FX.get((settings.voice_fx or "").lower(), FX_JARVIS)
    # atempo solo acepta 0.5–2.0; fuera de ahí haría falta encadenarlo y no merece
    speed = max(0.5, min(2.0, float(settings.voice_speed or 1.0)))
    if abs(speed - 1.0) > 0.01:
        chain = f"{chain},atempo={speed:.3f}" if chain else f"atempo={speed:.3f}"
    args = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(src)]
    if chain:
        args += ["-af", chain]
    return args + ["-codec:a", "libmp3lame", "-b:a", "96k", str(out)]


async def _run(args: list[str], stdin: bytes | None = None, timeout: float = 60) -> bool:
    proc = await asyncio.create_subprocess_exec(
        *args, stdin=asyncio.subprocess.PIPE if stdin is not None else None,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    global _last_error
    try:
        _, err = await asyncio.wait_for(proc.communicate(stdin), timeout)
    except asyncio.TimeoutError:
        proc.kill()
        _last_error = f"{args[0]} tardó más de {timeout:.0f}s"
        return False
    if proc.returncode != 0:
        _last_error = f"{args[0]}: {(err or b'').decode('utf-8', 'replace')[:200]}"
        return False
    return True


async def synth(text: str) -> bytes | None:
    """Genera el audio y lo devuelve. None si no hay ningún motor o algo falló.

    Devolver bytes en vez de reproducir aquí es deliberado: reproducir en el Mac Y
    en el navegador se oye doble, y el volumen dejaría de estar donde el usuario lo
    busca, que es la pestaña.
    """
    global _last_error
    _last_error = ""
    text = (text or "").strip()[:2000]
    if not text:
        return None
    with tempfile.TemporaryDirectory(prefix="hydra-voz-") as tmp:
        raw = Path(tmp) / "voz.wav"
        piper = _piper_cmd()
        model = pick_model()
        ok = False
        if piper and model:
            ok = await _run(piper + ["--model", str(model), "--output_file", str(raw)],
                            stdin=text.encode("utf-8"))
        if not ok:
            voice = pick_say_voice()
            if not voice:
                if not _last_error:
                    _last_error = ("no hay motor de voz local: instala Piper o baja una "
                                   "voz británica en Ajustes del Sistema")
                return None
            # LEI16@22050 es PCM de 16 bits: lo que ffmpeg y el navegador leen sin drama
            ok = await _run(["say", "-v", voice, "-o", str(raw),
                             "--data-format=LEI16@22050", text])
        if not ok or not raw.exists() or raw.stat().st_size < 128:
            if not _last_error:
                _last_error = "el motor de voz no produjo audio"
            return None
        if not shutil.which("ffmpeg"):
            # Sin ffmpeg no hay efecto ni mp3, pero la voz se oye. Mejor eso que nada.
            return raw.read_bytes()
        out = Path(tmp) / "voz.mp3"
        if not await _run(_fx_args(out, raw)) or not out.exists():
            return raw.read_bytes()                    # el efecto falló, la voz no
        return out.read_bytes()


def mime(data: bytes) -> str:
    """WAV o MP3, según lo que se haya podido generar."""
    return "audio/wav" if data[:4] == b"RIFF" else "audio/mpeg"


async def diagnose() -> dict:
    """Qué hay instalado, qué se usaría y una prueba real de generación."""
    info = {"motores": engines()}
    e = info["motores"]
    if not e["activo"]:
        info["ok"] = False
        info["error"] = ("no hay motor local. En un Mac: baja la voz 'Daniel (Enhanced)' "
                         "en Ajustes del Sistema → Accesibilidad → Contenido hablado → "
                         "Voz del sistema → Gestionar voces. Para la voz buena, instala "
                         "Piper (POST /voice/local/install te dice cómo).")
        return info
    audio = await synth("Sistemas en línea. Hydra a la escucha.")
    info["ok"] = bool(audio)
    info["bytes"] = len(audio or b"")
    info["formato"] = mime(audio) if audio else ""
    info["error"] = _last_error
    if e["activo"] == "say" and not e["say"]["buenas_instaladas"]:
        info["aviso"] = ("estás usando la voz de serie del Mac: suena sintética. Baja "
                         "'Daniel (Enhanced)' (unos 100 MB, una sola vez) y cambia "
                         "solo eso.")
    if not e["ffmpeg"]:
        info["aviso_fx"] = ("sin ffmpeg no se aplica el efecto JARVIS: la voz sale "
                            "limpia. `brew install ffmpeg` y ya.")
    return info


INSTALL = {
    "piper": [
        "pip install piper-tts",
        f"mkdir -p {Path(settings.data_dir) / 'voices'}",
        f"curl -L -o {Path(settings.data_dir) / 'voices' / 'en_GB-alan-medium.onnx'} "
        f"{PIPER_BASE}en_GB-alan-medium.onnx",
        f"curl -L -o {Path(settings.data_dir) / 'voices' / 'en_GB-alan-medium.onnx.json'} "
        f"{PIPER_BASE}en_GB-alan-medium.onnx.json",
    ],
    "ffmpeg": ["brew install ffmpeg"],
    "say": ["Ajustes del Sistema → Accesibilidad → Contenido hablado → Voz del "
            "sistema → Gestionar voces → busca 'Daniel' y baja la versión Enhanced"],
}
