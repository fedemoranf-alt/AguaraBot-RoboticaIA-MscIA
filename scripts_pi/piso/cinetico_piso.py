"""Mínimo para SEGUIR girando en el piso: rampa descendente sin pausas (modo C).

⚠️ Modo calibración = sin watchdog. El finally devuelve el ESP32 a protocolo.
"""
import time

import serial

SERIES = [
    ("A", 0, "izquierda", 380, (350, 320, 290, 260, 230, 200, 170)),
    ("B", 1, "derecha", 280, (250, 220, 190, 160, 130, 100)),
]
ARRANQUE_S, PASO_S, ENTRE_S = 1.0, 1.0, 3.0

ser = serial.Serial("/dev/ttyUSB0", 115200, timeout=0.05)
time.sleep(2.2)
ser.reset_input_buffer()
t_ini = time.monotonic()


def enviar(txt, nota=""):
    ser.write((txt + "\n").encode())
    print("%5.1fs  %s%s" % (time.monotonic() - t_ini, txt, nota), flush=True)


try:
    for nombre, rueda, lado, arranque, pasos in SERIES:
        print("\n== Serie %s: rueda %s ==" % (nombre, lado), flush=True)
        enviar("C,%d,%d" % (rueda, arranque))
        time.sleep(ARRANQUE_S)
        for i, d in enumerate(pasos, 1):
            enviar("C,%d,%d" % (rueda, d), "   <- escalón %d (segundo %d)" % (i, i))
            time.sleep(PASO_S)
        enviar("C,%d,0" % rueda)
        time.sleep(ENTRE_S)
finally:
    for linea in (b"C,2,0\n", b"x\n", b"p\n"):
        ser.write(linea)
        time.sleep(0.1)
    time.sleep(0.2)
    fin = ser.read_all().decode("ascii", "replace")
    ser.close()
    print("\nfin: ruedas en 0; ESP32 dice:",
          "watchdog ACTIVO" if "watchdog ACTIVO" in fin else "(sin confirmación)", flush=True)
