"""Gestión de posiciones abierta: reglas de código, no opinión de un modelo.

El principio es el de tu maestro y es correcto: **el modelo razona, el código
opera**. Un modelo que decide una salida en tiempo real acierta casi siempre y se
equivoca de vez en cuando — y ese "de vez en cuando" no es un error de estilo, es
un stop puesto donde no debía en una posición viva.

Antes de esto, el agente nocturno devolvía un `new_stop_loss` y ese número —salido
de un modelo de lenguaje— se mandaba al bróker. Había un control de dirección (solo
podía apretar, nunca ampliar) que evitaba lo peor, pero no acotaba el VALOR: un
stop "apretado" a dos pips del precio pasa ese control y lo barre el primer tick.

Aquí las reglas son aritmética sobre el precio, la entrada y el ATR:

- El stop nunca se aleja. Nunca, por ningún motivo.
- A partir de +1R se lleva a break-even: dejar de poder perder en una operación que
  ya ganó es lo único gratis que hay en esto.
- A partir de ahí, arrastre a N×ATR del precio.
- Y un suelo: el stop nunca queda a menos de `min_atr` del precio. Un stop pegado
  no protege beneficio, solo garantiza que el ruido normal te saque.

El modelo sigue opinando y su opinión se guarda — sirve para revisar después si
habría acertado. Lo que no hace es tocar la cuenta.
"""
from __future__ import annotations

import logging

log = logging.getLogger("gestion")


def r_actual(side: str, entrada: float, stop_inicial: float, precio: float) -> float | None:
    """Cuántas R lleva ganadas la posición. None si no se puede saber."""
    if not entrada or not stop_inicial:
        return None
    riesgo = abs(entrada - stop_inicial)
    if riesgo <= 0:
        return None
    avance = (precio - entrada) if side == "buy" else (entrada - precio)
    return avance / riesgo


def stop_objetivo(side: str, entrada: float, stop_actual: float | None,
                  stop_inicial: float | None, precio: float, atr: float,
                  be_en_r: float = 1.0, trail_atr: float = 2.0,
                  min_atr: float = 0.8) -> tuple[float | None, str]:
    """El stop que TOCA ahora, calculado. Devuelve (stop, motivo).

    (None, motivo) significa dejarlo como está — que es la respuesta correcta la
    mayoría de las veces y no un fallo.
    """
    if atr <= 0 or precio <= 0 or not entrada:
        return None, "sin datos para calcular"
    base = stop_inicial if stop_inicial else stop_actual
    r = r_actual(side, entrada, base, precio) if base else None
    if r is None:
        return None, "no sé cuánto riesgo se arriesgó: no muevo nada"
    if r < be_en_r:
        return None, f"lleva {r:.2f}R: todavía no toca mover"

    if side == "buy":
        candidato = max(entrada, precio - atr * trail_atr)
        # Suelo de seguridad: pegar el stop al precio no protege, solo garantiza
        # que el ruido normal del instrumento te saque de una operación que iba bien.
        candidato = min(candidato, precio - atr * min_atr)
        if stop_actual is not None and candidato <= stop_actual:
            return None, "el stop ya está igual o mejor"
        if candidato >= precio:
            return None, "el cálculo daría un stop por encima del precio"
    else:
        candidato = min(entrada, precio + atr * trail_atr)
        candidato = max(candidato, precio + atr * min_atr)
        if stop_actual is not None and candidato >= stop_actual:
            return None, "el stop ya está igual o mejor"
        if candidato <= precio:
            return None, "el cálculo daría un stop por debajo del precio"

    motivo = ("a break-even" if abs(candidato - entrada) < atr * 0.05
              else f"arrastre a {trail_atr}xATR")
    return round(candidato, 6), f"{motivo} ({r:.2f}R ganadas)"


# ----------------------------------------- validar lo que propone un modelo

def niveles_validos(side: str, entrada: float, sl: float, tp: float, atr: float,
                    min_rr: float, min_atr: float = 1.0,
                    max_atr: float = 5.0) -> tuple[bool, str]:
    """¿Son operables los niveles que ha dado el modelo?

    No es desconfianza genérica: son los cuatro modos concretos en que unos niveles
    salidos de un texto salen mal, y ninguno da error al mandarlos.
    """
    if atr <= 0:
        return False, "sin ATR no se puede juzgar si el stop es razonable"
    if entrada <= 0 or sl <= 0:
        return False, "faltan niveles"
    riesgo = abs(entrada - sl)
    if riesgo <= 0:
        return False, "el stop está en el precio de entrada"

    # 1. Del lado equivocado. Entra, y la operación nace con el riesgo invertido.
    if side == "buy" and sl >= entrada:
        return False, "en una compra el stop tiene que ir por debajo de la entrada"
    if side == "sell" and sl <= entrada:
        return False, "en una venta el stop tiene que ir por encima de la entrada"

    # 2. Demasiado pegado: lo barre el ruido normal antes de que la idea se pruebe.
    if riesgo < atr * min_atr:
        return False, (f"el stop está a {riesgo / atr:.2f}xATR: el ruido normal de "
                       f"este instrumento lo barre antes de que la idea falle")
    # 3. Demasiado lejos: el tamaño de posición sale ridículo o el riesgo real no es
    #    el que se cree.
    if riesgo > atr * max_atr:
        return False, f"el stop está a {riesgo / atr:.2f}xATR: demasiado lejos"

    # 4. La relación no es la que parece. Es el error que más se cuela porque los
    #    tres números por separado parecen razonables.
    if tp and tp > 0:
        if side == "buy" and tp <= entrada:
            return False, "en una compra el objetivo tiene que ir por encima"
        if side == "sell" and tp >= entrada:
            return False, "en una venta el objetivo tiene que ir por debajo"
        rr = abs(tp - entrada) / riesgo
        if rr < min_rr:
            return False, (f"da {rr:.2f} de beneficio/riesgo y el mínimo es {min_rr}. "
                           "Acercar el stop para que salgan las cuentas es la forma "
                           "más cara de arreglarlo")
    return True, "niveles operables"
