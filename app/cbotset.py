"""Lee un `.cbotset` de cTrader: los valores que TÚ tienes puestos.

Por qué hace falta, y por qué importa más de lo que parece: el `.algo` trae los
valores **por defecto** del bot, no los tuyos. Si tu Confluence Bot lleva el
break-even a 12 pips y el `.algo` dice 20, Hydra estaba gestionando con 20 — un
número que no usa nadie. Todo lo que se deduce de los parámetros (break-even,
trailing, parciales) sale mal por ahí sin que salte ningún error.

Un `.cbotset` es lo que guarda cTrader al pulsar «Save» en los ajustes de una
instancia del bot. Es el archivo que hay que subir cuando cambias algo a mano.

Sobre el formato: cTrader lo ha guardado en XML y en JSON según la versión, y no
siempre con las mismas etiquetas. Aquí se aceptan las formas conocidas de las dos
familias y, si no se reconoce ninguna, se dice claramente en vez de devolver un
diccionario vacío que parecería «no tiene parámetros».
"""
from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET

# Nombres de atributo/etiqueta que usan las distintas versiones para lo mismo.
_NAME_ATTRS = ("Name", "name", "Key", "key", "PropertyName", "propertyName")
_VALUE_ATTRS = ("Value", "value", "Val", "val")


class CbotsetError(RuntimeError):
    pass


def _coerce(v):
    """'12.5' -> 12.5, 'true' -> True. El texto se queda como texto.

    Se convierte a propósito: los valores llegan siempre como cadena y compararlos
    con el valor por defecto (que sí es número) daría «cambiado» en todo.
    """
    if isinstance(v, (int, float, bool)) or v is None:
        return v
    s = str(v).strip()
    low = s.lower()
    if low in ("true", "false"):
        return low == "true"
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s.replace(",", "."))
    except ValueError:
        return s


def _from_json(raw: str) -> dict:
    data = json.loads(raw)
    out: dict = {}

    def comer(obj):
        """Recorre cualquier anidamiento y recoge los pares nombre/valor."""
        if isinstance(obj, dict):
            # forma {"Name": "Risk", "Value": 1.0}
            nombre = next((obj[k] for k in _NAME_ATTRS if k in obj), None)
            valor = next((obj[k] for k in _VALUE_ATTRS if k in obj), None)
            if isinstance(nombre, str) and valor is not None and not isinstance(valor, (dict, list)):
                out[nombre] = _coerce(valor)
                return
            for k, v in obj.items():
                if isinstance(v, (dict, list)):
                    comer(v)
                elif isinstance(k, str):
                    # forma plana {"Risk": 1.0}
                    out[k] = _coerce(v)
        elif isinstance(obj, list):
            for x in obj:
                comer(x)

    comer(data)
    return out


def _from_xml(raw: str) -> dict:
    root = ET.fromstring(raw)
    out: dict = {}
    for el in root.iter():
        nombre = next((el.attrib[k] for k in _NAME_ATTRS if k in el.attrib), None)
        valor = next((el.attrib[k] for k in _VALUE_ATTRS if k in el.attrib), None)
        if nombre:
            # <Parameter Name="Risk" Value="1.0"/> o <Parameter Name="Risk">1.0</Parameter>
            out[nombre] = _coerce(valor if valor is not None else (el.text or ""))
            continue
        # <Risk>1.0</Risk>, solo hojas: un nodo con hijos no es un parámetro
        if len(el) == 0 and el.text and el.text.strip() and el is not root:
            out[el.tag] = _coerce(el.text)
    return out


# claves de envoltorio que no son parámetros del bot
_IGNORAR = {"parameters", "parametersroot", "root", "parameter", "params",
            "instance", "settings", "botsettings", "cbotsettings", "version",
            "schemaversion", "type", "name", "botname", "robotname"}


def parse(raw: bytes | str) -> dict:
    """Devuelve {"values": {nombre: valor}, "format": "json"|"xml", "n": int}.

    No adivina: si el archivo no se parece a ninguna forma conocida, levanta
    `CbotsetError`. Devolver {} en silencio se leería como «este bot no tiene nada
    configurado», que es justo la conclusión equivocada.
    """
    txt = raw.decode("utf-8-sig", "replace") if isinstance(raw, bytes) else raw
    txt = txt.strip()
    if not txt:
        raise CbotsetError("el archivo está vacío")

    fmt, vals, err = "", {}, ""
    if txt[:1] in "{[":
        fmt = "json"
        try:
            vals = _from_json(txt)
        except json.JSONDecodeError as exc:
            err = f"JSON inválido: {exc}"
    elif txt[:1] == "<":
        fmt = "xml"
        try:
            vals = _from_xml(txt)
        except ET.ParseError as exc:
            err = f"XML inválido: {exc}"
    else:
        err = "no es ni XML ni JSON"
    if err:
        raise CbotsetError(f"no pude leer el .cbotset: {err}")

    # fuera los envoltorios y los nombres que no parecen un parámetro
    vals = {k: v for k, v in vals.items()
            if re.sub(r"[^a-z0-9]", "", k.lower()) not in _IGNORAR}
    if not vals:
        raise CbotsetError(
            "el archivo se leyó pero no traía ningún parámetro reconocible. "
            "¿Es de verdad un .cbotset guardado desde los ajustes del bot?")
    return {"values": vals, "format": fmt, "n": len(vals)}


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower())


def apply_to(parsed: dict, values: dict) -> dict:
    """Mete tus valores en los parámetros leídos del .algo.

    Devuelve qué casó y qué no. Lo que no casa se dice: un parámetro del preset que
    no existe en el bot casi siempre significa que el `.cbotset` es de OTRO bot, y
    eso hay que verlo antes de gestionar posiciones con esos números.

    El valor por defecto NO se pisa: se guarda aparte en `value`, para poder enseñar
    los dos y marcar lo que has cambiado.
    """
    porn = {}
    for g in parsed.get("groups") or []:
        for p in g.get("params") or []:
            porn.setdefault(_norm(p.get("name")), []).append(p)

    casados, huerfanos, cambiados = [], [], []
    for nombre, valor in (values or {}).items():
        objetivo = porn.get(_norm(nombre))
        if not objetivo:
            huerfanos.append(nombre)
            continue
        for p in objetivo:
            p["value"] = valor
            p["from_preset"] = True
        casados.append(nombre)
        if _coerce(objetivo[0].get("default")) != _coerce(valor):
            cambiados.append({"name": nombre, "default": objetivo[0].get("default"),
                              "value": valor})

    total = sum(len(v) for v in porn.values())
    return {"matched": casados, "unmatched": huerfanos, "changed": cambiados,
            "n_matched": len(casados), "n_unmatched": len(huerfanos),
            "n_changed": len(cambiados), "n_params": total,
            # Si casa poco, lo más probable es que el preset sea de OTRO bot.
            # Que no case NADA es el caso más sospechoso de todos, no el menos:
            # tratarlo como bueno dejaba pasar en silencio el preset equivocado.
            "suspect": bool(huerfanos) and len(huerfanos) > len(casados)}
