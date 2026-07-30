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
        "chart_bound": chart_bound,
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
