"""
TPF Robótica IA — Análisis de corridas
==============================================================================
Lee el CSV que deja `main.py` (ver registro.py) y saca los números de la demo
en piso: los de PLAN.md §10 y los de los parámetros ⬜ del Día 5.

    python analizar_corrida.py ../logs/corrida_20260930_153012.csv
    python analizar_corrida.py ../logs/corrida_*.csv       # varias: una tabla

Sólo biblioteca estándar: corre igual en el Pi que en la PC.

Lo que el CSV NO puede decir, y hay que anotar a mano en cada corrida: la
distancia REAL a la que frenó (cinta métrica), si chocó, y cuánto giró de verdad
en BUSCAR y en la fase 2 de HUIR. El registro sabe qué pidió el Pi y qué vio la
cámara; no sabe dónde quedó el robot.
"""

from __future__ import annotations

import csv
import json
import statistics
import sys
from pathlib import Path

import config


def _f(v):
    return float(v) if v not in ("", None) else None


def leer(ruta):
    ruta = Path(ruta)
    with open(ruta, newline="", encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    for r in filas:
        r["t"] = float(r["t_s"])
        r["dt"] = float(r["dt_ms"])
        for k in ("v_lin", "v_ang"):
            r[k] = int(r[k])
        for k in ("obj_conf", "obj_ex", "obj_ar", "amz_conf", "amz_ex", "amz_ar"):
            r[k] = _f(r[k])
        r["franjas"] = _f(r.get("franjas"))    # los CSV anteriores al 2026-10-01 no la traen
    meta = {}
    ruta_json = ruta.with_suffix(".json")
    if ruta_json.exists():
        meta = json.loads(ruta_json.read_text(encoding="utf-8"))
    return filas, meta


def _pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(p / 100 * (len(xs) - 1))))]


# ==============================================================================
# Las métricas
# ==============================================================================
def analizar(filas, meta):
    """Devuelve un dict con todo lo medible. Los None son "no pasó"."""
    par = meta.get("parametros", {})
    zona = par.get("ZONA_MUERTA_ERROR_X", config.ZONA_MUERTA_ERROR_X)
    m = {"filas": len(filas)}
    if not filas:
        return m

    # -- lazo --------------------------------------------------------------
    dts = [r["dt"] for r in filas[1:]]        # la 1ª incluye el arranque
    m["duracion_s"] = filas[-1]["t"]
    m["fps"] = len(filas) / filas[-1]["t"] if filas[-1]["t"] > 0 else None
    if dts:
        m["dt_p50_ms"] = _pct(dts, 50)
        m["dt_p95_ms"] = _pct(dts, 95)
        m["dt_max_ms"] = max(dts)

    # -- salud de la imagen ---------------------------------------------------
    # Frames que llegaron con franjas grises (paquetes USB perdidos, ver
    # vision.franjas). Si son muchos, lo que sigue mide a una cámara ciega.
    fr = [r["franjas"] for r in filas if r["franjas"] is not None]
    if fr:
        m["img_medidos"] = len(fr)
        m["img_con_franjas"] = sum(1 for x in fr if x > 0.01)
        m["img_muy_danados"] = sum(1 for x in fr if x > 0.10)

    # -- estados y transiciones ---------------------------------------------
    tiempo, trans = {}, []
    for a, b in zip(filas, filas[1:]):
        tiempo[a["estado"]] = tiempo.get(a["estado"], 0.0) + (b["t"] - a["t"])
        if b["estado"] != a["estado"]:
            trans.append((b["t"], a["estado"], b["estado"], b["motivo"]))
    m["tiempo_por_estado"] = tiempo
    m["transiciones"] = trans
    m["t_encontrado"] = next((t for t, _, h, _ in trans if h == "ENCONTRADO"), None)
    m["perdidas"] = sum(1 for _, d, h, _ in trans if d == "APROXIMAR" and h == "BUSCAR")

    # -- BUSCAR: cuántos frames seguidos se ve el oso al barrer -------------
    # Es la medición que decide BUSCAR_FRENAR_AL_VER y V_ANG_BUSCAR: si las
    # rachas son más cortas que N_CONFIRMAR, girando no se confirma nunca.
    #
    # El frame de cada fila se tomó mientras se ejecutaba el comando de la fila
    # ANTERIOR: por eso "girando" se mira ahí. Mirarlo en la fila misma pierde
    # el frame que confirma, que ya queda anotado como APROXIMAR.
    rachas, n = [], 0
    for prev, r in zip(filas, filas[1:]):
        barriendo = prev["estado"] == "BUSCAR" and prev["v_ang"] != 0
        if barriendo and r["obj_conf"] is not None:
            n += 1
        else:
            if n:
                rachas.append(n)
            n = 0
    if n:
        rachas.append(n)
    m["rachas_barriendo"] = rachas

    # Primer avistamiento → confirmación, por cada entrada a APROXIMAR.
    confirmaciones = []
    for i, r in enumerate(filas):
        if r["estado"] == "APROXIMAR" and i and filas[i - 1]["estado"] == "BUSCAR":
            j = i - 1
            while j >= 0 and filas[j]["estado"] == "BUSCAR" and filas[j]["obj_conf"] is not None:
                j -= 1
            primero = filas[j + 1]
            # Dónde está el oso ~0,5 s después: si ya no está, se pasó de largo.
            despues = [f for f in filas[i:] if f["t"] <= r["t"] + 0.5]
            ex_desp = [f["obj_ex"] for f in despues if f["obj_ex"] is not None]
            confirmaciones.append({
                "t": r["t"],
                "demora_s": r["t"] - primero["t"],
                "ex_primero": primero["obj_ex"],
                "ex_0_5s": ex_desp[-1] if ex_desp else None,
                "lo_perdio": not ex_desp,
            })
    m["confirmaciones"] = confirmaciones

    # -- APROXIMAR: ¿oscila al centrarse? -----------------------------------
    # Un cruce es pasar de un lado al otro FUERA de la zona muerta: dentro de
    # ella la ley no gira, así que cruzarla ahí no es oscilar.
    ex = [r["obj_ex"] for r in filas if r["estado"] == "APROXIMAR" and r["obj_ex"] is not None]
    if ex:
        lados = [1 if e > zona else -1 for e in ex if abs(e) > zona]
        m["aprox_frames"] = len(ex)
        m["aprox_ex_rms"] = (sum(e * e for e in ex) / len(ex)) ** 0.5
        m["aprox_ex_max"] = max(abs(e) for e in ex)
        m["aprox_cruces"] = sum(1 for a, b in zip(lados, lados[1:]) if a != b)
        m["aprox_fuera_zona"] = len(lados) / len(ex)
        v_ang = [r["v_ang"] for r in filas if r["estado"] == "APROXIMAR" and r["v_ang"]]
        m["aprox_cambios_giro"] = sum(1 for a, b in zip(v_ang, v_ang[1:]) if (a > 0) != (b > 0))

    # -- ENCONTRADO: con qué área frenó -------------------------------------
    if m["t_encontrado"] is not None:
        antes = [r for r in filas if r["t"] <= m["t_encontrado"] and r["obj_ar"] is not None]
        if antes:
            m["ar_al_frenar"] = antes[-1]["obj_ar"]
            m["ex_al_frenar"] = antes[-1]["obj_ex"]
        # Lo que sigue viendo con el robot ya quieto: si el ar sube, se pasó.
        quieto = [r["obj_ar"] for r in filas
                  if r["t"] >= m["t_encontrado"] + 1.0 and r["obj_ar"] is not None]
        if quieto:
            m["ar_quieto"] = statistics.median(quieto)

    # -- HUIR: latencia de reacción y falsos positivos ----------------------
    huidas = []
    for i, r in enumerate(filas):
        if r["estado"] == "HUIR" and i and filas[i - 1]["estado"] != "HUIR":
            j = i - 1
            while j >= 0 and filas[j]["amz_conf"] is not None:
                j -= 1
            primero = filas[j + 1] if j + 1 < i else r
            huidas.append({"t": r["t"], "latencia_s": r["t"] - primero["t"],
                           "frames_vista": i - (j + 1)})
    m["huidas"] = huidas
    m["frames_con_mochila"] = sum(1 for r in filas if r["amz_conf"] is not None)
    return m


# ==============================================================================
# El informe
# ==============================================================================
def informar(ruta, m, meta):
    print("=" * 66)
    print(ruta)
    if meta.get("nota"):
        print("Nota: %s" % meta["nota"])
    par = meta.get("parametros", {})
    if par:
        claves = ("KP_ANG", "ZONA_MUERTA_ERROR_X", "V_ANG_BUSCAR", "BUSCAR_GIRO_S",
                  "HUIR_GIRO_S", "AREA_OBJETIVO", "BUSCAR_FRENAR_AL_VER")
        print("Parámetros: " + "  ".join("%s=%s" % (k, par[k]) for k in claves if k in par))
    print("=" * 66)
    if not m["filas"]:
        print("CSV vacío.")
        return

    print("Lazo: %d ciclos en %.1f s → %.2f FPS · dt p50 %.0f ms, p95 %.0f, máx %.0f"
          % (m["filas"], m["duracion_s"], m["fps"] or 0, m.get("dt_p50_ms", 0),
             m.get("dt_p95_ms", 0), m.get("dt_max_ms", 0)))
    if "img_medidos" in m:
        print("Imagen: %d de %d frames con franjas, %d muy dañados (>10 %% de las filas)%s"
              % (m["img_con_franjas"], m["img_medidos"], m["img_muy_danados"],
                 "  ⚠ CÁMARA A CIEGAS: lo de abajo no mide el comportamiento"
                 if m["img_muy_danados"] > 0.2 * m["img_medidos"] else ""))

    print("\nTiempo por estado: " + "  ".join(
        "%s %.1f s" % kv for kv in sorted(m["tiempo_por_estado"].items(),
                                         key=lambda kv: -kv[1])))
    for t, d, h, motivo in m["transiciones"]:
        print("  %6.1fs  %-10s → %-10s  %s" % (t, d, h, motivo))

    print("\nBUSCAR")
    r = m["rachas_barriendo"]
    if r:
        n = par.get("N_CONFIRMAR", config.N_CONFIRMAR)
        print("  rachas del oso visto GIRANDO: %s  (hacen falta %d seguidos para confirmar)"
              % (r, n))
        if par.get("BUSCAR_FRENAR_AL_VER"):
            print("  → con BUSCAR_FRENAR_AL_VER frena al primer frame: rachas cortas por diseño")
        else:
            print("  → %d de %d rachas alcanzan para confirmar sin frenar"
                  % (sum(1 for x in r if x >= n), len(r)))
    else:
        print("  el oso no se vio nunca con el robot girando")
    for c in m["confirmaciones"]:
        print("  %.1fs: confirmado %.2f s después de verlo · ex %s → %s a los 0,5 s%s"
              % (c["t"], c["demora_s"],
                 "%+.2f" % c["ex_primero"] if c["ex_primero"] is not None else "?",
                 "%+.2f" % c["ex_0_5s"] if c["ex_0_5s"] is not None else "—",
                 "  ← LO PERDIÓ (se pasó de largo)" if c["lo_perdio"] else ""))

    if "aprox_frames" in m:
        print("\nAPROXIMAR (%d frames con el oso)" % m["aprox_frames"])
        print("  ex: RMS %.3f, máx %.2f · %.0f %% de los frames fuera de la zona muerta"
              % (m["aprox_ex_rms"], m["aprox_ex_max"], 100 * m["aprox_fuera_zona"]))
        print("  cruces de lado fuera de la zona muerta: %d · cambios de sentido de giro: %d"
              % (m["aprox_cruces"], m["aprox_cambios_giro"]))
        if m["aprox_cruces"] >= 3:
            print("  ⚠ oscila: bajar KP_ANG antes que agrandar ZONA_MUERTA_ERROR_X")
    print("  'objetivo perdido' (APROXIMAR → BUSCAR): %d" % m["perdidas"])

    print("\nENCONTRADO")
    if m["t_encontrado"] is None:
        print("  no llegó")
    else:
        print("  a los %.1f s · ar al frenar %.3f (objetivo %s)%s"
              % (m["t_encontrado"], m.get("ar_al_frenar", float("nan")),
                 par.get("AREA_OBJETIVO", config.AREA_OBJETIVO),
                 " · ex %+.2f" % m["ex_al_frenar"] if m.get("ex_al_frenar") is not None else ""))
        if "ar_quieto" in m:
            print("  ar con el robot quieto: %.3f — si es mayor que al frenar, se pasó"
                  % m["ar_quieto"])
        print("  ⬜ anotar la distancia REAL con cinta: tiene que ser ~50 cm")

    print("\nHUIR")
    for h in m["huidas"]:
        print("  %.1fs: decidió huir %.2f s después de ver la mochila (confirmada al frame %d)"
              % (h["t"], h["latencia_s"], h["frames_vista"] + 1))
    if m["huidas"]:
        print("  + ~0,15 s de edad del frame e inferencia antes de eso, que el CSV no ve")
    if not m["huidas"]:
        print("  no hubo huidas")
    print("  frames con mochila detectada: %d%s"
          % (m["frames_con_mochila"],
             " ← sin mochila en la escena, cada uno es un falso positivo"
             if m["frames_con_mochila"] and not m["huidas"] else ""))


def tabla(resultados):
    """Una línea por corrida, para los 10 por escenario de §10."""
    print("\n%-34s %6s %6s %5s %5s %6s %6s" % (
        "corrida", "FPS", "t_enc", "perd", "cruc", "ar_fin", "huidas"))
    for ruta, m in resultados:
        print("%-34s %6.2f %6s %5d %5s %6s %6d" % (
            Path(ruta).stem[:34], m.get("fps") or 0,
            "%.1f" % m["t_encontrado"] if m.get("t_encontrado") is not None else "—",
            m.get("perdidas", 0),
            m.get("aprox_cruces", "—"),
            "%.3f" % m["ar_al_frenar"] if "ar_al_frenar" in m else "—",
            len(m.get("huidas", []))))
    llegaron = [m for _, m in resultados if m.get("t_encontrado") is not None]
    print("\nLlegaron a ENCONTRADO: %d/%d" % (len(llegaron), len(resultados)))
    if len(llegaron) >= 2:
        ts = [m["t_encontrado"] for m in llegaron]
        print("Tiempo hasta ENCONTRADO: %.1f ± %.1f s" % (statistics.mean(ts), statistics.stdev(ts)))


def main(argv=None):
    rutas = (argv if argv is not None else sys.argv[1:])
    if not rutas:
        print(__doc__)
        return 1
    resultados = []
    for ruta in rutas:
        filas, meta = leer(ruta)
        m = analizar(filas, meta)
        informar(ruta, m, meta)
        resultados.append((ruta, m))
        print()
    if len(resultados) > 1:
        tabla(resultados)
    return 0


if __name__ == "__main__":
    sys.exit(main())
