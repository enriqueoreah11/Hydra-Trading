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


def main() -> int:
    print(f"→ {MCP}")
    rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                       "clientInfo": {"name": "hydra", "version": "1.0"}})
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

    status: dict = {}
    for i in range(20):
        code, body, _ = get(f"{BASE}/generate/{gen}/status")
        if code != 200:
            print(f"\n❌ /generate/{gen}/status → HTTP {code}: {body[:200]!r}")
            break
        try:
            status = json.loads(body)
        except json.JSONDecodeError:
            print(f"\n(status no es JSON) {body[:300]!r}")
            break
        st = str(status.get("status") or status.get("state") or "")
        if st.lower() in ("done", "complete", "completed", "finished", "ready", "success"):
            break
        print(f"   … {st or 'en curso'} ({i + 1})")
        time.sleep(1)

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
                  f"{BASE}/generate/{gen}/file", f"{BASE}/generate/{gen}"):
        code, body, ctype = get(guess)
        flag = "✅" if code == 200 and (ctype.startswith("audio") or len(body) > 5000) else "  "
        print(f"{flag} {guess}  →  HTTP {code}, {len(body)} bytes, {ctype or '—'}")
    if not paths and not urls:
        print("  (el status no traía ninguna ruta ni URL)")

    print("\nCopia TODO esto y pégamelo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
