"""
TPF Robótica IA — Lazo principal (Día 4)
==============================================================================
Cierra el lazo percepción → decisión → actuación en el robot:

    cámara → YOLOv8n → confirmación temporal → máquina de estados → ESP32

Este archivo es sólo el cableado. Toda la inteligencia está en los módulos que
usa, y cada uno se puede verificar por separado sin los demás:

    vision.py        percepción      → bench_vision.py   (Día 3, en el Pi)
    control.py       ley de control  → python control.py (en cualquier lado)
    estados.py       comportamiento  → prueba_estados.py (en cualquier lado)
    enlace_esp32.py  protocolo       → --simular

Uso en el Pi:

    python main.py --simular          # sin ESP32: sólo mira y decide
    python main.py --tam 320          # el tamaño que haya salido del Día 3
    python main.py --espera 5         # 5 s para apoyar el robot y soltarlo
    python main.py --preview          # ventana con las cajas (baja el FPS)
    python main.py --nota "oso a 1 m"  # queda en el JSON de la corrida
    python main.py --grabar           # video anotado en logs/ (baja el FPS)

Cada corrida deja su CSV ciclo por ciclo en `logs/` (ver registro.py), que se
lee con `analizar_corrida.py`. `--sin-registro` lo apaga.

⚠️ El robot se mueve apenas arranca. `--espera` existe para eso: da tiempo a
apoyarlo en el piso y sacar las manos. Para las primeras corridas, el robot va
elevado con las ruedas al aire.
"""

from __future__ import annotations

import argparse
import signal
import sys
import time
from collections import Counter

import config
import control
import estados
from enlace_esp32 import Enlace
from registro import Registro
from vision import Camara, Confirmador, Detector, dibujar, franjas


_seguir = True


def _pedir_parada(*_):
    """Ctrl-C no corta el proceso de golpe: baja la bandera y deja que el lazo
    salga por su camino normal, que es el que frena los motores."""
    global _seguir
    _seguir = False


def parsear(argv=None):
    p = argparse.ArgumentParser(description="Lazo autónomo del TPF (Día 4)")
    p.add_argument("--simular", action="store_true",
                   help="no hablar con el ESP32: decide y loguea, pero no mueve")
    p.add_argument("--puerto", default=None, help="puerto serie del ESP32")
    p.add_argument("--tam", type=int, default=None, help="tamaño de inferencia")
    p.add_argument("--preview", action="store_true", help="ventana con las cajas")
    p.add_argument("--espera", type=float, default=3.0,
                   help="segundos antes de arrancar, para soltar el robot")
    p.add_argument("--duracion", type=float, default=0.0,
                   help="parar solo a los N segundos (0 = sin límite)")
    p.add_argument("--silencioso", action="store_true", help="una línea cada 10 ciclos")
    p.add_argument("--nota", default="",
                   help="qué escenario es esta corrida; va al JSON del registro")
    p.add_argument("--grabar", action="store_true",
                   help="guardar el video anotado junto al CSV (cuesta CPU)")
    p.add_argument("--sin-registro", action="store_true",
                   help="no escribir el CSV de la corrida en logs/")
    return p.parse_args(argv)


def main(argv=None):
    args = parsear(argv)
    signal.signal(signal.SIGINT, _pedir_parada)

    print(control.describir())

    cam = Camara()
    det = Detector(tam=args.tam)
    # resolucion_real() devuelve una tupla: el %s de antes intentaba rellenar
    # dos marcadores con ella y reventaba. No se había visto porque en la PC,
    # sin cámara, esta línea nunca llegó a ejecutarse (2026-09-22).
    res = cam.resolucion_real()
    print("Cámara: %s  %s" % (cam.backend, "%dx%d" % res if res else "sin frame"))
    print(det.describir())

    conf = Confirmador()
    maq = estados.Maquina()

    with Enlace(puerto=args.puerto, simular=args.simular) as esp:
        print(esp.describir())

        # Calentar antes de contar el tiempo: la primera inferencia de YOLO
        # tarda varias veces lo que las siguientes, y con el robot ya andando
        # ese retardo se paga en centímetros.
        det.calentar(cam.leer())

        # Sin ultrasónico el robot anda igual (dist = "no sé"), pero a ciegas:
        # avanza sin ver paredes. Que no pase sin que nadie se entere — el
        # 2026-10-02 se soltó un cable y una corrida entera salió sin lectura.
        if not args.simular and not esp.estado.hay_distancia:
            print("\n!! ULTRASÓNICO SIN LECTURA: el robot NO va a ver obstáculos."
                  "\n   Revisar los tres cables del sensor (demo.sh sonar)."
                  "\n   Para no correr así: Ctrl+C ahora.")

        if args.espera > 0:
            print("\nArranca en %.0f s — apoyá el robot y soltalo." % args.espera)
            for queda in range(int(args.espera), 0, -1):
                print("  %d..." % queda, end="\r", flush=True)
                time.sleep(1.0)
            print("  ¡vamos!    ")

        reg = None
        if not args.sin_registro:
            reg = Registro(grabar=args.grabar, extra={
                "nota": args.nota, "simular": args.simular,
                "puerto": args.puerto, "argv": sys.argv[1:]})
            print("Registro: %s" % reg.ruta)
        try:
            resumen = _correr(args, cam, det, conf, maq, esp, reg)
        finally:
            if reg is not None:
                reg.cerrar()

    cam.cerrar()
    _informar(resumen)
    if reg is not None:
        print("Registro: %s (%d filas)" % (reg.ruta, reg.filas))
        if reg.ruta_video is not None:
            print("Video:    %s" % reg.ruta_video)
    return 0


def _correr(args, cam, det, conf, maq, esp, reg=None):
    """El lazo. Devuelve el resumen de la corrida."""
    cv2 = None
    anotar = args.preview or (reg is not None and reg.ruta_video is not None)
    if args.preview:
        import cv2   # sólo si hace falta: en el robot final no hay pantalla

    ciclos = 0
    tiempo_por_estado = Counter()
    transiciones = []
    arranque = time.monotonic()
    estado_previo = maq.estado
    t_previo = arranque

    while _seguir:
        frame = cam.leer()
        if frame is None:
            print("! la cámara no entregó frame; corto")
            break

        # Antes de dibujar encima: mide el frame tal como llegó de la cámara.
        rotas = franjas(frame) if reg is not None else None
        detecciones, _ = det.detectar(frame)
        confirmadas = conf.actualizar(d.clase for d in detecciones)

        ahora = time.monotonic()
        cmd = maq.paso(confirmadas, detecciones, esp.estado, ahora)

        esp.mover(cmd.v_lin, cmd.v_ang)
        if cmd.buzzer is not None:
            esp.buzzer(cmd.buzzer)

        if reg is not None:
            reg.fila(ahora - arranque, ahora - t_previo, cmd, maq,
                     confirmadas, detecciones, esp.estado, rotas)

        # Contabilidad por estado: el tiempo se le carga al estado que estuvo
        # vigente DURANTE el intervalo, o sea el anterior a esta decisión.
        tiempo_por_estado[estado_previo] += ahora - t_previo
        t_previo = ahora
        if cmd.estado != estado_previo:
            transiciones.append((ahora - arranque, estado_previo, cmd.estado, cmd.motivo))
            print("  >> %-11s -> %-11s  %s" % (estado_previo, cmd.estado, cmd.motivo))
            estado_previo = cmd.estado

        ciclos += 1
        if not args.silencioso or ciclos % 10 == 0:
            print("[%6.1fs] %s  dist=%s" % (
                ahora - arranque, cmd,
                "--" if not esp.estado.hay_distancia else "%.0fcm" % esp.estado.dist_cm))

        if anotar:
            # Se dibuja una sola vez aunque haya ventana y video a la vez.
            dibujar(frame, detecciones, str(cmd))
            if reg is not None:
                reg.cuadro(frame)
        if args.preview:
            cv2.imshow("TPF", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

        if args.duracion and (ahora - arranque) >= args.duracion:
            print("\nSe cumplió --duracion")
            break

    if args.preview and cv2 is not None:
        cv2.destroyAllWindows()

    total = time.monotonic() - arranque
    return {
        "ciclos": ciclos,
        "segundos": total,
        "fps": ciclos / total if total > 0 else 0.0,
        "estado_final": maq.estado,
        "tiempo_por_estado": tiempo_por_estado,
        "transiciones": transiciones,
        "lineas_descartadas": esp.lineas_descartadas,
    }


def _informar(r):
    print("\n" + "=" * 62)
    print("Corrida: %d ciclos en %.1f s  ->  %.2f FPS del lazo completo"
          % (r["ciclos"], r["segundos"], r["fps"]))
    if r["fps"] and r["fps"] < config.FPS_OBJETIVO:
        print("  ! por debajo del objetivo de %.0f FPS (PLAN.md §10). Palancas en §11."
              % config.FPS_OBJETIVO)

    print("\nTiempo por estado:")
    for est, seg in r["tiempo_por_estado"].most_common():
        print("  %-11s %6.1f s" % (est, seg))

    print("\nTransiciones: %d" % len(r["transiciones"]))
    for t, desde, hasta, motivo in r["transiciones"]:
        print("  %6.1fs  %-11s -> %-11s  %s" % (t, desde, hasta, motivo))

    if r["lineas_descartadas"]:
        print("\nLíneas del ESP32 descartadas: %d (diagnóstico y ruido de arranque)"
              % r["lineas_descartadas"])
    print("Estado final: %s" % r["estado_final"])


if __name__ == "__main__":
    sys.exit(main())
