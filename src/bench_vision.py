"""
TPF Robótica IA — Banco de medición del lazo de visión (Día 3)
==============================================================================
Mide el FPS REAL de la cadena cámara → YOLOv8n → detecciones en el Pi, que es
el criterio de aceptación de PLAN.md §10 (≥ 5 FPS) y el número del que cuelga
todo el diseño del control: a 5 FPS el robot avanza entre 1,8 y 7,6 cm entre
frame y frame (ver scripts_auxiliares/01_calibracion_motores.ipynb).

Barre varios tamaños de inferencia porque la palanca de PLAN.md §11 es
justamente bajar la resolución. Separa el tiempo en tres etapas —captura,
inferencia y postproceso— porque si el cuello de botella es la cámara y no la
red, bajar `imgsz` no arregla nada.

Uso en el Pi:

    python bench_vision.py                        # barrido por defecto
    python bench_vision.py --en-vivo              # Paso 13 por SSH: ex/ar en consola
    python bench_vision.py --tam 640 --preview    # una sola config, con ventana
    python bench_vision.py --frames 200           # más muestras, menos ruido

Deja los resultados en logs/ (JSON con el resumen y CSV por frame), listos
para el cuaderno de análisis.
"""

from __future__ import annotations

import argparse
import csv
import json
import platform
import statistics
import sys
import time
from datetime import datetime

import numpy as np

import config
import vision


# ==============================================================================
# 1. Una corrida
# ==============================================================================
class CamaraSintetica:
    """Cámara falsa que devuelve ruido, para medir SIN cámara conectada.

    Nació el 2026-09-09, con la Arducam bloqueada por el conector de 15 pines:
    el costo del lazo es casi todo inferencia, así que se lo puede medir sin
    captura y decidir `TAM_INFERENCIA` igual. Fue lo que fijó el 320.

    ⚠️ **Lo que mide NO es el FPS del lazo.** `Detector.detectar()` hace
    letterbox + inferencia + NMS; lo que falta es justo la captura, que en el
    barrido real puede ser el cuello de botella (y si lo es, bajar `imgsz` no
    arregla nada). El número de acá es un **techo optimista**: sirve para
    descartar tamaños, no para dar por cerrado el Paso 14.

    Devuelve varios cuadros distintos y pregenerados: uno solo invitaría a
    dudar de algún caché, y generarlos al vuelo mediría `np.random` en vez de
    la cámara ausente, que es lo que se quiere que cueste cero.
    """

    backend = "sintética (sin cámara)"

    def __init__(self, ancho, alto, n=4):
        self._ancho, self._alto = ancho, alto
        rng = np.random.default_rng(0)      # semilla fija: medición reproducible
        self._cuadros = [rng.integers(0, 255, (alto, ancho, 3), dtype=np.uint8)
                         for _ in range(n)]
        self._i = 0

    def leer(self):
        cuadro = self._cuadros[self._i % len(self._cuadros)]
        self._i += 1
        return cuadro

    def resolucion_real(self):
        return self._ancho, self._alto

    def cerrar(self):
        pass


def medir(cam, tam, n_frames, pesos, preview=False):
    """Mide n_frames con un tamaño de inferencia dado. Devuelve (resumen, filas)."""
    det = vision.Detector(pesos=pesos, tam=tam)
    print(f"\n  modelo: {det.describir()}")

    # Descarte de calentamiento: las primeras inferencias son mucho más lentas.
    frame = cam.leer()
    if frame is None:
        raise RuntimeError("La cámara no entregó ningún frame.")
    print("  calentando...", end="", flush=True)
    det.calentar(frame, n=3)
    print(" listo")

    filas = []
    t_inicio = time.perf_counter()
    for i in range(n_frames):
        t0 = time.perf_counter()
        frame = cam.leer()
        t1 = time.perf_counter()
        if frame is None:
            print("  ⚠️  frame perdido, se descarta")
            continue

        detecciones, tiempos = det.detectar(frame)
        t2 = time.perf_counter()

        filas.append({
            "i": i,
            "tam_inferencia": tam,
            "captura_ms": (t1 - t0) * 1000,
            "inferencia_ms": tiempos["inferencia_ms"],
            "postproceso_ms": tiempos["postproceso_ms"],
            "total_ms": (t2 - t0) * 1000,
            "n_detecciones": len(detecciones),
            "clases": "|".join(sorted({d.clase for d in detecciones})),
        })

        if preview:
            import cv2
            fps_inst = 1000.0 / max(filas[-1]["total_ms"], 1e-6)
            vision.dibujar(frame, detecciones,
                           f"imgsz={tam}  {fps_inst:4.1f} FPS  "
                           f"({filas[-1]['total_ms']:.0f} ms)")
            cv2.imshow("TPF - bench de vision (q para salir)", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

        if (i + 1) % 20 == 0:
            print(f"  {i + 1}/{n_frames} frames", end="\r", flush=True)

    duracion = time.perf_counter() - t_inicio
    if not filas:
        raise RuntimeError("No se pudo medir ningún frame.")

    totales = [f["total_ms"] for f in filas]
    resumen = {
        "tam_inferencia": tam,
        "n_frames": len(filas),
        "duracion_s": round(duracion, 2),
        "fps_medio": round(len(filas) / duracion, 2),
        "latencia_media_ms": round(statistics.fmean(totales), 1),
        "latencia_p50_ms": round(statistics.median(totales), 1),
        "latencia_p95_ms": round(_percentil(totales, 95), 1),
        "captura_ms": round(statistics.fmean(f["captura_ms"] for f in filas), 1),
        "inferencia_ms": round(statistics.fmean(f["inferencia_ms"] for f in filas), 1),
        "postproceso_ms": round(statistics.fmean(f["postproceso_ms"] for f in filas), 1),
        "frames_con_deteccion": sum(1 for f in filas if f["n_detecciones"] > 0),
    }
    print(f"  {resumen['fps_medio']:5.2f} FPS  ·  "
          f"latencia {resumen['latencia_media_ms']:.0f} ms "
          f"(p95 {resumen['latencia_p95_ms']:.0f})            ")
    return resumen, filas


def en_vivo(cam, tam, pesos, cada_foto_s=1.0):
    """Paso 13 sin escritorio: una línea por frame con `ex` y `ar`, y una foto.

    El Pi corre headless, así que `--preview` (cv2.imshow) no tiene dónde abrir
    la ventana por SSH. Lo que el Paso 13 necesita son números —el signo de
    `ex` y el `ar` a la distancia de frenado— y eso entra por la consola.

    La foto anotada se sobrescribe en logs/vivo.jpg para mirar el encuadre
    desde la PC. Hace falta mirarla: una cámara montada al revés o espejada
    invierte el signo de `ex`, y en los números solos eso no se distingue de
    un error de código.
    """
    import cv2

    det = vision.Detector(pesos=pesos, tam=tam)
    print(f"\n  modelo: {det.describir()}")
    frame = cam.leer()
    if frame is None:
        raise RuntimeError("La cámara no entregó ningún frame.")
    det.calentar(frame, n=3)

    config.DIR_LOGS.mkdir(parents=True, exist_ok=True)
    ruta_foto = config.DIR_LOGS / "vivo.jpg"
    ruta_tmp = config.DIR_LOGS / "vivo.tmp.jpg"   # imwrite elige el formato por extensión
    print(f"  foto anotada cada {cada_foto_s:.0f} s en logs/{ruta_foto.name}")
    print("  Ctrl+C para terminar\n")

    t0 = time.perf_counter()
    t_foto = -cada_foto_s
    while True:
        frame = cam.leer()
        if frame is None:
            print("  ⚠️  frame perdido")
            continue
        detecciones, _ = det.detectar(frame)
        t = time.perf_counter() - t0

        partes = [f"{d.clase:<11} {d.conf:.2f}  ex={d.error_x:+.2f}  ar={d.area_ratio:.3f}"
                  for d in sorted(detecciones, key=lambda d: -d.area_ratio)]
        print(f"  {t:6.1f}s  " + (" | ".join(partes) if partes else "(nada)"))

        if t - t_foto >= cada_foto_s:
            # Escribir aparte y renombrar: un scp a mitad de escritura se
            # llevaría un JPEG cortado.
            cv2.imwrite(str(ruta_tmp), vision.dibujar(frame, detecciones))
            ruta_tmp.replace(ruta_foto)
            t_foto = t


def _percentil(datos, p):
    ordenados = sorted(datos)
    k = (len(ordenados) - 1) * p / 100.0
    bajo, alto = int(k), min(int(k) + 1, len(ordenados) - 1)
    return ordenados[bajo] + (ordenados[alto] - ordenados[bajo]) * (k - bajo)


# ==============================================================================
# 2. Informe
# ==============================================================================
def informe(resumenes, objetivo):
    print("\n" + "=" * 78)
    print("RESULTADO — lazo de visión")
    print("=" * 78)
    cab = f"{'imgsz':>7} {'FPS':>7} {'lat.med':>9} {'p95':>7} " \
          f"{'captura':>9} {'inferen.':>9} {'postpr.':>9} {'≥ objetivo':>11}"
    print(cab)
    print("-" * 78)
    for r in resumenes:
        ok = "✅ sí" if r["fps_medio"] >= objetivo else "❌ no"
        print(f"{r['tam_inferencia']:>7} {r['fps_medio']:>7.2f} "
              f"{r['latencia_media_ms']:>8.0f}ms {r['latencia_p95_ms']:>6.0f}ms "
              f"{r['captura_ms']:>8.1f}ms {r['inferencia_ms']:>8.1f}ms "
              f"{r['postproceso_ms']:>8.1f}ms {ok:>11}")
    print("-" * 78)

    mejor = max(resumenes, key=lambda r: r["fps_medio"])
    aptos = [r for r in resumenes if r["fps_medio"] >= objetivo]

    # Recomendar "el mayor que llega al objetivo" ya engañó una vez: el 480
    # daba 5,26 FPS sin captura (2026-09-09) y se lo dio por bueno. Por eso
    # acá se pide margen, y al que llega raspando se lo nombra como lo que es.
    #
    # Ojo con el motivo: NO es que el resto del lazo se coma el FPS. Medido el
    # 2026-09-22, la máquina de estados y el enlace cuestan ~1 % (11,33 → 11,22
    # con imgsz 320). El margen se pide por la LATENCIA, que el FPS esconde: a
    # 480 son 193 ms por decisión contra 88 ms a 320, y a 0,38 m/s eso son 7,4
    # cm de avance a ciegas contra 3,4 cm. Y porque un número al borde del
    # objetivo no deja lugar para el calor del chasis ni para una escena peor.
    MARGEN = 1.5
    con_margen = [r for r in resumenes if r["fps_medio"] >= objetivo * MARGEN]

    print(f"\nObjetivo de PLAN.md §10: ≥ {objetivo:.0f} FPS")
    if aptos:
        v_min, v_max = config.V_MIN_MS, config.V_MAX_MS
        print(f"  ✅ Cumplen {len(aptos)} de {len(resumenes)} configuraciones.")
        if con_margen:
            # El mayor con margen: más resolución = detección más estable lejos.
            elegido = max(con_margen, key=lambda r: r["tam_inferencia"])
            print(f"  → Recomendado: imgsz = {elegido['tam_inferencia']} "
                  f"({elegido['fps_medio']:.2f} FPS). Es el mayor que deja "
                  f"{MARGEN:.1f}× el objetivo para el resto del lazo.")
        else:
            elegido = max(aptos, key=lambda r: r["fps_medio"])
            print(f"  ⚠️  Ninguna llega a {objetivo * MARGEN:.0f} FPS: ninguna deja "
                  "margen para la máquina de estados y el enlace.")
            print(f"  → La más rápida es imgsz = {elegido['tam_inferencia']} "
                  f"({elegido['fps_medio']:.2f} FPS). Medir el lazo completo "
                  "(Paso 17) antes de fijarla.")
        for r in aptos:
            if r["fps_medio"] < objetivo * MARGEN:
                print(f"     imgsz {r['tam_inferencia']} llega al objetivo con "
                      f"{r['fps_medio']:.2f} FPS, pero sin margen: descartado.")
        fps = elegido["fps_medio"]
        print(f"  → Cargar TAM_INFERENCIA = {elegido['tam_inferencia']} en config.py")
        print(f"  → A {fps:.1f} FPS el robot avanza entre "
              f"{v_min * 100 / fps:.1f} y {v_max * 100 / fps:.1f} cm entre frames.")
    else:
        print(f"  ❌ Ninguna configuración llega. La mejor es imgsz = "
              f"{mejor['tam_inferencia']} con {mejor['fps_medio']:.2f} FPS.")
        cuello = max(
            [("la cámara", mejor["captura_ms"]),
             ("la inferencia", mejor["inferencia_ms"]),
             ("el postproceso", mejor["postproceso_ms"])],
            key=lambda p: p[1],
        )
        print(f"  → El cuello de botella es {cuello[0]} "
              f"({cuello[1]:.0f} ms de {mejor['latencia_media_ms']:.0f} ms).")
        if cuello[0] == "la inferencia":
            print("  → Palancas, en orden (PLAN.md §11): bajar imgsz a 320, "
                  "exportar a NCNN, procesar 1 de cada 2 frames.")
            print("     Exportar:  python -c \"from ultralytics import YOLO; "
                  "YOLO('yolov8n.pt').export(format='ncnn')\"")
            print("     Y después: python bench_vision.py --pesos yolov8n_ncnn_model")
        elif cuello[0] == "la cámara":
            print("  → Bajar imgsz NO va a ayudar: el costo está en la captura.")
            print("     Probar resolución de captura menor (--captura 320x240), "
                  "MJPG en vez de YUYV, o capturar en un hilo aparte.")

    print(f"\n  ⚠️  Anotar el valor elegido en PLAN.md §9 (Día 3) y §10.")
    return mejor


def guardar(resumenes, filas, cam, args):
    config.DIR_LOGS.mkdir(parents=True, exist_ok=True)
    sello = datetime.now().strftime("%Y%m%d_%H%M%S")

    meta = {
        "fecha": datetime.now().isoformat(timespec="seconds"),
        "equipo": platform.platform(),
        "python": sys.version.split()[0],
        "pesos": args.pesos,
        "camara_backend": cam.backend,
        "captura": f"{cam.ancho}x{cam.alto}",
        "umbral_confianza": config.UMBRAL_CONFIANZA,
        "frames_por_config": args.frames,
        "fps_objetivo": config.FPS_OBJETIVO,
        "resultados": resumenes,
    }
    ruta_json = config.DIR_LOGS / f"vision_bench_{sello}.json"
    ruta_json.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

    ruta_csv = config.DIR_LOGS / f"vision_bench_{sello}.csv"
    with ruta_csv.open("w", newline="", encoding="utf-8") as fh:
        escritor = csv.DictWriter(fh, fieldnames=list(filas[0].keys()))
        escritor.writeheader()
        escritor.writerows(filas)

    print(f"\n  Guardado: logs/{ruta_json.name}")
    print(f"            logs/{ruta_csv.name}  ({len(filas)} frames)")


# ==============================================================================
# 3. Main
# ==============================================================================
def main():
    p = argparse.ArgumentParser(description="Mide el FPS real del lazo de visión.")
    p.add_argument("--tam", default=None,
                   help="tamaños de inferencia a barrer, separados por coma "
                        "(default: 640,480,320; con --en-vivo, TAM_INFERENCIA)")
    p.add_argument("--frames", type=int, default=90,
                   help="frames medidos por configuración (default: 90)")
    p.add_argument("--pesos", default=config.PESOS_MODELO,
                   help="pesos o carpeta del modelo exportado (ej. yolov8n_ncnn_model)")
    p.add_argument("--camara", default=config.FUENTE_CAMARA,
                   choices=["auto", "csi", "usb"])
    p.add_argument("--captura", default=f"{config.ANCHO_CAPTURA}x{config.ALTO_CAPTURA}",
                   help="resolución de captura, ej. 640x480")
    p.add_argument("--indice", type=int, default=config.INDICE_CAMARA,
                   help="índice de la cámara USB (/dev/videoN)")
    p.add_argument("--preview", action="store_true",
                   help="muestra una ventana con las detecciones (necesita escritorio)")
    p.add_argument("--sin-camara", action="store_true",
                   help="medir con imagen sintética, sin cámara conectada "
                        "(techo optimista: no incluye la captura)")
    p.add_argument("--en-vivo", action="store_true",
                   help="Paso 13 sin escritorio: ex/ar por consola y foto anotada "
                        "en logs/vivo.jpg, hasta Ctrl+C. No mide ni guarda FPS")
    p.add_argument("--sin-guardar", action="store_true")
    args = p.parse_args()

    ancho, alto = (int(v) for v in args.captura.lower().split("x"))
    por_defecto = str(config.TAM_INFERENCIA) if args.en_vivo else "640,480,320"
    tams = [int(t) for t in (args.tam or por_defecto).split(",")]

    print("=" * 78)
    print("TPF — banco de medición del lazo de visión (Día 3)")
    print("=" * 78)
    print(f"  equipo   : {platform.platform()}")
    print(f"  captura  : {ancho}x{alto}")
    print(f"  barrido  : imgsz = {tams}")
    print(f"  frames   : {args.frames} por configuración")

    if args.sin_camara:
        cam = CamaraSintetica(ancho, alto)
        # Sin emoji a proposito: la consola de Windows va en cp1252 y no lo
        # traga, y este modo justamente se usa para probar en las dos maquinas.
        print("  [!] MODO SIN CAMARA: la captura no se mide, asi que el FPS de")
        print("      abajo es un TECHO. Sirve para descartar tamanos de")
        print("      inferencia, no para cerrar el Paso 14 del RUNBOOK.")
    else:
        cam = vision.Camara(ancho=ancho, alto=alto, fuente=args.camara, indice=args.indice)
    print(f"  cámara   : {cam.backend}")
    motivo_csi = getattr(cam, "motivo_csi", None)
    if motivo_csi and not cam.backend.startswith("csi"):
        print(f"             (CSI descartada: {motivo_csi})")
    real = cam.resolucion_real()
    if real and real != (ancho, alto):
        print(f"  ⚠️  la cámara entrega {real[0]}x{real[1]}, no lo pedido. "
              "Se mide con lo que entrega.")

    if args.en_vivo:
        try:
            en_vivo(cam, tams[0], args.pesos)
        except KeyboardInterrupt:
            print("\n  terminado")
        finally:
            cam.cerrar()
        return 0

    resumenes, todas = [], []
    try:
        for tam in tams:
            print(f"\n[imgsz = {tam}]")
            resumen, filas = medir(cam, tam, args.frames, args.pesos, args.preview)
            resumenes.append(resumen)
            todas.extend(filas)
    except KeyboardInterrupt:
        print("\n  interrumpido por el usuario")
    finally:
        cam.cerrar()
        if args.preview:
            import cv2
            cv2.destroyAllWindows()

    if not resumenes:
        print("No se completó ninguna medición.")
        return 1

    informe(resumenes, config.FPS_OBJETIVO)
    if not args.sin_guardar:
        guardar(resumenes, todas, cam, args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
