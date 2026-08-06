"""Contexto macro: lo que mueve a los CFDs y NO viene del bróker.

Tu bróker te da el precio. No te dice por qué se mueve. Y los CFDs no flotan
solos: el oro responde a los tipos reales, el USDJPY al diferencial de bonos entre
EEUU y Japón, los índices a la volatilidad implícita, y casi todo al dólar.

Fuentes elegidas, y por qué estas:

- **FRED** (Reserva Federal de St. Louis). Oficial, gratis, con clave gratuita, y
  documentada. De ahí salen los tipos nominales y reales, el VIX y el índice dólar.
- **CFTC** (Commitments of Traders). Oficial, gratis y SIN clave. Dice cómo está
  posicionado el dinero grande. Semanal, con retraso: sirve para saber si un
  movimiento está masificado, no para entrar.

Lo que NO se usa, a propósito:

- **Yahoo Finance**: no tiene API oficial; lo que se usa son raspados que se rompen
  cada pocos meses. Para algo que decide sobre dinero, una fuente que se cae sin
  avisar es peor que no tener el dato.
- **Opciones FX (los vencimientos del corte de Nueva York)**: el efecto es real y
  conocido —los strikes grandes atraen al precio y lo clavan hasta el vencimiento—
  pero NO existe una API pública decente. DTCC solo ve las operaciones con
  contraparte en EEUU (Londres, que es el grueso, no aparece), y el resto son
  páginas de noticias que habría que raspar. Se deja fuera hasta poder meterlo con
  una fuente que se sostenga; ver `OPCIONES_FX_NOTA`.

Y una advertencia que va en el propio dato: estas relaciones son TENDENCIAS
históricas, no leyes. El oro y los tipos reales se han desacoplado durante meses
enteros. Por eso esto entra como CONTEXTO que el analista pondera, nunca como una
regla que decide sola.
"""
from __future__ import annotations

import asyncio
import logging
import re
import time

log = logging.getLogger("macro")

# Series de FRED. La clave es como se llaman aqui; el valor, su id en FRED.
FRED_SERIES = {
    "us10y": "DGS10",        # bono EEUU 10 años, nominal
    "us2y": "DGS2",          # 2 años: el tramo que manda en las expectativas de tipos
    "us10y_real": "DFII10",  # 10 años REAL (protegido de inflacion). El del oro.
    "vix": "VIXCLS",         # volatilidad implicita del S&P
    "dxy": "DTWEXBGS",       # indice del dolar amplio de la Fed
    "breakeven10y": "T10YIE",  # inflacion esperada a 10 anos
}

# Codigos de contrato de la CFTC para lo que operas. El nombre exacto importa: la
# CFTC los publica con su nomenclatura, no con la del broker.
COT_CONTRATOS = {
    "XAUUSD": "GOLD - COMMODITY EXCHANGE INC.",
    "XAGUSD": "SILVER - COMMODITY EXCHANGE INC.",
    "XTIUSD": "WTI-PHYSICAL - NEW YORK MERCANTILE EXCHANGE",
    "EURUSD": "EURO FX - CHICAGO MERCANTILE EXCHANGE",
    "GBPUSD": "BRITISH POUND - CHICAGO MERCANTILE EXCHANGE",
    "USDJPY": "JAPANESE YEN - CHICAGO MERCANTILE EXCHANGE",
    "AUDUSD": "AUSTRALIAN DOLLAR - CHICAGO MERCANTILE EXCHANGE",
    "US500": "E-MINI S&P 500 - CHICAGO MERCANTILE EXCHANGE",
    "US100": "NASDAQ MINI - CHICAGO MERCANTILE EXCHANGE",
}

MIN_SEMANAS_COT = 52    # un año: menos no permite decir qué es extremo

OPCIONES_FX_NOTA = (
    "Los vencimientos de opciones FX del corte de Nueva York (10:00 ET) atraen al "
    "precio: los creadores de mercado cubren su riesgo cerca del strike y eso lo "
    "clava hasta el vencimiento. El efecto está documentado, pero no hay fuente "
    "pública fiable: DTCC solo ve la parte con contraparte en EEUU (falta Londres, "
    "que es el grueso) y lo demás son páginas de noticias. Sin fuente que se "
    "sostenga, meterlo sería darle al bot un dato que unos días es correcto y otros "
    "está a medias, sin forma de distinguirlo.")


# --------------------------------------------------------------- familias

_FAM = (
    ("metal", re.compile(r"^(XAU|XAG|XPT|XPD|GOLD|SILVER)")),
    ("energia", re.compile(r"^(XTI|XBR|USOIL|UKOIL|WTI|BRENT|NGAS)")),
    ("indice", re.compile(r"(US100|US30|US500|SPX|NAS|USTEC|DE40|GER40|UK100|JPN225|DAX)")),
    ("cripto", re.compile(r"^(BTC|ETH|XRP|SOL|LTC)")),
)


def familia(symbol: str) -> str:
    s = re.sub(r"[^A-Z0-9]", "", str(symbol or "").upper())
    for nombre, rx in _FAM:
        if rx.search(s):
            return nombre
    if len(s) >= 6 and s[:3].isalpha() and s[3:6].isalpha():
        return "forex"
    return "otro"


# Como se COMPORTA cada familia, que es distinto de que macro la mueve. Vive aqui
# porque aqui vive la clasificacion: tener la familia en un sitio y sus manias en
# otro es como se acaba con un analista que trata un par de forex igual que el oro.
#
# Estas notas se le pasan al analista SEGUN el simbolo que este mirando. Antes iban
# escritas a mano dentro del prompt y solo hablaban de metales, petroleo e indices:
# con pares de forex en la lista, el modelo recibia instrucciones de otro mercado y
# no habia forma de saberlo mirando la salida.
COMPORTAMIENTO = {
    "metal": ("Sensible al dolar y a los tipos reales; la plata amplifica al oro y es "
              "mas violenta. Respeta niveles redondos. Mejor ventana: solape "
              "Londres-NY (13:00-17:00 UTC). Cuidado con los barridos de liquidez "
              "antes de los datos de EEUU."),
    "energia": ("Manda la oferta/demanda: inventarios EIA los miercoles 14:30 UTC, "
                "OPEP+, geopolitica. Tendencias fuertes con reversiones bruscas. No "
                "operar los minutos previos a inventarios."),
    "indice": ("Direccion dominada por tipos y megacaps. La apertura de NY "
               "(13:30-15:00 UTC) concentra volumen y trampas; los gaps suelen "
               "rellenarse o extender con fuerza, asi que exige confirmacion. La "
               "sesion asiatica es rango pobre para tendencias."),
    "forex": ("Manda el diferencial de tipos y el calendario de bancos centrales. "
              "Rangos mas limpios y respeto por niveles previos mejor que en indices. "
              "Los cruces sin USD (EURGBP, EURJPY) se mueven menos y aguantan peor un "
              "stop ajustado. El corte de Nueva York (10:00 ET) puede imantar el "
              "precio hacia vencimientos de opciones. Evita la madrugada: el spread "
              "se come la ventaja."),
    "cripto": ("Opera 24/7, sin cierre ni sesiones; los fines de semana son ilíquidos "
               "y hacen mechas que no significan nada. Volatilidad muy superior: el "
               "mismo stop en ATR es mucho mas dinero. No le atribuyas relaciones "
               "macro estables, no las tiene."),
    "otro": ("Instrumento sin manias documentadas aqui. Opera solo lo que veas en el "
             "grafico y en el playbook; no le supongas comportamientos de otro "
             "mercado por parecido de nombre."),
}


def comportamiento(symbol: str) -> str:
    return COMPORTAMIENTO.get(familia(symbol), COMPORTAMIENTO["otro"])


# ------------------------------------------------------------- derivados

def _f(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return None if x != x else x       # NaN fuera


def derivados(series: dict) -> dict:
    """Lo que de verdad se mira, calculado de las series crudas.

    La pendiente 10y-2y y la inflación esperada no vienen dadas: hay que restarlas,
    y son más informativas que los niveles sueltos.
    """
    d10, d2 = _f(series.get("us10y")), _f(series.get("us2y"))
    real, be = _f(series.get("us10y_real")), _f(series.get("breakeven10y"))
    out = {
        "us10y": d10, "us2y": d2, "us10y_real": real,
        "vix": _f(series.get("vix")), "dxy": _f(series.get("dxy")),
        "breakeven10y": be,
        "curva_10y_2y": round(d10 - d2, 3) if (d10 is not None and d2 is not None) else None,
    }
    # curva invertida: el tramo corto por encima del largo. Historicamente ha
    # precedido recesiones, pero con retrasos de mas de un ano: es contexto, no senal
    out["curva_invertida"] = (out["curva_10y_2y"] is not None
                              and out["curva_10y_2y"] < 0)
    return out


def _nivel_vix(v):
    if v is None:
        return None
    if v < 15:
        return "calma"
    if v < 20:
        return "normal"
    if v < 30:
        return "tension"
    return "panico"


def lectura(symbol: str, macro: dict) -> dict:
    """Qué dice el macro PARA ESE instrumento, en una frase por factor.

    Solo se nombran los factores que de verdad afectan a esa familia. Soltarle al
    analista la curva de tipos cuando mira BTCUSD es ruido que compite con lo que sí
    importa, y el modelo no tiene forma de saber cuál ignorar.
    """
    fam = familia(symbol)
    d = derivados(macro or {})
    frases, factores = [], []

    if fam == "metal":
        r = d.get("us10y_real")
        if r is not None:
            factores.append("tipos reales")
            frases.append(
                f"Tipo real a 10 años en {r:.2f}%. Históricamente el oro se mueve al "
                "revés que el tipo real: si sube, el oro pierde atractivo frente a un "
                "bono que ya paga. Es una tendencia, no una ley — se han desacoplado "
                "meses enteros.")
        if d.get("dxy") is not None:
            factores.append("dólar")
            frases.append(f"Índice del dólar en {d['dxy']:.2f}: los metales cotizan en "
                          "dólares, un dólar fuerte les pesa en contra.")

    elif fam == "forex":
        s = str(symbol).upper()
        if "JPY" in s and d.get("us10y") is not None:
            factores.append("diferencial de bonos")
            frases.append(
                f"Bono EEUU 10 años en {d['us10y']:.2f}%. En los pares con yen el "
                "diferencial contra el bono japonés es de los factores más limpios: "
                "si se ensancha, el carry favorece al dólar.")
        if d.get("dxy") is not None:
            factores.append("dólar")
            frases.append(f"Índice del dólar en {d['dxy']:.2f}. Si va en contra de tu "
                          "tesis en un par contra el dólar, la operación nace peleada.")

    elif fam == "indice":
        v = d.get("vix")
        if v is not None:
            factores.append("volatilidad")
            frases.append(f"VIX en {v:.2f} ({_nivel_vix(v)}). Sube cuando caen los "
                          "índices: en zona de tensión las roturas fallan más y los "
                          "stops normales se quedan cortos.")
        if d.get("us10y") is not None:
            factores.append("tipos")
            frases.append(f"Bono a 10 años en {d['us10y']:.2f}%: subidas rápidas de "
                          "tipos suelen castigar más al Nasdaq que al Dow.")

    elif fam == "energia":
        if d.get("dxy") is not None:
            factores.append("dólar")
            frases.append(f"Índice del dólar en {d['dxy']:.2f}: el crudo cotiza en "
                          "dólares y suele moverse al revés que él.")

    # La curva solo se menciona donde ya hay algo que decir. Si no, acaba colándose
    # en familias a las que no les toca —BTC no cotiza contra el bono a 2 años— y ahí
    # deja de ser contexto para ser ruido con pinta de dato.
    if d.get("curva_invertida") and factores:
        factores.append("curva de tipos")
        frases.append("Curva de tipos invertida (2 años por encima de 10). Es contexto "
                      "de fondo, no una señal: los retrasos son de más de un año.")

    return {"symbol": str(symbol).upper(), "familia": fam,
            "factores": factores, "frases": frases, "datos": d,
            "aviso": ("son tendencias históricas, no leyes: entran como contexto a "
                      "ponderar, nunca como regla que decide sola")}


# ------------------------------------------------------------------- COT

def cot_resumen(filas: list[dict]) -> dict:
    """Posicionamiento del dinero grande, de las filas crudas de la CFTC.

    Lo que interesa no es el número: es si está EXTREMO. Una posición muy masificada
    no dice a dónde va el precio, dice que si se da la vuelta hay mucha gente
    corriendo por la misma puerta.
    """
    if not filas:
        return {"ok": False, "error": "sin datos de posicionamiento"}
    ord_ = sorted(filas, key=lambda r: str(r.get("report_date_as_yyyy_mm_dd") or ""))
    netos = []
    for r in ord_:
        # Un campo que falta NO es un cero: un cero se lee como "posicionamiento
        # plano", que es una afirmación. Si no viene el dato, esa semana no cuenta.
        largo = _f(r.get("noncomm_positions_long_all"))
        corto = _f(r.get("noncomm_positions_short_all"))
        if largo is None or corto is None:
            continue
        netos.append({"fecha": str(r.get("report_date_as_yyyy_mm_dd") or "")[:10],
                      "neto": largo - corto, "largo": largo, "corto": corto})
    if not netos:
        return {"ok": False, "error": "las filas no traían posiciones"}

    ultimo = netos[-1]
    valores = [x["neto"] for x in netos]
    pct = round(sum(1 for v in valores if v <= ultimo["neto"]) / len(valores) * 100, 1)
    # Hace falta historia para que "extremo" signifique algo: con veinte semanas,
    # extremo solo quiere decir "lo mas alto de los ultimos cinco meses". Y el
    # percentil va por RANGO y no por min-max: con min-max, un solo pico historico
    # aplasta la escala y todo lo demas parece moderado para siempre.
    suficiente = len(netos) >= MIN_SEMANAS_COT
    extremo = suficiente and (pct >= 90 or pct <= 10)
    if not suficiente:
        lectura = (f"solo hay {len(netos)} semanas: hace falta mas historia para decir "
                   "si esto es un extremo o lo normal en este mercado")
    elif extremo:
        lectura = ("posicionamiento MUY masificado: no dice a dónde va el precio, dice "
                   "que una vuelta tendría mucha gente saliendo a la vez")
    else:
        lectura = "posicionamiento sin extremos"
    return {"ok": True, "fecha": ultimo["fecha"], "neto": ultimo["neto"],
            "largo": ultimo["largo"], "corto": ultimo["corto"],
            "percentil": pct, "extremo": extremo, "semanas": len(netos),
            "historia_suficiente": suficiente, "lectura": lectura,
            "aviso": ("la CFTC publica los viernes con datos del martes: sirve para "
                      "saber si algo está masificado, nunca para cronometrar una entrada")}


# ------------------------------------------------------------- traerlos

FRED_URL = "https://api.stlouisfed.org/fred/series/observations"
COT_URL = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"


async def fetch_fred(api_key: str, timeout: float = 15) -> dict:
    """Último valor de cada serie de FRED. {} si no hay clave o no contesta.

    Se pide una a una a propósito: si una serie falla (se renombra, se retira), las
    demás siguen llegando. Un fallo total dejaría al analista sin contexto sin que
    nadie se enterase.
    """
    if not (api_key or "").strip():
        return {}
    import httpx

    out: dict = {}
    async with httpx.AsyncClient(timeout=timeout) as http:
        for nombre, sid in FRED_SERIES.items():
            try:
                r = await http.get(FRED_URL, params={
                    "series_id": sid, "api_key": api_key, "file_type": "json",
                    "sort_order": "desc", "limit": 1})
                r.raise_for_status()
                obs = (r.json().get("observations") or [])
                if obs and obs[0].get("value") not in (".", "", None):
                    out[nombre] = float(obs[0]["value"])
                    out[nombre + "_fecha"] = obs[0].get("date")
            except Exception as exc:  # noqa: BLE001 - una serie caída no tumba el resto
                log.info("FRED %s no disponible: %s", sid, str(exc)[:80])
    return out


async def fetch_cot(symbol: str, semanas: int = 156, timeout: float = 20) -> list[dict]:
    """Histórico de posicionamiento de ese símbolo. Lista vacía si no aplica.

    Tres años de semanas por defecto: el percentil necesita historia para significar
    algo. Con seis meses, "extremo" sería simplemente "lo más alto del semestre".
    """
    contrato = COT_CONTRATOS.get(str(symbol or "").upper())
    if not contrato:
        return []
    import httpx

    try:
        async with httpx.AsyncClient(timeout=timeout) as http:
            r = await http.get(COT_URL, params={
                "market_and_exchange_names": contrato,
                "$order": "report_date_as_yyyy_mm_dd DESC",
                "$limit": int(semanas)})
            r.raise_for_status()
            return r.json() or []
    except Exception as exc:  # noqa: BLE001
        log.info("COT de %s no disponible: %s", symbol, str(exc)[:100])
        return []


# ------------------------------------------------------- caché y contexto

# FRED publica una vez al día; la CFTC, una vez por semana. Pedirlo en cada ciclo
# de análisis (cada 15 min × 6 símbolos) sería tirar llamadas para recibir el mismo
# número. El TTL corto de fallo evita el otro extremo: quedarse sin macro toda la
# tarde porque una petición se cayó en el peor momento.
_TTL_FRED = 3 * 3600
_TTL_COT = 12 * 3600
_TTL_FALLO = 600
# Un dato viejo presentado como actual es peor que no tenerlo: el VIX de anteayer
# puesto al lado del precio de ahora se lee como el de ahora. Pasado este tope se
# tira y el analista se queda sin macro, que es lo honesto.
_MAX_EDAD = 24 * 3600

_cache: dict = {"fred": {}, "fred_ts": 0.0, "intento_ts": 0.0, "cot": {}}
_lock = asyncio.Lock()


def reset_cache() -> None:
    _cache.update({"fred": {}, "fred_ts": 0.0, "intento_ts": 0.0, "cot": {}})


def _ahora() -> float:
    return time.time()


async def series() -> tuple[dict, float | None]:
    """Series de FRED cacheadas. Devuelve (datos, edad_en_segundos)."""
    from .config import settings

    if not getattr(settings, "macro_enabled", True):
        return {}, None
    ahora = _ahora()
    async with _lock:
        edad = ahora - _cache["fred_ts"] if _cache["fred"] else None
        fresco = edad is not None and edad < _TTL_FRED
        # aunque estén viejos, no se reintenta en bucle si el último intento falló
        if fresco or (ahora - _cache["intento_ts"]) < _TTL_FALLO:
            if edad is not None and edad > _MAX_EDAD:
                return {}, edad
            return dict(_cache["fred"]), edad

        _cache["intento_ts"] = ahora
        datos = await fetch_fred(settings.fred_api_key)
        if datos:
            _cache["fred"], _cache["fred_ts"] = datos, ahora
            return dict(datos), 0.0
        # no vino nada: se conserva lo anterior mientras no pase de viejo
        edad = ahora - _cache["fred_ts"] if _cache["fred"] else None
        if edad is None or edad > _MAX_EDAD:
            return {}, edad
        return dict(_cache["fred"]), edad


async def cot(symbol: str) -> dict | None:
    """Posicionamiento cacheado de ese símbolo. None si no cotiza en Chicago."""
    from .config import settings

    if not getattr(settings, "macro_enabled", True):
        return None
    sym = str(symbol or "").upper()
    if sym not in COT_CONTRATOS:
        return None
    ahora = _ahora()
    guardado = _cache["cot"].get(sym)
    if guardado and (ahora - guardado["ts"]) < (
            _TTL_COT if guardado["res"].get("ok") else _TTL_FALLO):
        return guardado["res"]
    res = cot_resumen(await fetch_cot(sym))
    _cache["cot"][sym] = {"ts": ahora, "res": res}
    return res


async def contexto(symbol: str) -> dict:
    """Todo el macro que le toca a ese símbolo, listo para el analista."""
    datos, edad = await series()
    ctx = lectura(symbol, datos)
    ctx["edad_h"] = round(edad / 3600, 1) if edad is not None else None
    ctx["cot"] = await cot(symbol)
    ctx["opciones_fx"] = OPCIONES_FX_NOTA if ctx["familia"] == "forex" else None
    return ctx


def texto(ctx: dict | None) -> str:
    """El contexto en prosa. Vacío si no hay nada que decir.

    Se le da al modelo en texto y no en JSON porque son frases con matiz —«es una
    tendencia, no una ley»— y ese matiz es justo lo que se pierde al serializarlo
    en campos que el modelo puede leer como hechos duros.
    """
    if not ctx:
        return ""
    lineas = list(ctx.get("frases") or [])
    c = ctx.get("cot")
    if c and c.get("ok"):
        lineas.append(
            f"Posicionamiento CFTC ({c['fecha']}): neto {c['neto']:,.0f} contratos, "
            f"percentil {c['percentil']} de {c['semanas']} semanas — {c['lectura']}. "
            f"{c['aviso']}.")
    if not lineas:
        return ""
    if ctx.get("edad_h") and ctx["edad_h"] >= 1:
        lineas.append(f"(Estos datos macro son de hace {ctx['edad_h']:.0f} h.)")
    return ("Contexto macro — " + ctx.get("aviso", "") + ":\n"
            + "\n".join(f"- {x}" for x in lineas))
