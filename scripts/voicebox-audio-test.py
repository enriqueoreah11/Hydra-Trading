#!/usr/bin/env python3
"""¿Se puede RECUPERAR el audio de Voicebox, o solo dispararlo a las bocinas?

voicebox.speak dice que reproduce en las bocinas y devuelve un id consultable en
/generate/{id}/status. Si por ahí sale una ruta o una URL al archivo, Hydra puede
servir el audio al navegador igual que hoy hace con ElevenLabs — y entonces
silenciar, parar y el control de volumen siguen funcionando.

Este script lo comprueba de punta a punta:
    1. pide a Voicebox que hable  (⚠️ VA A SONAR EN TUS BOCINAS)
    2. saca el id de generación
    3. consulta /generate/{id}/status
    4. si aparece un archivo, lo busca y reporta tamaño y tipo

    python3 scripts/voicebox-audio-test.py
    python3 scripts/voicebox-audio-test.py "otro texto" Jarvis
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:17493"
MCP = BASE + "/mcp"
TEXT = sys.argv[1] if len(sys.argv) > 1 else "Hola Krauser, prueba de voz desde Hydra."
PROFILE = sys.argv[2] if len(sys.argv) > 2 else "Jarvis"
SESSION: dict = {"id": None, "url": MCP}


def _post(url: str, payload: bytes, depth: int = 0):
    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json",
                 "Accept": "application/json, text/event-stream",
                 **({"Mcp-Session-Id": SESSION["id"]} if SESSION["id"] else {})},
        method="POST")
    try:
        return urllib.request.urlopen(req, timeout=120)
    except urllib.error.HTTPError as exc:
        if exc.code in (301, 302, 307, 308) and depth < 4:
            loc = exc.headers.get("Location")
            if loc:
                SESSION["url"] = urllib.parse.urljoin(url, loc)
                return _post(SESSION["url"], payload, depth + 1)
        raise


def rpc(method: str, params: dict | None = None, notify: bool = False):
    body: dict = {"jsonrpc": "2.0", "method": method}
    if params is not None:
        body["params"] = params
    if not notify:
        body["id"] = 1
    with _post(SESSION["url"], json.dumps(body).encode()) as r:
        if not SESSION["id"]:
            SESSION["id"] = r.headers.get("Mcp-Session-Id")
        raw = r.read().decode("utf-8", "replace")
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            line = line[5:].strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return raw


def get(url: str) -> tuple[int, bytes, str]:
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return r.status, r.read(), r.headers.get("Content-Type", "")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()[:400], exc.headers.get("Content-Type", "")
    except urllib.error.URLError as exc:
        return 0, str(exc.reason).encode(), ""


TERMINAL = {"done", "complete", "completed", "finished", "ready", "success",
            "error", "failed", "cancelled", "canceled"}


def sse_wait(url: str, timeout: float = 180) -> dict:
    """Consume el stream SSE de estado hasta que termine.

    /generate/{id}/status NO es un JSON de una sola lectura: es un flujo de
    eventos `data: {...}` que sigue abierto mientras genera. Hay que leerlo
    línea por línea y cortar al llegar a un estado terminal.
    """
    req = urllib.request.Request(url, headers={"Accept": "text/event-stream"})
    last: dict = {}
    seen = ""
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            for raw in r:
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                try:
                    ev = json.loads(line[5:].strip())
                except json.JSONDecodeError:
                    continue
                last = ev
                st = str(ev.get("status") or "").lower()
                if st != seen:                    # solo avisa cuando cambia
                    print(f"   … {st} ({time.time() - t0:.0f}s)")
                    seen = st
                if st in TERMINAL:
                    break
                if time.time() - t0 > timeout:
                    break
    except Exception as exc:  # noqa: BLE001 - el stream puede cortarse al final
        if last:
            print(f"   (stream cerrado: {type(exc).__name__})")
        else:
            print(f"   ❌ {type(exc).__name__}: {exc}")
    return last


def main() -> int:
    print(f"→ {MCP}")
    try:
        rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                           "clientInfo": {"name": "hydra", "version": "1.0"}})
    except urllib.error.URLError as exc:
        print(f"\n❌ No responde: {getattr(exc, 'reason', exc)}\n")
        print("   La app Voicebox debe estar ABIERTA — el servidor corre dentro de ella.")
        print("   Ábrela desde /Applications y vuelve a correr esto.")
        return 1
    try:
        rpc("notifications/initialized", {}, notify=True)
    except Exception:  # noqa: BLE001
        pass

    print(f"\n🔊 Generando (va a sonar): {TEXT!r}  ·  perfil {PROFILE!r}")
    res = rpc("tools/call", {"name": "voicebox.speak",
                             "arguments": {"text": TEXT, "profile": PROFILE}})
    result = (res or {}).get("result") or res
    payload: dict = {}
    print("\n--- respuesta cruda de speak ---")
    for block in (result.get("content") or []) if isinstance(result, dict) else []:
        if block.get("type") == "text":
            txt = block.get("text", "")
            print(txt[:1200])
            try:
                payload = json.loads(txt)
            except json.JSONDecodeError:
                pass
    if not payload:
        print(json.dumps(result, indent=2, ensure_ascii=False)[:1200])

    blob = json.dumps(payload) if payload else json.dumps(result)
    m = re.search(r'"(?:generation_?id|id)"\s*:\s*"([^"]+)"', blob)
    gen = m.group(1) if m else None
    if not gen:
        print("\n⚠️  No encontré un id de generación en la respuesta.")
        return 1
    print(f"\n🆔 id de generación: {gen}")

    # Voicebox nos da la ruta de consulta; úsala en vez de inventarla
    poll = payload.get("poll_url") or f"/generate/{gen}/status"
    poll_url = urllib.parse.urljoin(BASE, poll)
    print(f"⏳ Escuchando {poll_url}")
    print("   (la PRIMERA vez tarda: carga el modelo de voz. No escribas nada.)")
    status = sse_wait(poll_url)

    if status:
        print("\n--- status completo ---")
        print(json.dumps(status, indent=2, ensure_ascii=False)[:2000])

    # ¿hay una ruta o URL al audio?
    blob2 = json.dumps(status)
    paths = re.findall(r'"([^"]*\.(?:wav|mp3|m4a|ogg|flac))"', blob2, re.IGNORECASE)
    urls = re.findall(r'"(https?://[^"]+)"', blob2)
    print("\n--- ¿podemos leer el audio? ---")
    for p in dict.fromkeys(paths):
        real = p.replace("\\/", "/")
        ok = os.path.isfile(real)
        size = os.path.getsize(real) if ok else 0
        print(f"  archivo {real}  →  {'✅ existe, ' + str(size) + ' bytes' if ok else '❌ no existe'}")
    for u in dict.fromkeys(urls):
        code, body, ctype = get(u)
        print(f"  url {u}  →  HTTP {code}, {len(body)} bytes, {ctype}")
    for guess in (f"{BASE}/generate/{gen}/audio", f"{BASE}/generate/{gen}/download",
                  f"{BASE}/generate/{gen}/file", f"{BASE}/generate/{gen}",
                  f"{BASE}/captures/{gen}/audio", f"{BASE}/audio/{gen}"):
        code, body, ctype = get(guess)
        flag = "✅" if code == 200 and (ctype.startswith("audio") or len(body) > 5000) else "  "
        print(f"{flag} {guess}  →  HTTP {code}, {len(body)} bytes, {ctype or '—'}")
    if not paths and not urls:
        print("  (el status no traía ninguna ruta ni URL)")

    # Voicebox dice que guarda cada generación en la pestaña Captures/History:
    # ahí suele venir la ruta real del archivo.
    print("\n--- capturas recientes (aquí suele estar la ruta del audio) ---")
    try:
        res2 = rpc("tools/call", {"name": "voicebox.list_captures",
                                  "arguments": {"limit": 3}})
        r2 = (res2 or {}).get("result") or res2
        shown = False
        for block in (r2.get("content") or []) if isinstance(r2, dict) else []:
            if block.get("type") == "text":
                txt = block.get("text", "")
                try:
                    print(json.dumps(json.loads(txt), indent=2, ensure_ascii=False)[:2500])
                except json.JSONDecodeError:
                    print(txt[:2500])
                shown = True
        if not shown:
            print(json.dumps(r2, indent=2, ensure_ascii=False)[:2500])
    except Exception as exc:  # noqa: BLE001
        print(f"(no pude listar capturas: {exc})")

    print("\nCopia TODO esto y pégamelo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
