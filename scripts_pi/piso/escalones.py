"""Escalones de comando en el piso, por el protocolo normal (watchdog activo)."""
import sys
import time

sys.path.insert(0, "/home/admin/TPF/src")
from enlace_esp32 import Enlace  # noqa: E402

PASOS = [(0, 60, 2.0), (0, 80, 2.0), (0, 100, 2.0), (40, 0, 1.0), (72, 0, 1.0)]

with Enlace() as esp:
    print(esp.describir(), flush=True)
    time.sleep(0.5)
    t_ini = time.monotonic()
    try:
        for i, (vl, va, dur) in enumerate(PASOS, 1):
            print("%5.1fs  paso %d: M,%d,%d durante %.0f s"
                  % (time.monotonic() - t_ini, i, vl, va, dur), flush=True)
            t0 = time.monotonic()
            while time.monotonic() - t0 < dur:
                esp.mover(vl, va)
                time.sleep(0.05)
            esp.parar()
            print("%5.1fs  pausa" % (time.monotonic() - t_ini), flush=True)
            time.sleep(2.0)
    finally:
        esp.parar()
print("fin", flush=True)
