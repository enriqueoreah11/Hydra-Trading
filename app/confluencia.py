"""El patrón del Confluence Bot, corriendo dentro de Hydra.

Tu bot vive en cTrader y solo puede mirar el gráfico al que está pegado: para que
vigilara todos los pares harían falta tantas instancias como gráficos, y aun así
Hydra solo se enteraría de lo que el bot le mandase. Esto es lo contrario: leer
QUÉ patrón busca y buscarlo aquí, sobre todos los instrumentos a la vez.

El patrón es el de las capturas que ya manda tu bot a /ingest/trade-context: una
ZONA de precio donde coinciden varias razones independientes, puntuada por cuántas
coinciden. Las familias son las suyas — HTFKL, KeyLevel, Fib, EMA, SMA, Session,
Round — y se llaman igual a propósito, para poder comparar señal contra señal.

**Lo que hace que esto funcione o sea un adorno: se cuentan FAMILIAS, no señales.**
Tres EMAs pegadas al mismo precio son UNA razón para que ese nivel importe, no
tres. Contando señales, cualquier sitio donde se juntan medias parece una zona de
oro, y son justo los sitios donde no hay nada. Por eso tu bot lleva `n_families`
aparte de `n_confluences`, y por eso aquí puntúa la primera.

La anchura de la zona va en ATR y no en pips. En pips, la misma configuración que
es sensata en el EURUSD no toca nunca una zona en el Nasdaq y salta con todo en el
oro — y no hay forma de notarlo salvo mirando por qué no opera un símbolo.

Lo que esta réplica NO tiene, y no se disimula:
- Líneas de tendencia y cualquier objeto que dibujes a mano. Si tu bot los lee,
  parte de sus señales son irreproducibles aquí por definición.
- Los ajustes exactos de tu .algo. Los parámetros de abajo son los de esta
  implementación; se miden fuera de muestra como cualquier otra estrategia.
"""
from __future__ import annotations

import logging

from . import indicators as ind
from .broker import Candle

log = logging.getLogger("confluencia")

# Los mismos nombres que usa el bot al clasificar sus etiquetas. Coincidir en el
# vocabulario es lo que permite comparar una captura suya con una señal de aquí.
FAMILIAS = ("HTFKL", "IKL", "KeyLevel", "TrendLine", "Fib", "EMA", "SMA",
            "Session", "Round")

# Ninguna familia se queda fuera: las líneas de tendencia, los key levels y los
# Fibonacci los CALCULA el bot, no los lees tú del gráfico, así que son
# reproducibles. Lo que no se puede copiar son sus umbrales exactos: el .algo solo
# expone tres parámetros (break-even y trailing) y el resto va compilado dentro.
# Por eso los de aquí no se copian, se miden fuera de muestra como los de
# cualquier otra estrategia.
NO_REPLICADAS: tuple[str, ...] = ()
NOTA_AJUSTES = ("las familias son las mismas, pero los umbrales de tu bot van "
                "compilados en el .algo (solo expone 3 parámetros): los de aquí "
                "salen de medir, no de copiar")


def _redondos(precio: float, atr_v: float) -> list[float]:
    """Niveles redondos a la escala del instrumento.

    El paso sale del precio, no de una tabla: 1.0850 en el EURUSD y 3400 en el oro
    piden pasos distintos, y una tabla fija se queda vieja en cuanto añades un
    símbolo. Solo se devuelven los que están razonablemente cerca.
    """
    if precio <= 0 or atr_v <= 0:
        return []
    paso = 10.0 ** (len(str(int(abs(precio)))) - 2) if abs(precio) >= 10 else 0.01
    paso = max(paso, 0.0001)
    base = round(precio / paso) * paso
    return [round(base + k * paso, 6) for k in (-1, 0, 1)]


def _swings(candles: list[Candle], hasta: int, lookback: int, n: int) -> list[float]:
    """Máximos y mínimos que el precio ya respetó: la estructura."""
    out: list[float] = []
    lo = max(lookback, hasta - 400)
    for i in range(hasta - lookback, lo, -1):
        if i - lookback < 0 or i + lookback > hasta:
            continue
        ventana = candles[i - lookback:i + lookback + 1]
        c = candles[i]
        if c.high >= max(x.high for x in ventana):
            out.append(c.high)
        elif c.low <= min(x.low for x in ventana):
            out.append(c.low)
        if len(out) >= n:
            break
    return out


def _agrupar(candles: list[Candle], hasta: int, mult: int) -> list[Candle]:
    """Las mismas velas en un marco mayor. Se agrupa desde el final para que la
    última vela agregada termine donde estamos: agrupando desde el principio, el
    resto sobrante desplazaría todas las cajas y los niveles saldrían movidos."""
    out: list[Candle] = []
    fin = hasta + 1
    ini = fin - ((fin // mult) * mult)
    for k in range(ini, fin, mult):
        trozo = candles[k:k + mult]
        if len(trozo) < mult:
            continue
        out.append(Candle(ts=trozo[0].ts, open=trozo[0].open,
                          high=max(c.high for c in trozo),
                          low=min(c.low for c in trozo),
                          close=trozo[-1].close,
                          volume=sum(c.volume for c in trozo)))
    return out


def _pivotes(candles: list[Candle], hasta: int, lookback: int,
             n: int) -> tuple[list[tuple[int, float]], list[tuple[int, float]]]:
    """Máximos y mínimos pivote con su posición. Los índices hacen falta para las
    líneas: una recta necesita DOS puntos y cuándo ocurrió cada uno."""
    altos: list[tuple[int, float]] = []
    bajos: list[tuple[int, float]] = []
    lo = max(lookback, hasta - 400)
    for i in range(hasta - lookback, lo, -1):
        if i - lookback < 0 or i + lookback > hasta:
            continue
        ventana = candles[i - lookback:i + lookback + 1]
        c = candles[i]
        if c.high >= max(x.high for x in ventana) and len(altos) < n:
            altos.append((i, c.high))
        elif c.low <= min(x.low for x in ventana) and len(bajos) < n:
            bajos.append((i, c.low))
        if len(altos) >= n and len(bajos) >= n:
            break
    return altos, bajos


def _lineas(candles: list[Candle], hasta: int, lookback: int, tol: float,
            toques_min: int = 3) -> list[float]:
    """Líneas de tendencia trazadas entre pivotes, proyectadas hasta la vela actual.

    Es lo que hace el bot al dibujarlas: pivotes que definen una recta y se
    extiende. Dos condiciones, y la segunda es la que decide si esto sirve:

    1. El precio la RESPETÓ entre los extremos. Una recta que atravesó cinco veces
       no es una línea de tendencia.
    2. **Al menos tres toques.** Dos puntos definen una recta, y por dos puntos
       cualesquiera pasa exactamente una: sobre ruido puro eso daba ocho "líneas"
       de doce posibles. Con ocho, la familia TrendLine está presente en cualquier
       zona que mires y deja de discriminar — que es peor que no tenerla, porque
       infla la cuenta de familias sin aportar una razón.

    Se miran pocos pivotes a propósito: esto corre en cada vela del backtest, y
    cuantas más rectas se admiten más fácil es que una pase por donde sea.
    """
    altos, bajos = _pivotes(candles, hasta, lookback, 5)
    out: list[float] = []
    for puntos, es_alto in ((altos, True), (bajos, False)):
        for a in range(len(puntos)):
            for b in range(a + 1, len(puntos)):
                i1, v1 = puntos[b]                      # el más antiguo
                i2, v2 = puntos[a]
                if i2 - i1 < lookback * 2:
                    continue                            # demasiado juntos: no es una línea
                m = (v2 - v1) / (i2 - i1)
                roto = False
                for k in range(i1 + 1, i2):
                    y = v1 + m * (k - i1)
                    c = candles[k]
                    if (es_alto and c.high > y + tol) or (not es_alto and c.low < y - tol):
                        roto = True
                        break
                if roto:
                    continue
                toques = sum(1 for j, v in puntos
                             if abs(v - (v1 + m * (j - i1))) <= tol)
                if toques < toques_min:
                    continue
                proyectado = v1 + m * (hasta - i1)
                if proyectado > 0:
                    out.append(round(proyectado, 6))
    return out


def _fibs(candles: list[Candle], hasta: int, ventana: int) -> list[float]:
    """Retrocesos del último tramo relevante."""
    tramo = candles[max(0, hasta - ventana):hasta + 1]
    if len(tramo) < 10:
        return []
    hi = max(c.high for c in tramo)
    lo = min(c.low for c in tramo)
    if hi <= lo:
        return []
    return [round(hi - (hi - lo) * r, 6) for r in (0.382, 0.5, 0.618)]


def _sesion(candles: list[Candle], hasta: int, velas_dia: int) -> list[float]:
    """Máximo, mínimo y cierre del periodo anterior (el "día" de este timeframe)."""
    ini = hasta - velas_dia * 2
    if ini < 0:
        return []
    previo = candles[ini:hasta - velas_dia]
    if not previo:
        return []
    return [max(c.high for c in previo), min(c.low for c in previo), previo[-1].close]


def niveles(candles: list[Candle], i: int, p: dict) -> list[tuple[str, float]]:
    """Todos los niveles candidatos con la familia de la que salen."""
    out: list[tuple[str, float]] = []
    closes = [c.close for c in candles[:i + 1]]
    precio = candles[i].close
    a = ind.atr(candles[:i + 1], 14)
    atr_v = a[-1] if a else 0.0
    if not atr_v:
        return out

    lb = int(p.get("swing_lookback", 5))
    for v in _swings(candles, i, lb, 12):
        out.append(("KeyLevel", v))
    # Las líneas de tendencia las DIBUJA el bot, no se leen del gráfico: son
    # algorítmicas y por tanto reproducibles. La tolerancia va en ATR para que la
    # misma exigencia valga en un par de forex y en un índice.
    for v in _lineas(candles, i, lb, atr_v * float(p.get("tl_tol_atr", 0.25))):
        out.append(("TrendLine", v))
    # Los niveles de marcos superiores se sacan agregando las MISMAS velas: sin
    # pedir otra serie, y sin poder desincronizarse de la que se está mirando.
    # IKL es el marco intermedio y HTFKL el alto, igual que los distingue el bot.
    for fam, mult in (("IKL", int(p.get("ikl_mult", 2))),
                      ("HTFKL", int(p.get("htf_mult", 4)))):
        if mult <= 1:
            continue
        agrupadas = _agrupar(candles, i, mult)
        if len(agrupadas) > 30:
            for v in _swings(agrupadas, len(agrupadas) - 1, lb, 8):
                out.append((fam, v))

    for per in (int(p.get("ema_fast", 20)), int(p.get("ema_slow", 50))):
        e = ind.ema(closes, per)
        if e:
            out.append(("EMA", e[-1]))
    s = ind.sma(closes, int(p.get("sma_trend", 200)))
    if s:
        out.append(("SMA", s[-1]))
    for v in _fibs(candles, i, int(p.get("fib_window", 120))):
        out.append(("Fib", v))
    for v in _sesion(candles, i, int(p.get("velas_dia", 96))):
        out.append(("Session", v))
    for v in _redondos(precio, atr_v):
        out.append(("Round", v))
    return out


def zonas(candles: list[Candle], i: int, p: dict) -> list[dict]:
    """Agrupa los niveles en zonas y las puntúa por familias distintas.

    Se ordenan por precio y se van juntando los que caen dentro de la anchura. La
    puntuación es el número de familias DISTINTAS: si fuera el número de niveles,
    un sitio con tres medias juntas puntuaría como una confluencia real y no lo es.
    """
    a = ind.atr(candles[:i + 1], 14)
    atr_v = a[-1] if a else 0.0
    if not atr_v:
        return []
    ancho = atr_v * float(p.get("zona_atr", 0.35))
    if ancho <= 0:
        return []
    todos = sorted(niveles(candles, i, p), key=lambda x: x[1])
    if not todos:
        return []
    grupos: list[list[tuple[str, float]]] = [[todos[0]]]
    for fam, v in todos[1:]:
        if v - grupos[-1][-1][1] <= ancho:
            grupos[-1].append((fam, v))
        else:
            grupos.append([(fam, v)])
    out = []
    for g in grupos:
        fams = sorted({f for f, _ in g})
        precios = [v for _, v in g]
        out.append({"centro": round(sum(precios) / len(precios), 6),
                    "top": round(max(precios) + ancho / 2, 6),
                    "bottom": round(min(precios) - ancho / 2, 6),
                    "familias": fams, "n_familias": len(fams),
                    "n_niveles": len(g), "ancho_atr": round(ancho, 6)})
    out.sort(key=lambda z: (-z["n_familias"], z["centro"]))
    return out


def confluencia(candles: list[Candle], p: dict, i: int):
    """Señal cuando el precio llega a una zona con suficientes familias de acuerdo.

    Se opera el REBOTE en la zona, que es lo que busca el bot: una zona por debajo
    con varias razones es soporte y se compra, una por encima es resistencia y se
    vende. Se exige que la vela actual confirme —que haya tocado y cerrado del lado
    correcto—, porque entrar solo por cercanía es entrar antes de que el nivel haya
    hecho nada.
    """
    from .strategies import Signal, _stops

    minimo = int(p.get("min_familias", 3))
    if i < 250:
        return None
    a = ind.atr(candles[:i + 1], 14)
    atr_v = a[-1] if a else 0.0
    if not atr_v:
        return None
    c = candles[i]
    cerca = atr_v * float(p.get("dist_atr", 0.6))

    for z in zonas(candles, i, p):
        if z["n_familias"] < minimo:
            continue
        # Soporte: la zona queda por debajo, el precio la ha tocado y ha cerrado
        # por encima. Si cierra dentro o por debajo, el nivel está cediendo — eso
        # no es un rebote, es justo lo contrario.
        if z["top"] < c.close <= z["top"] + cerca and c.low <= z["top"]:
            if c.close > c.open:
                return Signal("buy", c.close, *_stops(c.close, atr_v, p, "buy"))
        if z["bottom"] > c.close >= z["bottom"] - cerca and c.high >= z["bottom"]:
            if c.close < c.open:
                return Signal("sell", c.close, *_stops(c.close, atr_v, p, "sell"))
    return None


def radar(candles: list[Candle], p: dict, top: int = 3) -> dict:
    """Qué zonas tiene ahora mismo este instrumento, haya señal o no.

    Sirve para mirar: una zona de cuatro familias a media sesión de distancia es
    información aunque hoy no se opere.
    """
    if len(candles) < 250:
        return {"ok": False, "error": f"hacen falta 250 velas y hay {len(candles)}",
                "zonas": []}
    i = len(candles) - 1
    a = ind.atr(candles[:i + 1], 14)
    atr_v = a[-1] if a else 0.0
    precio = candles[i].close
    zs = [z for z in zonas(candles, i, p) if z["n_familias"] >= 2][:top]
    for z in zs:
        z["dist_atr"] = round(abs(precio - z["centro"]) / atr_v, 2) if atr_v else None
        z["lado"] = "soporte" if z["centro"] < precio else "resistencia"
    señal = confluencia(candles, p, i)
    return {"ok": True, "precio": precio, "atr": round(atr_v, 6), "zonas": zs,
            "senal": señal.as_dict() if señal else None,
            "familias": list(FAMILIAS), "no_replicadas": list(NO_REPLICADAS),
            "nota_ajustes": NOTA_AJUSTES}
