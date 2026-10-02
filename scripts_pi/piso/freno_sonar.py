"""A qué distancia de una pared queda el robot si frena por el ultrasónico.

⚠️ MUEVE EL ROBOT. Avanza derecho hacia lo que tenga adelante y frena cuando
el ultrasónico lee UMBRAL cm o menos. Sirve para elegir `DIST_PARADA_CM`: lo
que importa no es dónde se manda frenar sino dónde termina parado, que es
más cerca (el lazo tarda en enterarse y el robot sigue un poco por inercia).

    python freno_sonar.py [v_lin] [umbral_cm] [segundos_max]
    python freno_sonar.py 60 20 4        # los valores por defecto

Poner el robot a 1 m o más de la pared, de frente. Va en modo protocolo, con
el watchdog del ESP32 activo: si este script muere, el robot frena solo.
Si no hay lectura del sensor NO arranca.
"""
import sys
import time

import serial

V_LIN = int(sys.argv[1]) if len(sys.argv) > 1 else 60
UMBRAL_CM = int(sys.argv[2]) if len(sys.argv) > 2 else 20
MAX_S = float(sys.argv[3]) if len(sys.argv) > 3 else 4.0
PERIODO_S = 0.09            # ~11 Hz, el ritmo del lazo de main.py

ser = serial.Serial("/dev/ttyUSB0", 115200, timeout=0.02)
time.sleep(2.2)
ser.reset_input_buffer()

dist, resto = None, ""


def leer():
    """Deja en `dist` la última distancia válida que mandó el ESP32."""
    global dist, resto
    resto += ser.read(256).decode("ascii", "replace")
    *lineas, resto = resto.split("\n")
    for linea in lineas:
        campos = linea.strip().split(",")
        if campos[0] == "D" and len(campos) == 4:
            try:
                d = int(campos[1])
            except ValueError:
                continue
            dist = d if d >= 0 else None


def mandar(v_lin):
    ser.write(b"M,%d,0\n" % v_lin)


try:
    t0 = time.monotonic()
    while time.monotonic() - t0 < 1.0:
        leer()
    if dist is None:
        print("SIN LECTURA del ultrasónico: no arranco.")
        sys.exit(1)
    print("Antes de arrancar: %d cm. Avanzo a v_lin=%d hasta leer <= %d cm."
          % (dist, V_LIN, UMBRAL_CM), flush=True)
    if dist <= UMBRAL_CM:
        print("Ya está más cerca que el umbral: no arranco.")
        sys.exit(1)

    t0 = time.monotonic()
    motivo = "se cumplió el tiempo máximo (%.1f s) sin llegar al umbral" % MAX_S
    dist_freno = None
    while time.monotonic() - t0 < MAX_S:
        leer()
        if dist is not None and dist <= UMBRAL_CM:
            dist_freno = dist
            motivo = "umbral"
            break
        mandar(V_LIN)
        print("%5.2fs  %s cm" % (time.monotonic() - t0,
                                 "--" if dist is None else "%3d" % dist), flush=True)
        time.sleep(PERIODO_S)
    t_freno = time.monotonic() - t0

    # Frenar y esperar a que se quede quieto, sin dejar de mandar M,0,0.
    t1 = time.monotonic()
    while time.monotonic() - t1 < 1.5:
        mandar(0)
        leer()
        time.sleep(PERIODO_S)

    print()
    if dist_freno is None:
        print("NO FRENÓ POR EL SENSOR: %s. Quedó a %s cm."
              % (motivo, "--" if dist is None else dist))
    else:
        print("Mandó frenar a los %.2f s, leyendo %d cm." % (t_freno, dist_freno))
        print("Quedó parado a %s cm: siguió %s cm después de la orden."
              % ("--" if dist is None else dist,
                 "--" if dist is None else dist_freno - dist))
finally:
    mandar(0)
    time.sleep(0.1)
    ser.close()
