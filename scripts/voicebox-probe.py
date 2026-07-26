#!/usr/bin/env python3
"""Sonda del servidor MCP de Voicebox: descubre qué herramientas expone.

Voicebox corre un servidor MCP dentro de la app (solo mientras esté abierta).
Este script hace el saludo MCP y lista las herramientas con sus parámetros,
para poder conectar Hydra a la generación de voz local.

    python scripts/voicebox-probe.py

No manda nada a internet: todo es contra 127.0.0.1.
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request

_ARGS = [a for a in sys.argv[1:]]
_CALL: str | None = None
_CALL_ARGS: dict = {}
if "--call" in _ARGS:
    i = _ARGS.index("--call")
    _CALL = _ARGS[i + 1] if len(_ARGS) > i + 1 else None
    if len(_ARGS) > i + 2:
        _CALL_ARGS = json.loads(_ARGS[i + 2])
    _ARGS = _ARGS[:i]

URL = _ARGS[0] if _ARGS else "http://127.0.0.1:17493/mcp"
SESSION: dict = {"id": None, "url": URL}


def _post(url: str, payload: bytes, depth: int = 0):
    """POST siguiendo redirects a mano.

    urllib NO sigue un 307/308 cuando el método es POST (lanza HTTPError), y los
    servidores MCP suelen redirigir /mcp → /mcp/. Sin esto, la sonda se rinde
    contra un servidor que está perfectamente vivo.
    """
    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json",
                 "Accept": "application/json, text/event-stream",
                 **({"Mcp-Session-Id": SESSION["id"]} if SESSION["id"] else {})},
        method="POST")
    try:
        return urllib.request.urlopen(req, timeout=30)
    except urllib.error.HTTPError as exc:
        if exc.code in (301, 302, 307, 308) and depth < 4:
            loc = exc.headers.get("Location")
            if loc:
                nxt = urllib.parse.urljoin(url, loc)
                SESSION["url"] = nxt          # recuérdalo para las siguientes
                return _post(nxt, payload, depth + 1)
        raise


def rpc(method: str, params: dict | None = None, notify: bool = False):
    body = {"jsonrpc": "2.0", "method": method}
    if params is not None:
        body["params"] = params
    if not notify:
        body["id"] = 1
    with _post(SESSION["url"], json.dumps(body).encode()) as r:
        if not SESSION["id"]:
            SESSION["id"] = r.headers.get("Mcp-Session-Id")
        raw = r.read().decode("utf-8", "replace")
    if not raw.strip():
        return None
    # la respuesta puede venir como SSE ("data: {...}") o como JSON pelón
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


def main() -> int:
    print(f"→ Conectando a {URL}\n")
    try:
        init = rpc("initialize", {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "hydra-probe", "version": "1.0"}})
    except urllib.error.HTTPError as exc:
        # el servidor SÍ contestó: es un problema de protocolo, no de arranque
        detail = exc.read().decode("utf-8", "replace")[:400]
        print(f"❌ El servidor respondió HTTP {exc.code} ({exc.reason})\n")
        if detail.strip():
            print(f"   {detail}\n")
        print(f"   Prueba apuntando a otra ruta, p.ej.:\n"
              f"     python3 {sys.argv[0]} {URL.rstrip('/')}/")
        return 1
    except urllib.error.URLError as exc:
        print(f"❌ No responde: {exc.reason}\n")
        print("   ¿Está abierta la app Voicebox? El servidor corre DENTRO de ella.")
        print("   Ábrela desde /Applications y vuelve a correr esto.")
        return 1

    info = ((init or {}).get("result") or {}).get("serverInfo") or {}
    print(f"✅ Conectado: {info.get('name', '?')} v{info.get('version', '?')}\n")
    try:
        rpc("notifications/initialized", {}, notify=True)
    except Exception:  # noqa: BLE001 - algunos servidores no la requieren
        pass

    res = rpc("tools/list", {})
    tools = ((res or {}).get("result") or {}).get("tools") or []
    if not tools:
        print("⚠️  No listó herramientas. Respuesta cruda:")
        print(json.dumps(res, indent=2, ensure_ascii=False)[:1500])
        return 1

    print(f"🔧 {len(tools)} herramientas:\n" + "=" * 60)
    for t in tools:
        print(f"\n▸ {t.get('name')}")
        desc = (t.get("description") or "").strip().replace("\n", " ")
        if desc:
            print(f"  {desc[:300]}")
        props = ((t.get("inputSchema") or {}).get("properties") or {})
        req = set((t.get("inputSchema") or {}).get("required") or [])
        for pname, pinfo in props.items():
            star = "*" if pname in req else " "
            print(f"   {star} {pname} ({_type_of(pinfo)})"
                  + (f" — {(pinfo.get('description') or '')[:90]}"
                     if pinfo.get("description") else ""))

    print("\n" + "=" * 60)
    print("Para llamar una herramienta:")
    print(f"  python3 {sys.argv[0]} --call voicebox.list_profiles")
    return 0


def _type_of(p: dict) -> str:
    """Describe el tipo de un parámetro, incluso si viene envuelto en anyOf/$ref.

    Los esquemas generados por Pydantic suelen poner los opcionales como
    anyOf:[{...},{type:null}] — sin esto se veían todos como '?'.
    """
    if "enum" in p:
        e = p["enum"]
        return "[" + ", ".join(map(str, e[:14])) + ("…" if len(e) > 14 else "") + "]"
    if p.get("type"):
        return str(p["type"])
    for key in ("anyOf", "oneOf", "allOf"):
        if key in p:
            parts = [_type_of(s) for s in p[key] if s.get("type") != "null"]
            parts = [x for x in parts if x != "?"]
            if parts:
                return " | ".join(dict.fromkeys(parts)) + (
                    " (opcional)" if any(s.get("type") == "null" for s in p[key]) else "")
    if "$ref" in p:
        return p["$ref"].rsplit("/", 1)[-1]
    return "?"


def call(name: str, args: dict) -> int:
    """Llama una herramienta y muestra la respuesta."""
    try:
        rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                           "clientInfo": {"name": "hydra-probe", "version": "1.0"}})
        try:
            rpc("notifications/initialized", {}, notify=True)
        except Exception:  # noqa: BLE001
            pass
        res = rpc("tools/call", {"name": name, "arguments": args})
    except urllib.error.URLError as exc:
        print(f"❌ {getattr(exc, 'reason', exc)}")
        return 1
    result = (res or {}).get("result") or res
    # el contenido suele venir como bloques de texto con JSON dentro
    for block in (result.get("content") or []) if isinstance(result, dict) else []:
        if block.get("type") == "text":
            txt = block.get("text", "")
            try:
                print(json.dumps(json.loads(txt), indent=2, ensure_ascii=False)[:6000])
            except json.JSONDecodeError:
                print(txt[:6000])
            return 0
    print(json.dumps(result, indent=2, ensure_ascii=False)[:6000])
    return 0


if __name__ == "__main__":
    sys.exit(call(_CALL, _CALL_ARGS) if _CALL else main())
