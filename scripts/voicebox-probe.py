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
import urllib.request

URL = "http://127.0.0.1:17493/mcp"
SESSION: dict = {"id": None}


def rpc(method: str, params: dict | None = None, notify: bool = False):
    body = {"jsonrpc": "2.0", "method": method}
    if params is not None:
        body["params"] = params
    if not notify:
        body["id"] = 1
    req = urllib.request.Request(
        URL, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json",
                 "Accept": "application/json, text/event-stream",
                 **({"Mcp-Session-Id": SESSION["id"]} if SESSION["id"] else {})},
        method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
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
            ptype = pinfo.get("type", "?")
            pdesc = (pinfo.get("description") or "")[:90]
            enum = pinfo.get("enum")
            line = f"   {star} {pname} ({ptype})"
            if enum:
                shown = ", ".join(map(str, enum[:12]))
                line += f" = [{shown}{'…' if len(enum) > 12 else ''}]"
            print(line + (f" — {pdesc}" if pdesc else ""))

    print("\n" + "=" * 60)
    print("Copia TODO esto y pégamelo para conectar Hydra a la voz local.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
