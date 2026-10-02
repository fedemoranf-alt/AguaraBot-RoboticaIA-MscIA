"""
TPF Robótica IA — Ley de control (PLAN.md §7)
==============================================================================
Convierte una detección en un comando del protocolo. Nada más.

Todo acá es una función pura: entra `error_x` / `area_ratio`, sale
`(v_lin, v_ang)`. No toca la cámara, no toca el puerto serie y no recuerda
nada entre llamadas. Eso permite verificarla entera en la PC, sin robot — que
es como se verificó `vision.py` el 2026-08-28.

**Cambio de unidades.** PLAN.md §7 escribe la ley en normalizado (0 a 1) y el
protocolo de §8 viaja en enteros de -100 a 100. La conversión (×100) vive acá
y en ningún otro lado: `KP_ANG` y `KP_LIN` se leen como ganancias normalizadas,
mientras que `V_LIN_MAX` y `V_ANG_MAX` ya están en unidades del protocolo.

**Dos cosas que la calibración del 2026-08-27 impone y que no son negociables:**

- No hay arranque suave. Cualquier `u > 0` da como mínimo 0,091 m/s
  (HARDWARE.md §0.5). Un `v_lin` de 1 no hace que el robot vaya despacio: lo
  hace ir a 0,091 m/s. Por eso hay zona muerta y por eso frenar es mandar
  exactamente 0.
- `v_ang > 0` gira a la derecha, igual que `error_x > 0` significa objetivo a
  la derecha. El signo sale de la ley y entra al protocolo sin invertirse.
"""

from __future__ import annotations

import config


# ==============================================================================
# 1. Acotados
# ==============================================================================
def acotar(v, minimo, maximo):
    return max(minimo, min(maximo, v))


def a_protocolo(v_normalizado, tope):
    """Normalizado (-1..1) → entero del protocolo (-100..100), acotado a `tope`."""
    return int(round(acotar(v_normalizado * 100.0, -tope, tope)))


# ==============================================================================
# 2. Giro — control proporcional sobre el error lateral
# ==============================================================================
def girar_hacia(error_x, kp=None, zona_muerta=None, tope=None):
    """`v_ang` para centrar el objetivo. Positivo = derecha.

    La zona muerta no es un ajuste fino, es una consecuencia del escalón: sin
    ella, con el objetivo casi centrado la ley pide un giro mínimo, el robot lo
    ejecuta a la velocidad mínima —que no es mínima— se pasa, y oscila.
    """
    kp = config.KP_ANG if kp is None else kp
    zona_muerta = config.ZONA_MUERTA_ERROR_X if zona_muerta is None else zona_muerta
    tope = config.V_ANG_MAX if tope is None else tope

    if abs(error_x) < zona_muerta:
        return 0
    return a_protocolo(kp * error_x, tope)


# ==============================================================================
# 3. Avance — control proporcional sobre el área
# ==============================================================================
def avanzar_hacia(area_ratio, kp=None, area_objetivo=None, tope=None):
    """`v_lin` para acercarse hasta el área objetivo. Nunca negativo.

    El área crece al acercarse, así que el error `(objetivo − actual)` se achica
    y el robot frena solo. Pasado el objetivo el error se vuelve negativo y se
    recorta a 0: la ley no retrocede. Alejarse es trabajo de HUIR, no de
    APROXIMAR.
    """
    kp = config.KP_LIN if kp is None else kp
    area_objetivo = config.AREA_OBJETIVO if area_objetivo is None else area_objetivo
    tope = config.V_LIN_MAX if tope is None else tope

    v = a_protocolo(kp * (area_objetivo - area_ratio), tope)
    return max(0, v)


# ==============================================================================
# 4. La ley completa
# ==============================================================================
def perseguir(deteccion, **kw):
    """(v_lin, v_ang) para ir hacia una `Deteccion` de vision.py.

    El giro se recorta a `|v_ang| <= 0,7 · v_lin`: avanzando, la rueda de adentro
    nunca baja del 30 % de `v_lin`, o sea que ni se invierte ni se detiene.
    El motivo es que no hay arranque suave: una rueda que cruza por cero no
    gira "un poquito menos", pasa de 0,09 m/s a nada (o a 0,09 m/s para atrás),
    y el robot pivota a 40-70°/s justo cuando está llegando. Medido en el piso
    el 2026-10-01, dos veces:

      - sin recorte, el último ciclo pidió (12, -19): rueda izquierda en
        reversa, y el oso saltó de ex = -0,33 a +0,21 con el robot frenando;
      - con recorte a `|v_ang| <= v_lin` la rueda de adentro quedaba en 0 y el
        robot pivotaba sobre ella: terminó girado ~15°, con el oso cortado por
        el borde derecho de la imagen (ex = +0,58).

    Así la autoridad de giro acompaña a la velocidad, como en un auto: lejos y
    rápido gira mucho, cerca y lento corrige suave. Primero se probó con la
    mitad de `v_lin`, y quedó corto justo al final, que es donde el robot se
    tuerce solo al frenar (corrida_20261001_170756: perdió el oso por el borde
    con el giro recortado a 17 cuando la ley pedía 23).
    """
    v_lin = avanzar_hacia(deteccion.area_ratio, **_solo(kw, "kp_lin", "area_objetivo"))
    v_ang = girar_hacia(deteccion.error_x, **_solo(kw, "kp_ang", "zona_muerta"))
    if v_lin > 0:
        tope = int(0.7 * v_lin)
        v_ang = acotar(v_ang, -tope, tope)
    return v_lin, v_ang


def _solo(kw, *nombres):
    """Reparte los kwargs entre las dos mitades de la ley, sin sus prefijos."""
    corte = {"kp_lin": "kp", "kp_ang": "kp", "area_objetivo": "area_objetivo",
             "zona_muerta": "zona_muerta"}
    return {corte[n]: kw[n] for n in nombres if n in kw}


# ==============================================================================
# 5. Diagnóstico del rango efectivo
# ==============================================================================
# Con la ley proporcional, `v_lin` es máximo cuando el objeto está infinitamente
# lejos (area_ratio → 0), y ahí vale KP_LIN · AREA_OBJETIVO · 100. Ese es el
# techo REAL de la aproximación; V_LIN_MAX sólo actúa si es menor.
#
# 🔴 Con los valores de hoy (KP_LIN 2,0 · AREA_OBJETIVO 0,15) el techo efectivo
# es 30, no 72: el clamp de V_LIN_MAX nunca se activa y el robot se aproxima a
# ~0,18 m/s en vez de los 0,30 m/s para los que se dimensionó el lazo. No es un
# error —30 es una velocidad segura y KP_LIN está marcado ⬜ sin calibrar— pero
# conviene saber cuál de los dos números manda antes de tocar el otro. Para que
# V_LIN_MAX sea el que limita hace falta KP_LIN ≥ V_LIN_MAX / (AREA_OBJETIVO·100).
#
# Es el mismo patrón que las cuatro estimaciones caídas del bloque de tracción:
# un parámetro que parece estar gobernando algo y en realidad no llega a actuar.
def techo_efectivo_lineal(kp_lin=None, area_objetivo=None, tope=None):
    """El `v_lin` máximo que la ley puede pedir, y cuál de los dos límites manda."""
    kp_lin = config.KP_LIN if kp_lin is None else kp_lin
    area_objetivo = config.AREA_OBJETIVO if area_objetivo is None else area_objetivo
    tope = config.V_LIN_MAX if tope is None else tope

    por_ganancia = kp_lin * area_objetivo * 100.0
    if por_ganancia <= tope:
        return por_ganancia, "KP_LIN"
    return float(tope), "V_LIN_MAX"


def kp_lin_para_saturar(v_lin_max=None, area_objetivo=None):
    """El KP_LIN mínimo para que V_LIN_MAX sea el límite que actúa."""
    v_lin_max = config.V_LIN_MAX if v_lin_max is None else v_lin_max
    area_objetivo = config.AREA_OBJETIVO if area_objetivo is None else area_objetivo
    return v_lin_max / (area_objetivo * 100.0)


def describir():
    """Resumen legible de la ley vigente, para el log de arranque."""
    techo, manda = techo_efectivo_lineal()
    return (
        "Ley de control: KP_ANG=%.2f KP_LIN=%.2f area_obj=%.3f zona_muerta=%.3f\n"
        "  v_ang tope %d  |  v_lin techo efectivo %.0f (lo fija %s; V_LIN_MAX=%d)\n"
        "  v_lin=%.0f  ->  %.3f m/s"
        % (config.KP_ANG, config.KP_LIN, config.AREA_OBJETIVO,
           config.ZONA_MUERTA_ERROR_X, config.V_ANG_MAX, techo, manda,
           config.V_LIN_MAX, techo, config.velocidad_real(techo / 100.0))
    )


if __name__ == "__main__":
    print(describir())
    print()
    print("  error_x   v_ang        area_ratio   v_lin")
    for e in (-1.0, -0.5, -0.1, -0.05, 0.0, 0.05, 0.1, 0.5, 1.0):
        print("  %+6.2f   %+4d" % (e, girar_hacia(e)))
    print()
    for a in (0.0, 0.02, 0.05, 0.10, 0.15, 0.20, 0.40):
        print("               %25.2f   %4d   (%.3f m/s)"
              % (a, avanzar_hacia(a), config.velocidad_real(avanzar_hacia(a) / 100.0)))
