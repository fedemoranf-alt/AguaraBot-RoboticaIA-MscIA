"""
TPF Robótica IA — Capa de percepción
==============================================================================
Captura de cámara + YOLOv8n + filtrado de clases + confirmación temporal.

Este módulo NO decide comportamiento y NO habla con el ESP32: sólo convierte
frames en detecciones con los dos números que la ley de control necesita
(PLAN.md §7):

    error_x    = ((x + w/2) − W/2) / (W/2)      → [-1, +1], + significa derecha
    area_ratio = (w · h) / (W · H)              → proxy de distancia

Uso típico:

    cam = Camara()
    det = Detector()
    for _ in range(100):
        frame = cam.leer()
        detecciones, tiempos = det.detectar(frame)

Correr `python bench_vision.py` para medir el FPS real (Día 3 del cronograma).
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np

import config


# ==============================================================================
# 1. Detección
# ==============================================================================
@dataclass(frozen=True)
class Deteccion:
    """Una caja detectada, ya convertida a las magnitudes del control."""

    clase: str
    conf: float
    x: int          # esquina superior izquierda
    y: int
    w: int
    h: int
    error_x: float  # desviación lateral normalizada, [-1, +1]
    area_ratio: float

    @property
    def centro(self):
        return self.x + self.w // 2, self.y + self.h // 2


def _a_deteccion(clase, conf, x1, y1, x2, y2, ancho_img, alto_img):
    """Convierte una caja xyxy en píxeles a una Deteccion (PLAN.md §7)."""
    x, y = int(x1), int(y1)
    w, h = int(x2 - x1), int(y2 - y1)
    error_x = ((x + w / 2) - ancho_img / 2) / (ancho_img / 2)
    area_ratio = (w * h) / float(ancho_img * alto_img)
    return Deteccion(clase, float(conf), x, y, w, h, error_x, area_ratio)


class Detector:
    """YOLOv8n preentrenado en COCO, filtrado a las clases de interés.

    Los IDs de clase se resuelven contra `model.names` en vez de hardcodear
    los de COCO (backpack 24, teddy bear 77): si algún día se cambia el modelo,
    esto falla ruidosamente en el arranque en vez de detectar la clase
    equivocada en silencio (PLAN.md §5 D3).
    """

    def __init__(self, pesos=None, tam=None, conf=None, iou=None, clases=None):
        from ultralytics import YOLO  # import perezoso: tarda ~2 s

        self.pesos = pesos or config.PESOS_MODELO
        self.tam = tam or config.TAM_INFERENCIA
        self.conf = conf if conf is not None else config.UMBRAL_CONFIANZA
        self.iou = iou if iou is not None else config.UMBRAL_IOU
        clases = tuple(clases or config.CLASES_DE_INTERES)

        self.modelo = YOLO(self.pesos)
        self.nombres = dict(self.modelo.names)

        # Resolución nombre → id, con error explícito si el modelo no la tiene.
        por_nombre = {v: k for k, v in self.nombres.items()}
        faltantes = [c for c in clases if c not in por_nombre]
        if faltantes:
            raise ValueError(
                f"El modelo {self.pesos} no conoce estas clases: {faltantes}. "
                f"Clases disponibles: {sorted(por_nombre)[:10]}..."
            )
        # Alias: otros nombres del modelo para el mismo objeto (config.ALIAS_CLASES).
        # Se le piden también a YOLO, y detectar() los devuelve ya renombrados.
        self.alias = {a: c for a, c in config.ALIAS_CLASES.items()
                      if c in clases and a in por_nombre}
        self.ids = [por_nombre[c] for c in clases] + [por_nombre[a] for a in self.alias]
        self.clases = clases
        # Umbral por clase (config.UMBRAL_POR_CLASE): a YOLO se le pide con el
        # más bajo de todos y detectar() filtra cada caja con el de su clase.
        self.conf_clase = {c: config.UMBRAL_POR_CLASE.get(c, self.conf) for c in clases}
        self._conf_minima = min([self.conf] + list(self.conf_clase.values()))

    def describir(self):
        pares = ", ".join(f"{c} = {i}" for c, i in zip(self.clases, self.ids))
        alias = "".join(f" · {a} cuenta como {c}" for a, c in self.alias.items())
        propios = "".join(f" · conf {c} = {u}" for c, u in self.conf_clase.items()
                          if u != self.conf)
        return (f"{self.pesos} · imgsz={self.tam} · conf={self.conf} · [{pares}]"
                f"{alias}{propios}")

    def calentar(self, frame, n=3):
        """Primeras inferencias: son mucho más lentas (alocación, cachés).

        Medirlas junto con el resto arruina el promedio, así que se descartan
        a propósito.
        """
        for _ in range(n):
            self.detectar(frame)

    def detectar(self, frame):
        """Devuelve (lista de Deteccion, dict de tiempos en ms)."""
        alto, ancho = frame.shape[:2]

        t0 = time.perf_counter()
        salida = self.modelo.predict(
            frame,
            imgsz=self.tam,
            conf=self._conf_minima,
            iou=self.iou,
            classes=self.ids,     # el filtrado lo hace la propia librería
            verbose=False,
        )
        t1 = time.perf_counter()

        detecciones = []
        cajas = salida[0].boxes
        if cajas is not None and len(cajas):
            xyxy = cajas.xyxy.cpu().numpy()
            confs = cajas.conf.cpu().numpy()
            clases = cajas.cls.cpu().numpy().astype(int)
            for (x1, y1, x2, y2), c, k in zip(xyxy, confs, clases):
                nombre = self.alias.get(self.nombres[k], self.nombres[k])
                if c < self.conf_clase.get(nombre, self.conf):
                    continue
                detecciones.append(
                    _a_deteccion(nombre, c, x1, y1, x2, y2, ancho, alto)
                )
        t2 = time.perf_counter()

        tiempos = {
            "inferencia_ms": (t1 - t0) * 1000,
            "postproceso_ms": (t2 - t1) * 1000,
        }
        return detecciones, tiempos


# ==============================================================================
# 2. Confirmación temporal (PLAN.md §5 D6)
# ==============================================================================
class Confirmador:
    """Exige N frames consecutivos para confirmar y M para dar por perdida.

    Sin esto, un falso positivo aislado dispara un cambio de estado y el robot
    oscila entre comportamientos.
    """

    def __init__(self, n_confirmar=None, m_perder=None):
        self.n = n_confirmar or config.N_CONFIRMAR
        self.m = m_perder or config.M_PERDER
        self._presentes = {}   # clase → frames consecutivos vista
        self._ausentes = {}    # clase → frames consecutivos sin ver
        self._confirmadas = set()

    def actualizar(self, clases_vistas):
        """Recibe el conjunto de clases del frame actual, devuelve las confirmadas."""
        vistas = set(clases_vistas)
        for clase in set(self._presentes) | set(self._ausentes) | vistas:
            if clase in vistas:
                self._presentes[clase] = self._presentes.get(clase, 0) + 1
                self._ausentes[clase] = 0
                if self._presentes[clase] >= self.n:
                    self._confirmadas.add(clase)
            else:
                self._ausentes[clase] = self._ausentes.get(clase, 0) + 1
                self._presentes[clase] = 0
                if self._ausentes[clase] >= self.m:
                    self._confirmadas.discard(clase)
        return set(self._confirmadas)

    def reiniciar(self):
        self._presentes.clear()
        self._ausentes.clear()
        self._confirmadas.clear()


def mejor(detecciones, clase):
    """La detección más confiable de una clase, o None."""
    candidatas = [d for d in detecciones if d.clase == clase]
    return max(candidatas, key=lambda d: d.conf) if candidatas else None


# ==============================================================================
# 3. Cámara
# ==============================================================================
class Camara:
    """Abstrae las dos cámaras posibles del Pi 5.

    - CSI  → Picamera2 (viene por apt como python3-picamera2, NO por pip;
             el venv tiene que crearse con --system-site-packages).
    - USB  → OpenCV sobre V4L2.

    Con fuente="auto" intenta CSI y cae a USB. Los dos backends entregan el
    frame en orden BGR, que es lo que esperan OpenCV y Ultralytics.
    """

    def __init__(self, ancho=None, alto=None, fuente=None, indice=None):
        self.ancho = ancho or config.ANCHO_CAPTURA
        self.alto = alto or config.ALTO_CAPTURA
        self.indice = indice if indice is not None else config.INDICE_CAMARA
        fuente = (fuente or config.FUENTE_CAMARA).lower()

        self.backend = None
        self.motivo_csi = None   # por qué no abrió la CSI, para no adivinar
        self._cam = None
        self._cap = None

        if fuente in ("auto", "csi"):
            if self._abrir_csi() is False and fuente == "csi":
                raise RuntimeError(
                    f"No se pudo abrir la cámara CSI (Picamera2): {self.motivo_csi}")
        if self.backend is None and fuente in ("auto", "usb"):
            if self._abrir_usb() is False:
                raise RuntimeError(
                    f"No se pudo abrir la cámara USB en /dev/video{self.indice}. "
                    "Probá `v4l2-ctl --list-devices` para ver qué hay conectado."
                )
        if self.backend is None:
            raise RuntimeError("No se encontró ninguna cámara (ni CSI ni USB).")

    def _abrir_csi(self):
        try:
            from picamera2 import Picamera2
        except ImportError as e:
            self.motivo_csi = f"no se pudo importar picamera2 ({e})"
            return False
        try:
            cam = Picamera2()
            # "RGB888" en Picamera2 entrega los canales en orden BGR en memoria,
            # que es justo lo que quieren OpenCV y Ultralytics. No invertir.
            cfg = cam.create_preview_configuration(
                main={"size": (self.ancho, self.alto), "format": "RGB888"}
            )
            cam.configure(cfg)
            cam.start()
            time.sleep(0.5)   # el AE/AWB necesita unos frames para estabilizar
            self._cam = cam
            self.backend = "csi (Picamera2)"
            return True
        except Exception as e:
            # Sin cámara, Picamera2() tira IndexError; con un sensor que
            # libcamera no reconoce, otra cosa. Las dos terminan acá.
            self.motivo_csi = f"{type(e).__name__}: {e}"
            return False

    def _abrir_usb(self):
        import os

        import cv2

        cap = None
        if os.name != "nt":                       # V4L2 sólo existe en Linux
            cap = cv2.VideoCapture(self.indice, cv2.CAP_V4L2)
        if cap is None or not cap.isOpened():
            cap = cv2.VideoCapture(self.indice)   # backend por defecto
        if not cap.isOpened():
            return False
        # El formato va antes que el tamaño: en V4L2 cada formato tiene su propia
        # lista de resoluciones. MJPG es el que tolera el ruido de los motores
        # (config.FORMATO_CAMARA, 2026-09-30).
        if config.FORMATO_CAMARA:
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*config.FORMATO_CAMARA))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.ancho)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.alto)
        cap.set(cv2.CAP_PROP_FPS, config.FPS_CAMARA_SOLICITADO)
        # Buffer chico: sin esto se acumulan frames viejos y el lazo de control
        # trabaja sobre una imagen de hace medio segundo.
        try:
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass
        self._cap = cap
        dispositivo = (f"cámara {self.indice}" if os.name == "nt"
                       else f"/dev/video{self.indice}")
        self.backend = f"usb (OpenCV, {dispositivo})"
        return True

    def leer(self):
        """Un frame BGR, o None si la captura falló."""
        if self._cam is not None:
            return self._cam.capture_array()
        ok, frame = self._cap.read()
        return frame if ok else None

    def resolucion_real(self):
        """Lo que la cámara entrega de verdad, que no siempre es lo pedido."""
        frame = self.leer()
        if frame is None:
            return None
        return frame.shape[1], frame.shape[0]

    def cerrar(self):
        if self._cam is not None:
            self._cam.stop()
            self._cam.close()
        if self._cap is not None:
            self._cap.release()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.cerrar()


# ==============================================================================
# 4. Salud de la imagen
# ==============================================================================
def franjas(frame):
    """Fracción de las filas del frame que son una franja gris uniforme.

    Con MJPG, cuando se pierden paquetes USB en el camino, libjpeg rellena el
    tramo que falta con gris medio hasta el próximo marcador de reinicio: el
    frame llega entero pero con franjas horizontales, y YOLO no reconoce nada
    detrás de ellas. El 2026-10-01 esto pasó con el robot QUIETO y los motores
    desenchufados, de a ratos: 69 de 71 frames dañados en una medición y 0 de
    606 un rato después (media/2026-10-01_imagen_rota/).

    Se mide en cada ciclo y va al CSV de la corrida, para que una corrida que
    "no vio el oso" diga por sí sola si la cámara estaba ciega. 0.0 es un frame
    sano; por encima de ~0.10 la detección ya no es confiable.

    ⚠️ Una fila de la escena que sea gris medio y lisa de punta a punta (una
    pared gris ocupando todo el ancho) cuenta como franja. Es raro, pero el
    número mide "filas grises uniformes", no "paquetes perdidos".
    """
    # 1 de cada 16 columnas: da el mismo número que con todas y cuesta 1,7 ms
    # en el Pi (con 1 de cada 4 eran 6,6 ms, un FPS entero del lazo).
    f = frame[:, ::16].astype(np.int16)
    gris = f.sum(axis=2) / 3.0
    croma = (f.max(axis=2) - f.min(axis=2)).mean(axis=1)
    uniforme = (gris.std(axis=1) < 4) & (np.abs(gris.mean(axis=1) - 128) < 12) & (croma < 6)
    return float(uniforme.mean())


# ==============================================================================
# 5. Dibujo (sólo para depurar y para el video de la demo)
# ==============================================================================
_COLOR = {
    config.CLASE_OBJETIVO: (214, 120, 42),   # BGR — azul: objetivo, APROXIMAR
    config.CLASE_AMENAZA: (52, 104, 235),    # BGR — naranja: amenaza, HUIR
}


def dibujar(frame, detecciones, texto=None):
    """Anota el frame in place con las cajas y los números del control."""
    import cv2

    alto, ancho = frame.shape[:2]
    cv2.line(frame, (ancho // 2, 0), (ancho // 2, alto), (150, 150, 150), 1)

    for d in detecciones:
        color = _COLOR.get(d.clase, (150, 150, 150))
        cv2.rectangle(frame, (d.x, d.y), (d.x + d.w, d.y + d.h), color, 2)
        etiqueta = f"{d.clase} {d.conf:.2f} | ex={d.error_x:+.2f} ar={d.area_ratio:.3f}"
        (tw, th), _ = cv2.getTextSize(etiqueta, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(frame, (d.x, d.y - th - 6), (d.x + tw + 4, d.y), color, -1)
        cv2.putText(frame, etiqueta, (d.x + 2, d.y - 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)

    if texto:
        cv2.putText(frame, texto, (8, 22), cv2.FONT_HERSHEY_SIMPLEX,
                    0.6, (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(frame, texto, (8, 22), cv2.FONT_HERSHEY_SIMPLEX,
                    0.6, (255, 255, 255), 1, cv2.LINE_AA)
    return frame
