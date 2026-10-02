"""
TPF Robótica IA — Registro de corridas
==============================================================================
Una fila por ciclo del lazo, en CSV, para que la demo en piso deje NÚMEROS y no
sólo impresiones. La consola de `main.py` sirve para mirar en vivo; esto sirve
para contar después: cuánto tardó en encontrar, si oscila al centrarse, cuánto
se pasó al frenar el barrido, cuánto tardó en reaccionar a la mochila. Las
métricas de PLAN.md §10 piden 10 corridas por escenario, y eso no se saca
leyendo una consola.

Cada corrida deja dos archivos con el mismo nombre en `logs/`:

    corrida_20260930_153012.csv    una fila por ciclo
    corrida_20260930_153012.json   los parámetros con los que se corrió

El JSON no es opcional: el Día 5 va a cambiar KP_ANG, V_ANG_BUSCAR y los
tiempos de HUIR entre corrida y corrida, y un CSV sin sus parámetros es un
número sin el contexto donde vale — el hilo conductor del proyecto.

Opcionalmente (`--grabar` en main.py) también guarda el video anotado, que es la
vista desde el robot para el informe. Cuesta CPU: no usarlo en las corridas que
miden FPS o latencia.

    python analizar_corrida.py ../logs/corrida_20260930_153012.csv
"""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

import config
from vision import mejor


COLUMNAS = (
    "t_s", "dt_ms", "estado", "fase_huir", "v_lin", "v_ang", "buzzer",
    "confirmadas", "n_det",
    # Fracción de filas del frame que llegaron como franja gris (vision.franjas):
    # sin esto, "no vio el oso" y "la cámara estaba ciega" se ven igual en el CSV.
    "franjas",
    # La mejor caja CRUDA de cada clase en este frame, confirmada o no. Es lo
    # que permite medir cuánto tarda la confirmación desde el primer avistamiento.
    "obj_conf", "obj_ex", "obj_ar", "obj_w", "obj_h",
    "amz_conf", "amz_ex", "amz_ar",
    "dist_cm", "motivo",
)

# Los parámetros que el Día 5 calibra, más los que fijan el contexto de la
# medición. Van al JSON de cada corrida.
PARAMETROS = (
    "TAM_INFERENCIA", "UMBRAL_CONFIANZA", "N_CONFIRMAR", "M_PERDER",
    "KP_ANG", "KP_LIN", "AREA_OBJETIVO", "ZONA_MUERTA_ERROR_X",
    "V_LIN_MAX", "V_ANG_MAX", "V_ANG_BUSCAR", "BUSCAR_GIRO_S",
    "BUSCAR_AVANCE_S", "V_LIN_BUSCAR", "BUSCAR_FRENAR_AL_VER",
    "BUSCAR_SENTIDO_AZAR_TRAS_HUIR",
    "BUSCAR_PASO_GIRO_S", "BUSCAR_PASO_MIRAR_S", "FORMATO_CAMARA",
    "HUIR_RETROCESO_S", "HUIR_GIRO_S", "HUIR_AVANCE_S", "HUIR_V_RETROCESO",
    "HUIR_GIRO_RETROCESO", "HUIR_V_AVANCE", "HUIR_REFRACTARIO_S",
    "DIST_PARADA_CM", "DIST_OBSTACULO_CM", "SONAR_CENTRADO",
    "SONAR_FRACCION_AREA", "SONAR_RETENCION_S",
    "CLASE_OBJETIVO", "CLASE_AMENAZA",
)


def _num(v, formato):
    return "" if v is None else formato % v


class Registro:
    """Escribe el CSV de una corrida, y el video si se pide."""

    def __init__(self, directorio=None, nombre=None, extra=None, grabar=False):
        directorio = Path(directorio or config.DIR_LOGS)
        directorio.mkdir(parents=True, exist_ok=True)
        nombre = nombre or datetime.now().strftime("corrida_%Y%m%d_%H%M%S")
        self.ruta = directorio / (nombre + ".csv")

        meta = {"inicio": datetime.now().isoformat(timespec="seconds"),
                "parametros": {p: getattr(config, p) for p in PARAMETROS}}
        meta.update(extra or {})
        with open(directorio / (nombre + ".json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

        # Con buffer de línea: si la corrida termina mal (corte de la UPS,
        # kill), lo escrito hasta ese ciclo queda en disco. A ~11 filas por
        # segundo el costo es despreciable.
        self._f = open(self.ruta, "w", newline="", encoding="utf-8", buffering=1)
        self._w = csv.writer(self._f)
        self._w.writerow(COLUMNAS)
        self.filas = 0

        self.ruta_video = directorio / (nombre + ".avi") if grabar else None
        self._video = None

    def fila(self, t, dt, cmd, maq, confirmadas, detecciones, estado_esp, franjas=None):
        obj = mejor(detecciones, config.CLASE_OBJETIVO)
        amz = mejor(detecciones, config.CLASE_AMENAZA)
        self._w.writerow((
            "%.3f" % t, "%.1f" % (dt * 1000), cmd.estado, maq.fase_huir,
            cmd.v_lin, cmd.v_ang, "" if cmd.buzzer is None else cmd.buzzer,
            "|".join(sorted(confirmadas)), len(detecciones),
            _num(franjas, "%.3f"),
            _num(obj and obj.conf, "%.2f"), _num(obj and obj.error_x, "%.3f"),
            _num(obj and obj.area_ratio, "%.4f"),
            "" if obj is None else obj.w, "" if obj is None else obj.h,
            _num(amz and amz.conf, "%.2f"), _num(amz and amz.error_x, "%.3f"),
            _num(amz and amz.area_ratio, "%.4f"),
            _num(estado_esp.dist_cm, "%.0f"), cmd.motivo,
        ))
        self.filas += 1

    def cuadro(self, frame_anotado, fps=10.0):
        """Agrega un frame ya anotado (vision.dibujar) al video."""
        if self.ruta_video is None:
            return
        if self._video is None:
            import cv2
            alto, ancho = frame_anotado.shape[:2]
            # MJPG en AVI: comprime cuadro por cuadro, sin estado entre frames,
            # que es lo más barato de codificar en el Pi y lo que menos se
            # rompe si la corrida se corta a mitad.
            self._video = cv2.VideoWriter(str(self.ruta_video),
                                          cv2.VideoWriter_fourcc(*"MJPG"),
                                          fps, (ancho, alto))
        self._video.write(frame_anotado)

    def cerrar(self):
        self._f.close()
        if self._video is not None:
            self._video.release()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.cerrar()
