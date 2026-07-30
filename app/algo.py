"""Lee un .algo de cTrader y saca sus parámetros.

El contenedor es: los 4 bytes `algo`, 5 bytes de versión, y a partir del offset 9
un flujo gzip con los METADATOS en JSON. Detrás viene la DLL compilada, que no
nos sirve: es .NET y solo la ejecuta el host de cTrader.

Ojo con `gzip.decompress`: revienta con "Not a gzipped file" porque intenta leer
la DLL como un segundo miembro gzip. Hay que usar un descompresor que se pare al
final del flujo y deje el resto en `unused_data`.
"""
from __future__ import annotations

import json
import zlib

MAGIC = b"algo"
GZIP_OFFSET = 9

# Los parámetros que leen objetos dibujados A MANO en el gráfico de cTrader no se
# pueden reproducir fuera de él: no hay gráfico ni dibujos. Se marcan para poder
# avisar antes de que alguien espere una réplica exacta.
_CHART_HINTS = ("chartread", "chartonly", "chartsource", "usechart", "readchart")

# PERO hay que mirar el modo ELEGIDO antes de acusar a nadie. Muchos bots detectan
# ellos mismos sus niveles y solo LEEN dibujos si se les pide. En AutoOnly no leen
# ninguno, así que decir "lee dibujos a mano" sería falso. Estos son los valores
# típicos del selector de fuente y lo que implican de verdad.
_MODE_BY_VALUE = {"autoonly": "auto", "auto": "auto", "internal": "auto",
                  "indicators": "auto", "chartonly": "chart", "chart": "chart",
                  "manual": "chart", "drawings": "chart",
                  "combined": "mixto", "both": "mixto", "mixed": "mixto"}


class AlgoError(RuntimeError):
    pass


def _meta(raw: bytes) -> dict:
    if raw[:4] != MAGIC:
        raise AlgoError("no parece un .algo de cTrader (falta la marca 'algo')")
    try:
        dec = zlib.decompressobj(16 + 15)          # 16 = espera cabecera gzip
        body = dec.decompress(raw[GZIP_OFFSET:])
    except zlib.error as exc:
        raise AlgoError(f"no pude descomprimir los metadatos: {exc}") from None
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise AlgoError(f"los metadatos no son JSON válido: {exc}") from None


def _is_chart_bound(param: dict) -> bool:
    blob = (str(param.get("PropertyName", "")) + " "
            + str(param.get("FriendlyName", ""))).lower()
    if any(h in blob.replace(" ", "").replace("—", "") for h in _CHART_HINTS):
        return True
    # un enum con la opcion ChartOnly tambien depende del grafico
    return "ChartOnly" in (param.get("EnumValues") or {})


def _enum_pick(param: dict) -> str:
    """El valor ELEGIDO de un enum, por nombre. El defecto suele venir por índice."""
    names = list(param.get("enum") or {})
    cur = param.get("default")
    if isinstance(cur, bool):
        return str(cur)
    if isinstance(cur, int) and 0 <= cur < len(names):
        return names[cur]
    return str(cur)


def _chart_mode(items: list[dict]) -> tuple[str, str]:
    """Cómo consigue el bot sus niveles: solos, de tus dibujos, o las dos cosas.

    Se lee del selector de fuente (el enum que ofrece ChartOnly). Sin selector no
    se puede afirmar nada, y eso también hay que decirlo.
    """
    for p in items:
        if "ChartOnly" in (p.get("enum") or {}):
            return _MODE_BY_VALUE.get(_enum_pick(p).lower(), "mixto"), p["name"]
    return "desconocido", ""


def parse(raw: bytes) -> dict:
    """Devuelve nombre, versión y los parámetros agrupados como los ve cTrader."""
    meta = _meta(raw)
    types = meta.get("Types") or []
    if not types:
        raise AlgoError("el .algo no declara ningún robot ni indicador")
    t = types[0]

    groups: dict[str, list] = {}
    chart_bound: list[str] = []
    for p in t.get("Parameters") or []:
        prop = str(p.get("PropertyName") or "")
        if not prop:
            continue
        item = {
            "name": prop,
            "label": p.get("FriendlyName") or prop,
            "type": p.get("ParameterType") or "?",
            "default": p.get("DefaultValue"),
            "min": p.get("MinValue"),
            "max": p.get("MaxValue"),
            "step": p.get("Step"),
            "enum": p.get("EnumValues") or None,
            "chart_bound": _is_chart_bound(p),
        }
        if item["chart_bound"]:
            chart_bound.append(prop)
        groups.setdefault(str(p.get("GroupName") or "Sin grupo"), []).append(item)

    # Ahora que están todos, se mira el MODO para no acusar en falso. Un parámetro
    # que puede leer dibujos solo los lee si el modo lo pide y si está activado.
    allp = [p for g in groups.values() for p in g]
    mode, mode_param = _chart_mode(allp)
    if mode == "auto":                    # el bot se calcula sus propios niveles
        real, maybe = [], list(chart_bound)
    elif mode == "chart":                 # depende del gráfico y punto
        real, maybe = list(chart_bound), []
    else:                                 # mixto (o sin selector): solo lo activado
        real, maybe = [], []
        for p in allp:
            if not p["chart_bound"]:
                continue
            off = p.get("default") is False or _enum_pick(p).lower() == "false"
            (maybe if off else real).append(p["name"])
        if mode_param and mode_param in real:
            real.remove(mode_param)       # el selector no es un dibujo, es el modo
            maybe.append(mode_param)
    for p in allp:                        # que la marca por parámetro no engañe
        p["chart_bound"] = p["name"] in real
    total = sum(len(v) for v in groups.values())
    # ¿Este bot puede reportar a Hydra? Solo si QUIEN LO ESCRIBIÓ le puso esos
    # parámetros. No se pueden añadir desde fuera: habría que tocar su código y
    # recompilarlo. Conviene saberlo antes de buscar una casilla que no existe.
    flat = {p["name"].lower(): p["name"]
            for g in groups.values() for p in g}
    remote = {k: flat[k] for k in
              ("backendurl", "backendapikey", "enableremotelogging", "remoteinstanceid")
              if k in flat}
    return {
        "name": t.get("FriendlyName") or t.get("ShortName") or t.get("TypeName") or "bot",
        "type_name": t.get("TypeName"),
        "kind": meta.get("Flags"),                 # Robot | Indicator
        "api_version": meta.get("ApiVersion"),
        "framework": meta.get("TargetFramework"),
        "built_at": meta.get("Timestamp"),
        "source_included": bool((meta.get("Store") or {}).get("SourceIncluded")),
        "n_params": total,
        "n_groups": len(groups),
        "chart_bound": real,           # los que HOY leen dibujos, con estos valores
        "chart_maybe": maybe,          # los que podrían, si cambias el modo
        "chart_mode": mode,            # auto | chart | mixto | desconocido
        "chart_mode_param": mode_param,
        "can_report": len(remote) >= 2,        # url + interruptor, como mínimo
        "remote_params": remote,
        "groups": [{"group": g, "params": ps} for g, ps in groups.items()],
    }


def defaults(parsed: dict) -> dict:
    """Los valores por defecto, planos: {PropertyName: valor}."""
    out: dict = {}
    for g in parsed.get("groups") or []:
        for p in g["params"]:
            out[p["name"]] = p["default"]
    return out
