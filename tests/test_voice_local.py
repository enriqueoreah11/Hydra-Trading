"""La voz local: elección de motor, elección de voz y cadena de efectos.

No se puede probar aquí cómo SUENA. Lo que sí se puede probar es todo lo que hace
que no suene: elegir una voz que no está instalada, mandarle a ffmpeg una velocidad
que rechaza, anunciar un WAV como si fuera MP3, o quedarse sin voz porque el motor
bueno no está cuando el Mac tenía uno de sobra.
"""
import asyncio

import pytest
from pathlib import Path

from app import voice_local as vl


@pytest.fixture(autouse=True)
def limpio(monkeypatch, tmp_path):
    monkeypatch.setattr(vl.settings, "data_dir", str(tmp_path))
    monkeypatch.setattr(vl.settings, "local_voice", "")
    monkeypatch.setattr(vl.settings, "voice_fx", "jarvis")
    monkeypatch.setattr(vl.settings, "voice_speed", 1.0)
    return tmp_path


def modelo(tmp_path, nombre):
    d = tmp_path / "voices"
    d.mkdir(exist_ok=True)
    p = d / f"{nombre}.onnx"
    p.write_bytes(b"onnx")
    return p


# ------------------------------------------------------------ elección de voz

def test_the_british_voice_wins_over_the_default_one(monkeypatch):
    """El acento es media caracterización: si está Daniel, no se usa Alex."""
    monkeypatch.setattr(vl.shutil, "which", lambda n: "/usr/bin/say" if n == "say" else None)
    monkeypatch.setattr(vl, "say_voices", lambda: ["Alex", "Samantha", "Daniel (Enhanced)"])
    assert vl.pick_say_voice() == "Daniel (Enhanced)"


def test_enhanced_beats_the_plain_version(monkeypatch):
    monkeypatch.setattr(vl, "say_voices", lambda: ["Daniel", "Daniel (Enhanced)"])
    assert vl.pick_say_voice() == "Daniel (Enhanced)"


def test_a_voice_that_is_not_installed_is_not_used(monkeypatch):
    """Pedir una voz que no está y usarla igual daría un error del sistema y silencio."""
    monkeypatch.setattr(vl.settings, "local_voice", "Daniel (Premium)")
    monkeypatch.setattr(vl, "say_voices", lambda: ["Alex", "Daniel"])
    assert vl.pick_say_voice() == "Daniel"          # cae a la mejor que SÍ está


def test_without_voices_it_returns_nothing_instead_of_inventing(monkeypatch):
    monkeypatch.setattr(vl, "say_voices", lambda: [])
    assert vl.pick_say_voice() == ""


def test_the_best_piper_model_is_chosen_by_preference_not_alphabet(limpio):
    modelo(limpio, "es_ES-carlfm-x_low")
    modelo(limpio, "en_GB-alan-medium")
    assert vl.pick_model().stem == "en_GB-alan-medium"


def test_the_chosen_model_wins_over_the_preference(limpio, monkeypatch):
    modelo(limpio, "en_GB-alan-medium")
    modelo(limpio, "es_ES-carlfm-x_low")
    monkeypatch.setattr(vl.settings, "local_voice", "es_ES-carlfm-x_low")
    assert vl.pick_model().stem == "es_ES-carlfm-x_low"


def test_no_models_no_piper(limpio):
    assert vl.pick_model() is None and vl.piper_models() == []


# --------------------------------------------------------------- qué se usaría

def test_piper_is_preferred_but_say_keeps_the_voice_alive(limpio, monkeypatch):
    """Sin Piper NO hay que quedarse mudo: el Mac ya trae `say`."""
    monkeypatch.setattr(vl, "_piper_cmd", lambda: None)
    monkeypatch.setattr(vl.shutil, "which", lambda n: "/usr/bin/say" if n == "say" else None)
    monkeypatch.setattr(vl, "say_voices", lambda: ["Daniel (Enhanced)"])
    assert vl.engines()["activo"] == "say" and vl.available()

    modelo(limpio, "en_GB-alan-medium")
    monkeypatch.setattr(vl, "_piper_cmd", lambda: ["piper"])
    assert vl.engines()["activo"] == "piper"        # en cuanto está, manda


def test_with_nothing_installed_it_admits_it(monkeypatch):
    monkeypatch.setattr(vl, "_piper_cmd", lambda: None)
    monkeypatch.setattr(vl.shutil, "which", lambda n: None)
    monkeypatch.setattr(vl, "say_voices", lambda: [])
    assert vl.engines()["activo"] == "" and not vl.available()


# ------------------------------------------------------------------- efectos

def test_the_jarvis_chain_is_applied_and_the_output_is_mp3(tmp_path):
    args = vl._fx_args(tmp_path / "o.mp3", tmp_path / "i.wav")
    chain = args[args.index("-af") + 1]
    assert "aecho" in chain and "acompressor" in chain      # sala + volumen parejo
    assert "libmp3lame" in args


def test_the_clean_mode_has_no_room(tmp_path, monkeypatch):
    monkeypatch.setattr(vl.settings, "voice_fx", "limpio")
    chain = vl._fx_args(tmp_path / "o.mp3", tmp_path / "i.wav")
    assert "aecho" not in chain[chain.index("-af") + 1]


def test_no_effect_means_no_filter_at_all(tmp_path, monkeypatch):
    monkeypatch.setattr(vl.settings, "voice_fx", "")
    assert "-af" not in vl._fx_args(tmp_path / "o.mp3", tmp_path / "i.wav")


def test_speed_stays_inside_what_ffmpeg_accepts(tmp_path, monkeypatch):
    """atempo solo admite 0.5–2.0. Fuera de ahí ffmpeg falla y te quedas sin voz."""
    for pedido, esperado in ((0.1, 0.5), (9.0, 2.0)):
        monkeypatch.setattr(vl.settings, "voice_speed", pedido)
        args = vl._fx_args(tmp_path / "o.mp3", tmp_path / "i.wav")
        assert f"atempo={esperado:.3f}" in args[args.index("-af") + 1]


def test_speed_one_does_not_add_a_pointless_filter(tmp_path, monkeypatch):
    monkeypatch.setattr(vl.settings, "voice_speed", 1.0)
    assert "atempo" not in vl._fx_args(tmp_path / "o.mp3", tmp_path / "i.wav")[
        vl._fx_args(tmp_path / "o.mp3", tmp_path / "i.wav").index("-af") + 1]


# -------------------------------------------------------------------- formato

def test_wav_and_mp3_are_announced_for_what_they_are():
    """Sin ffmpeg sale WAV. Anunciarlo como audio/mpeg hace que algunos navegadores
    no lo reproduzcan, y desde fuera parece que 'la voz no funciona'."""
    assert vl.mime(b"RIFF....WAVEfmt ") == "audio/wav"
    assert vl.mime(b"ID3\x03\x00\x00") == "audio/mpeg"


def motor_falso(monkeypatch, tmp_path, falla=(), ffmpeg=True):
    """Sustituye los programas externos: escriben un archivo en vez de hablar.

    Devuelve la lista de programas invocados, que es lo que permite comprobar el
    orden de preferencia y las caídas de un motor a otro.
    """
    llamadas = []

    async def _run(args, stdin=None, timeout=60):
        llamadas.append(args[0])
        if args[0] in falla:
            return False
        # cada programa dice su salida de una forma: `say` con -o, los otros al final
        destino = Path(args[args.index("-o") + 1] if "-o" in args else args[-1])
        destino.write_bytes((b"ID3\x03" if args[0] == "ffmpeg" else b"RIFF") + b"\0" * 400)
        return True

    monkeypatch.setattr(vl, "_run", _run)
    monkeypatch.setattr(vl.shutil, "which",
                        lambda n: f"/usr/bin/{n}" if (n != "ffmpeg" or ffmpeg) else None)
    return llamadas


def test_if_piper_fails_the_mac_voice_takes_over(monkeypatch, limpio):
    """Un motor roto no puede dejar la app muda si hay otro al lado."""
    modelo(limpio, "en_GB-alan-medium")
    monkeypatch.setattr(vl, "_piper_cmd", lambda: ["piper"])
    monkeypatch.setattr(vl, "pick_say_voice", lambda: "Daniel (Enhanced)")
    llamadas = motor_falso(monkeypatch, limpio, falla=("piper",))
    audio = asyncio.run(vl.synth("hola"))
    assert audio, "se quedó sin voz teniendo `say` disponible"
    assert llamadas == ["piper", "say", "ffmpeg"]      # lo intenta en orden


def test_without_ffmpeg_the_voice_still_comes_out_raw(monkeypatch, limpio):
    """El efecto es un adorno; quedarse sin voz por no tener ffmpeg, no."""
    monkeypatch.setattr(vl, "_piper_cmd", lambda: None)
    monkeypatch.setattr(vl, "pick_say_voice", lambda: "Daniel")
    llamadas = motor_falso(monkeypatch, limpio, ffmpeg=False)
    audio = asyncio.run(vl.synth("hola"))
    assert audio and vl.mime(audio) == "audio/wav"
    assert "ffmpeg" not in llamadas


def test_if_the_effect_fails_the_clean_voice_is_returned(monkeypatch, limpio):
    monkeypatch.setattr(vl, "_piper_cmd", lambda: None)
    monkeypatch.setattr(vl, "pick_say_voice", lambda: "Daniel")
    motor_falso(monkeypatch, limpio, falla=("ffmpeg",))
    audio = asyncio.run(vl.synth("hola"))
    assert audio and vl.mime(audio) == "audio/wav"     # sin efecto, pero se oye


def test_with_no_engine_it_explains_instead_of_failing_silently(monkeypatch):
    monkeypatch.setattr(vl, "_piper_cmd", lambda: None)
    monkeypatch.setattr(vl, "pick_say_voice", lambda: "")
    assert asyncio.run(vl.synth("hola")) is None
    assert "motor de voz local" in vl.last_error()


def test_empty_text_is_not_sent_to_the_engine(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("no debería llamarse al motor con texto vacío")
    monkeypatch.setattr(vl, "_run", boom)
    assert asyncio.run(vl.synth("   ")) is None
