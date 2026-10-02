"""
TPF Robótica IA — Enlace serie con el ESP32 (PLAN.md §8)
==============================================================================
Traduce entre la intención del Pi y el protocolo ASCII del firmware. Es la
única pieza del Pi que sabe que existe un cable.

    Pi  → ESP32:   M,<v_lin>,<v_ang>     enteros en [-100, 100]
                   B,<patron>            0=off, 1=hallazgo, 2=alarma
    ESP32 → Pi:    D,<dist_cm>,<enc_izq>,<enc_der>    a ~20 Hz
                   #...                  diagnóstico para humanos, se descarta

Dos cosas que este módulo resuelve y que no son obvias:

1. **El latido.** El ESP32 frena si no recibe un `M` en 500 ms (watchdog de
   §8). El lazo de visión corre a ~5 FPS, o sea 200 ms por vuelta en el mejor
   caso: cualquier frame lento haría frenar el robot a mitad de maniobra. Un
   hilo aparte repite el último comando a 10 Hz y desacopla las dos cadencias.

2. **La vigencia.** Repetir el último comando para siempre anularía justamente
   el watchdog que lo protege: si el lazo principal se cuelga, el latido
   seguiría diciendo "andá". Por eso el latido sólo repite comandos frescos
   (`VIGENCIA_COMANDO_S`); pasado ese tiempo manda M,0,0 por su cuenta. El
   watchdog del ESP32 queda como última red, no como primera.

Uso típico:

    with Enlace() as esp:
        esp.mover(40, -15)          # avanzar girando a la izquierda
        print(esp.estado.dist_cm)   # None si el ultrasónico no tiene lectura
        esp.buzzer(config.BUZZER_HALLAZGO)
    # al salir del with frena, siempre, incluso si hubo excepción

Sin ESP32 conectado (verificación en PC):

    with Enlace(simular=True) as esp:
        ...
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass

import config


# ==============================================================================
# 1. Lo que el ESP32 informa
# ==============================================================================
@dataclass(frozen=True)
class EstadoESP32:
    """Última línea D recibida, ya interpretada.

    `dist_cm` es None cuando el ESP32 mandó -1, que en §8 significa "sin
    lectura válida" — sensor desconectado, o un eco que no volvió. NO es cero:
    tratarlo como distancia cero haría frenar el robot de arranque cada vez
    que al sensor se le suelta un cable (pasó el 2026-10-02).

    Con el PING))) "no hay nada adelante" NO llega como -1 sino como un número
    grande (~370 cm): el sensor devuelve su pulso más largo.
    """

    dist_cm: float          # None si no hay lectura (ver arriba)
    enc_izq: int
    enc_der: int
    recibido_en: float      # time.monotonic() de la recepción

    @property
    def hay_distancia(self):
        return self.dist_cm is not None

    def obstaculo(self, umbral_cm=None):
        """¿Hay algo más cerca que el umbral? "No sé" cuenta como "no"."""
        umbral = config.DIST_PARADA_CM if umbral_cm is None else umbral_cm
        return self.hay_distancia and self.dist_cm <= umbral

    def vencido(self, ahora=None, max_edad_s=1.0):
        ahora = time.monotonic() if ahora is None else ahora
        return (ahora - self.recibido_en) > max_edad_s


ESTADO_VACIO = EstadoESP32(dist_cm=None, enc_izq=0, enc_der=0, recibido_en=0.0)


def parsear_linea(linea):
    """Interpreta una línea del ESP32. Devuelve EstadoESP32 o None.

    None significa "esta línea no es telemetría": diagnóstico (#), basura de
    arranque, o un D mal formado. El lazo no se puede caer por una línea rota,
    así que acá nada levanta excepción.
    """
    linea = linea.strip()
    if not linea or linea.startswith("#"):
        return None

    partes = linea.split(",")
    if len(partes) != 4 or partes[0] != "D":
        return None

    try:
        dist = float(partes[1])
        enc_izq = int(partes[2])
        enc_der = int(partes[3])
    except ValueError:
        return None

    return EstadoESP32(
        dist_cm=None if dist == config.DIST_INVALIDA else dist,
        enc_izq=enc_izq,
        enc_der=enc_der,
        recibido_en=time.monotonic(),
    )


# ==============================================================================
# 2. Puerto
# ==============================================================================
def detectar_puerto():
    """Busca el ESP32 entre los puertos serie. Devuelve la ruta o None.

    `config.PUERTO_SERIE` dice ttyUSB0 con un cuadrito pendiente al lado:
    depende del chip USB del módulo. Los ESP32 con CP210x o CH340 aparecen
    como ttyUSB*, los que tienen USB nativo (S2/S3/C3) como ttyACM*. Se prueba
    por descripción y, si no, por nombre de dispositivo.
    """
    try:
        from serial.tools import list_ports
    except ImportError:
        return None

    puertos = list(list_ports.comports())
    marcas = ("cp210", "ch340", "ch910", "silicon labs", "wch", "esp32", "usb serial")

    for p in puertos:
        texto = " ".join(str(x) for x in (p.description, p.manufacturer, p.product)).lower()
        if any(m in texto for m in marcas):
            return p.device

    for p in puertos:
        if any(t in p.device for t in ("ttyUSB", "ttyACM", "COM")):
            return p.device

    return None


class _PuertoSimulado:
    """Reemplazo de un serial.Serial para verificar el lazo sin ESP32.

    Responde D con distancia inválida, que es exactamente lo que manda el
    firmware con el ultrasónico desconectado: el caso simulado es el robot
    sin sensor. Guarda lo enviado en `escrito` para poder revisar qué mandó
    la máquina de estados.
    """

    def __init__(self):
        self.escrito = []
        self.abierto = True
        self._ultimo_d = 0.0

    def write(self, datos):
        self.escrito.append(datos.decode("ascii", "replace"))
        return len(datos)

    def readline(self):
        ahora = time.monotonic()
        if ahora - self._ultimo_d < 0.05:     # ~20 Hz, como el firmware
            time.sleep(0.01)
            return b""
        self._ultimo_d = ahora
        return b"D,-1,0,0\n"

    def flush(self):
        pass

    def close(self):
        self.abierto = False

    @property
    def is_open(self):
        return self.abierto


# ==============================================================================
# 3. El enlace
# ==============================================================================
class Enlace:
    """Enlace con el ESP32, con hilo lector y latido de watchdog.

    Los métodos públicos (`mover`, `parar`, `buzzer`, `estado`) son seguros
    desde cualquier hilo.
    """

    def __init__(self, puerto=None, baudios=None, simular=False, vigencia_s=None):
        self.simulado = simular
        self.baudios = baudios or config.BAUDIOS
        self.vigencia_s = config.VIGENCIA_COMANDO_S if vigencia_s is None else vigencia_s

        self._lock = threading.Lock()
        self._lock_escritura = threading.Lock()
        self._estado = ESTADO_VACIO
        self._comando = (0, 0)          # (v_lin, v_ang) vigente
        self._comando_en = 0.0          # cuándo lo pidió la máquina de estados
        self._corriendo = False
        self._hilos = []
        self._lineas_descartadas = 0

        if simular:
            self.puerto = "(simulado)"
            self._ser = _PuertoSimulado()
        else:
            self.puerto = puerto or config.PUERTO_SERIE
            self._ser = self._abrir()

        self._arrancar_hilos()

    # -- apertura ---------------------------------------------------------
    def _abrir(self):
        # import local: falla en una PC sin pyserial y sólo hace falta acá
        import serial

        try:
            ser = serial.Serial(self.puerto, self.baudios, timeout=config.TIMEOUT_SERIE_S)
        except Exception:
            detectado = detectar_puerto()
            if not detectado or detectado == self.puerto:
                raise
            ser = serial.Serial(detectado, self.baudios, timeout=config.TIMEOUT_SERIE_S)
            self.puerto = detectado

        # El ESP32 se reinicia cuando se abre el puerto (DTR/RTS): los primeros
        # ~2 s son el boot log del bootloader, no protocolo. Sin esta espera la
        # primera orden se pierde y el robot arranca tarde.
        time.sleep(2.0)
        try:
            ser.reset_input_buffer()
        except Exception:
            pass
        return ser

    def _arrancar_hilos(self):
        self._corriendo = True
        for objetivo, nombre in ((self._bucle_lector, "esp32-lector"),
                                 (self._bucle_latido, "esp32-latido")):
            h = threading.Thread(target=objetivo, name=nombre, daemon=True)
            h.start()
            self._hilos.append(h)

    # -- hilos ------------------------------------------------------------
    def _bucle_lector(self):
        while self._corriendo:
            try:
                cruda = self._ser.readline()
            except Exception:
                break
            if not cruda:
                continue

            estado = parsear_linea(cruda.decode("ascii", "replace"))
            with self._lock:
                if estado is None:
                    self._lineas_descartadas += 1
                else:
                    self._estado = estado

    def _bucle_latido(self):
        """Repite el comando vigente a 10 Hz, mientras siga fresco."""
        while self._corriendo:
            with self._lock:
                v_lin, v_ang = self._comando
                fresco = (time.monotonic() - self._comando_en) <= self.vigencia_s
                if not fresco:
                    self._comando = (0, 0)
                    v_lin, v_ang = 0, 0

            self._escribir("M,%d,%d\n" % (v_lin, v_ang))
            time.sleep(config.PERIODO_COMANDO_S)

    def _escribir(self, texto):
        # Escriben dos hilos (el latido y el lazo principal): sin el candado dos
        # líneas podrían salir entremezcladas y el ESP32 descartaría las dos.
        try:
            with self._lock_escritura:
                self._ser.write(texto.encode("ascii"))
                self._ser.flush()
            return True
        except Exception:
            return False

    # -- API --------------------------------------------------------------
    def mover(self, v_lin, v_ang):
        """Fija el comando vigente. El latido lo sostiene hasta el próximo.

        Si el comando es el mismo que ya estaba, no escribe en el puerto: sólo
        renueva lo que el latido repite, y la cadencia del cable no depende de
        la del lazo de visión.

        Si CAMBIA, lo manda en el acto. Esperar al latido agregaba entre 0 y
        100 ms a cada cambio, al azar: no importa para avanzar, pero el barrido
        a pasos de BUSCAR son pulsos de ~0,25 s, y ±0,1 s en cada punta hacía
        que un paso girara la mitad o el doble que el anterior (2026-10-01).
        También es lo que tarda en llegar el freno de ENCONTRADO.
        """
        v_lin = _acotar_100(v_lin)
        v_ang = _acotar_100(v_ang)
        with self._lock:
            cambio = (v_lin, v_ang) != self._comando
            self._comando = (v_lin, v_ang)
            self._comando_en = time.monotonic()
        if cambio:
            self._escribir("M,%d,%d\n" % (v_lin, v_ang))
        return v_lin, v_ang

    def parar(self):
        """Frena. Manda M,0,0 en el acto, sin esperar al latido.

        Tiene que ser exactamente 0: con el mapa calibrado cualquier valor
        distinto de cero da como mínimo 0,091 m/s (HARDWARE.md §0.5).
        """
        with self._lock:
            self._comando = (0, 0)
            self._comando_en = time.monotonic()
        return self._escribir("M,0,0\n")

    def buzzer(self, patron):
        """Patrón de buzzer. Se manda en el acto: es un evento, no un estado."""
        return self._escribir("B,%d\n" % int(patron))

    @property
    def estado(self):
        with self._lock:
            return self._estado

    @property
    def lineas_descartadas(self):
        with self._lock:
            return self._lineas_descartadas

    def describir(self):
        return "Enlace(%s @ %d baudios%s)" % (
            self.puerto, self.baudios, ", SIMULADO" if self.simulado else "")

    # -- cierre -----------------------------------------------------------
    def cerrar(self):
        """Frena y suelta el puerto. Idempotente."""
        if not self._corriendo:
            return
        self._corriendo = False
        self.parar()
        time.sleep(0.05)            # que el M,0,0 salga antes de cerrar
        for h in self._hilos:
            h.join(timeout=0.5)
        try:
            self._ser.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *_):
        # Frenar en el camino de salida, pase lo que pase. Un robot con los
        # motores a fondo y el proceso muerto sigue andando hasta chocar.
        self.cerrar()
        return False


def _acotar_100(v):
    return max(-100, min(100, int(round(v))))
