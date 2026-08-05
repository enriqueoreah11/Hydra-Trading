"""Los oídos: pasar de voz a texto sin que el audio salga del Mac.

Voicebox ya está en la máquina para hablar, y trae Whisper dentro con un endpoint
REST propio (`POST /transcribe`, multipart). Así que oír no necesita ninguna app
nueva, ninguna clave y ninguna conexión a internet: el mismo proceso que pone la
voz pone el oído.

Lo delicado aquí no es la llamada, es lo que se hace con lo que vuelve. Whisper
NO devuelve vacío cuando no ha oído nada: se inventa una frase. Sobre silencio o
ruido de fondo saca "Gracias por ver el video" o "Subtítulos realizados por la
comunidad de Amara.org" — restos de los vídeos con los que se entrenó. Si eso
entra en el sistema como si lo hubieras dicho tú, acabas con notas fantasma en la
memoria o con el cerebro contestando a una pregunta que nadie hizo.
"""
from __future__ import annotations

import logging
import re
import unicodedata

import httpx

from .config import settings

log = logging.getLogger("stt")

_last_error: str = ""

# Frases que Whisper produce a partir de silencio o ruido. No son transcripciones,
# son residuos del entrenamiento (subtítulos de YouTube).
#
# Van en dos listas porque el criterio no es el mismo. Las INCONFUNDIBLES nadie las
# dice delante de un micro, así que se cortan midan lo que midan — y Whisper suele
# soltarlas repetidas, de ahí el startswith. Las GENÉRICAS son palabras normales:
# solo se descartan cuando son TODA la frase, o el filtro se comería un "gracias,
# ahora dime cómo va el oro".
_ALUCINACIONES = (
    "subtitulos realizados por la comunidad de amara",
    "subtitulos por la comunidad de amara",
    "subtitulado por la comunidad de amara",
    "mas informacion en www alimmenta com",
    "gracias por ver el video",
    "gracias por ver este video",
    "gracias por su atencion",
    "thanks for watching",
    "thank you for watching",
    "subscribe to my channel",
)
# "sí" y "no" NO entran aquí a propósito: son las dos respuestas que más falta hace
# que lleguen enteras. Perder un "gracias" da igual; perder un "no" no.
_ALUCINACIONES_CORTAS = ("gracias", "you", "bye", "amen", "eh", "mm")

# Por debajo de esto no hay una frase, hay un clic. El navegador manda cuánto duró
# la grabación porque medir la duración del audio aquí exigiría decodificarlo.
MIN_MS = 400
MIN_BYTES = 1200


def available() -> bool:
    """Oír depende de Voicebox, igual que hablar."""
    return settings.tts_provider == "voicebox" and bool(settings.stt_enabled)


def last_error() -> str:
    return _last_error


def _plano(texto: str) -> str:
    """Sin tildes, sin signos y en minúsculas, para comparar con la lista."""
    s = unicodedata.normalize("NFKD", texto.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^\w\s]", "", s).strip()


def es_alucinacion(texto: str) -> bool:
    plano = _plano(texto)
    if not plano:                                   # solo signos: "...", "¿?"
        return True
    if any(plano.startswith(f) for f in _ALUCINACIONES):
        return True
    return plano in _ALUCINACIONES_CORTAS


def _texto_de(dato) -> str:
    """El texto venga como venga: la forma exacta cambia entre versiones."""
    if isinstance(dato, str):
        return dato.strip()
    if isinstance(dato, dict):
        for k in ("text", "transcript", "transcription", "result", "data"):
            if k in dato:
                t = _texto_de(dato[k])
                if t:
                    return t
    if isinstance(dato, list):
        return " ".join(x for x in (_texto_de(d) for d in dato) if x).strip()
    return ""


async def transcribe(audio: bytes, ms: int = 0, filename: str = "captura.webm") -> dict:
    """Audio -> texto. Nunca lanza: devuelve por qué no se pudo."""
    global _last_error
    _last_error = ""

    if not available():
        return {"ok": False, "text": "",
                "error": "los oídos van con Voicebox; enciéndela y elige la voz de Voicebox"}
    if len(audio) < MIN_BYTES or (ms and ms < MIN_MS):
        # Devolver "" sin más se leería como «no dijiste nada»; lo que pasó es que
        # no llegó a grabarse.
        return {"ok": False, "text": "", "corto": True,
                "error": "no se grabó nada: mantén pulsado mientras hablas"}

    url = settings.voicebox_url.rstrip("/") + "/transcribe"
    try:
        async with httpx.AsyncClient(timeout=settings.stt_timeout_s) as http:
            r = await http.post(
                url,
                files={"audio": (filename, audio, "application/octet-stream")},
                data={"model": settings.stt_model})
            if r.status_code == 404:
                _last_error = ("tu versión de Voicebox no tiene /transcribe: "
                               "actualízala y vuelve a probar")
                return {"ok": False, "text": "", "error": _last_error}
            r.raise_for_status()
            try:
                crudo = r.json()
            except ValueError:
                crudo = r.text
    except httpx.TimeoutException:
        _last_error = f"Voicebox no contestó en {settings.stt_timeout_s:.0f}s"
        return {"ok": False, "text": "", "error": _last_error}
    except Exception as exc:  # noqa: BLE001
        _last_error = f"no se pudo hablar con Voicebox: {str(exc)[:120]}"
        return {"ok": False, "text": "", "error": _last_error}

    texto = _texto_de(crudo)
    if not texto:
        return {"ok": False, "text": "", "error": "Voicebox no devolvió texto"}
    if es_alucinacion(texto):
        # Se dice lo que pasó en vez de callarlo: si no, parece que el micro no va.
        log.info("descartado residuo de Whisper: %r", texto[:60])
        return {"ok": False, "text": "", "vacio": True,
                "error": "no se entendió nada; habla un poco más cerca"}
    return {"ok": True, "text": texto, "error": ""}


# --------------------------------------------- qué hacer con lo que dijiste

# Órdenes habladas. La regla no es "bloquear todo", es mirar hacia dónde falla cada
# una si Whisper se equivoca:
#
#   PARAR mal entendido deja el sistema quieto. Molesta y se deshace con un botón.
#   REANUDAR mal entendido pone a operar una cuenta que tú habías parado a mano, y
#   eso no se deshace: para cuando lo ves, ya hay órdenes puestas.
#
# Por eso parar sí se ejecuta hablando y lo demás pide un botón. No es desconfianza
# del micro: es que las dos equivocaciones no cuestan lo mismo.
_ORDENES_SEGURAS = ("para", "parar", "detente", "deten", "halt", "alto", "pausa")
_ORDENES = _ORDENES_SEGURAS + (
    "abre", "abrir", "compra", "comprar", "vende", "vender", "cierra", "cerrar",
    "liquida", "liquidar", "apaga", "apagar", "enciende", "encender", "duplica",
    "arriesga", "reanuda", "reanudar", "continua", "activa")
# Solo en imperativo y al principio: "cierra el oro" es una orden, "cómo cierra el
# oro hoy" es una pregunta, y confundirlas sería negarle una respuesta normal.
_DICTAR = ("apunta", "anota", "apuntame", "apuntame que", "nota", "guarda",
           "recuerda", "acuerdate")


def intencion(texto: str) -> dict:
    """Qué se hace con la frase: dictar una nota, contestar, o no tocar nada."""
    limpio = (texto or "").strip()
    palabras = _plano(limpio).split()
    if not palabras:
        return {"tipo": "nada", "texto": ""}
    primera = palabras[0]

    if primera in _DICTAR:
        # "apunta que el oro respetó el 3400" -> se guarda sin el verbo ni el "que"
        resto = limpio.split(" ", 1)[1].strip() if " " in limpio else ""
        if _plano(resto).split()[:1] == ["que"]:
            resto = resto.split(" ", 1)[1].strip() if " " in resto else ""
        return {"tipo": "nota", "texto": resto or limpio}

    if primera in _ORDENES:
        return {"tipo": "orden", "texto": limpio,
                "seguro": primera in _ORDENES_SEGURAS}

    return {"tipo": "pregunta", "texto": limpio}


async def diagnose() -> dict:
    """Si los oídos funcionan y, si no, por qué."""
    info: dict = {"ok": False, "activo": bool(settings.stt_enabled),
                  "motor": "Voicebox (Whisper local)", "url": settings.voicebox_url,
                  "modelo": settings.stt_model}
    if settings.tts_provider != "voicebox":
        info["error"] = "los oídos van con Voicebox; ahora mismo la voz no es Voicebox"
        return info
    if not settings.stt_enabled:
        info["error"] = "el micrófono está apagado en Configuración"
        return info
    try:
        async with httpx.AsyncClient(timeout=5.0) as http:
            r = await http.get(settings.voicebox_url.rstrip("/") + "/profiles")
            r.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        info["error"] = f"Voicebox no responde: {str(exc)[:120]}"
        return info
    info["ok"] = True
    return info
