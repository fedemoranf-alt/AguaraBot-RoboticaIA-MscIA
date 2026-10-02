"""Umbral de arranque de cada rueda en el piso, con duty crudo (modo C del firmware).

⚠️ En modo calibración el ESP32 NO tiene watchdog: el finally lo devuelve a
protocolo ('x' para soltar, 'p' para reactivar el watchdog) pase lo que pase.
"""
import sys
import time

import serial

SERIES = [
    ("A", 0, "izquierda", (250, 300, 350, 400, 450)),
    ("B", 1, "derecha", (150, 200, 250, 300)),
]
PASO_S, PAUSA_S = 0.7, 1.5


def leer(ser):
    for linea in ser.read_all().decode("ascii", "replace").splitlines():
        if linea.startswith("#"):
            print("        esp32: " + linea, flush=True)


ser = serial.Serial("/dev/ttyUSB0", 115200, timeout=0.05)
time.sleep(2.2)                     # abrir el puerto reinicia al ESP32
ser.reset_input_buffer()
t_ini = time.monotonic()
try:
    for nombre, rueda, lado, duties in SERIES:
        print("\n== Serie %s: rueda %s ==" % (nombre, lado), flush=True)
        for i, d in enumerate(duties, 1):
            print("%5.1fs  %s%d: C,%d,%d" % (time.monotonic() - t_ini, nombre, i, rueda, d),
                  flush=True)
            ser.write(b"C,%d,%d\n" % (rueda, d))
            time.sleep(PASO_S)
            ser.write(b"C,%d,0\n" % rueda)
            leer(ser)
            time.sleep(PAUSA_S)
        time.sleep(1.5)
finally:
    ser.write(b"C,2,0\n")
    time.sleep(0.1)
    ser.write(b"x\n")
    time.sleep(0.1)
    ser.write(b"p\n")
    time.sleep(0.3)
    leer(ser)
    ser.close()
    print("\nfin: ruedas en 0 y watchdog reactivado", flush=True)
