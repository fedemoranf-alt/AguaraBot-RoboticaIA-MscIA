"""Qué distancia mide el ultrasónico, con el robot quieto.

Lee la telemetría del ESP32 (D,<dist_cm>,...) durante unos segundos y la
resume. No manda ningún comando de movimiento: da lo mismo que los 12 V estén
puestos o no.

    python sonar.py [segundos]      # 5 por defecto

Abrir el puerto reinicia al ESP32: no usarlo con una corrida andando.
"""
import statistics
import sys
import time

import serial

DUR_S = float(sys.argv[1]) if len(sys.argv) > 1 else 5.0

ser = serial.Serial("/dev/ttyUSB0", 115200, timeout=0.05)
time.sleep(2.2)                     # abrir el puerto reinicia al ESP32
ser.reset_input_buffer()

todas, tramo, resto = [], [], ""
t_ini = t_tramo = time.monotonic()
try:
    while time.monotonic() - t_ini < DUR_S:
        resto += ser.read(256).decode("ascii", "replace")
        *lineas, resto = resto.split("\n")
        for linea in lineas:
            campos = linea.strip().split(",")
            if campos[0] != "D" or len(campos) != 4:
                continue
            try:
                tramo.append(int(campos[1]))
            except ValueError:
                pass
        if time.monotonic() - t_tramo >= 1.0:
            validas = [d for d in tramo if d >= 0]
            print("%4.0fs  %s  (%d lecturas, %d sin eco)"
                  % (time.monotonic() - t_ini,
                     ("%3.0f cm" % statistics.median(validas)) if validas else "  -- ",
                     len(tramo), len(tramo) - len(validas)), flush=True)
            todas += tramo
            tramo, t_tramo = [], time.monotonic()
finally:
    ser.close()

todas += tramo
validas = [d for d in todas if d >= 0]
print()
if not todas:
    print("SIN TELEMETRIA: el ESP32 no mandó ninguna línea D. ¿Arrancó?")
elif not validas:
    print("SIN LECTURA: %d líneas, todas en -1. El sensor no responde: revisar"
          " 5 V, GND y la línea SIG." % len(todas))
else:
    print("Lecturas: %d, válidas %d (%.0f %%)"
          % (len(todas), len(validas), 100.0 * len(validas) / len(todas)))
    print("Distancia: mín %d  mediana %.0f  máx %d cm"
          % (min(validas), statistics.median(validas), max(validas)))
