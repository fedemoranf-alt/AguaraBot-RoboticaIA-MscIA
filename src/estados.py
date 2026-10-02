"""
TPF Robótica IA — Máquina de estados (PLAN.md §6)
==============================================================================
El comportamiento del robot: BUSCAR, APROXIMAR, HUIR, ENCONTRADO.

Igual que `control.py`, esto no toca hardware. Recibe una percepción ya
digerida (qué clases están confirmadas, dónde están, qué dice el ultrasónico)
y el instante actual, y devuelve un `Comando`. Todo el tiempo se pasa por
argumento en vez de leerlo de `time`, así que la máquina se puede correr a
velocidad de simulación y verificar entera sin robot ni cámara.

    maquina = Maquina()
    cmd = maquina.paso(confirmadas, detecciones, estado_esp, ahora)
    esp.mover(cmd.v_lin, cmd.v_ang)
    if cmd.buzzer is not None:
        esp.buzzer(cmd.buzzer)

**Las tres reglas que gobiernan todo:**

1. **HUIR tiene prioridad incondicional** (§6.3). Si la amenaza está
   confirmada, se huye, aunque el oso esté a la vista y aunque falte poco para
   llegar.
2. **HUIR no se reevalúa a mitad de camino.** Las fases 2 y 3 giran y avanzan a
   ciegas: la cámara pierde de vista la mochila y eso es parte del diseño. Si
   se reevaluara, ver la mochila de nuevo reiniciaría la maniobra para siempre.
3. **El buzzer es un evento, no un estado.** Sale sólo en la transición que lo
   provoca; el resto de los ciclos `cmd.buzzer` es None. Sin esto el Pi
   mandaría una orden `B` por frame, cinco veces por segundo.
4. **Después de huir hay un período sordo a la amenaza.** No estaba en §6 y lo
   encontró `prueba_estados.py`: sin él las huidas se reencadenan solas. El
   culpable no es ver la mochila de nuevo, es el Confirmador — al terminar la
   fase 3 el robot ya giró 180° y la mochila no está en cámara, pero `M_PERDER`
   = 5 frames la mantiene confirmada un rato más. La máquina vuelve a BUSCAR,
   lee esa confirmación vencida y dispara una huida idéntica. El refractario
   dura más de lo que el confirmador tarda en soltarla.

   Es el mismo patrón que las estimaciones caídas del bloque de tracción: un
   número correcto (M=5, que existe para no perder el objetivo por un frame
   malo) usado fuera del contexto donde vale (después de una maniobra que
   cambió deliberadamente lo que la cámara mira).
"""

from __future__ import annotations

import random
from dataclasses import dataclass

import config
import control
from vision import mejor


BUSCAR = "BUSCAR"
APROXIMAR = "APROXIMAR"
HUIR = "HUIR"
ENCONTRADO = "ENCONTRADO"


@dataclass(frozen=True)
class Comando:
    """Lo que la máquina le pide al ESP32 en un ciclo."""

    v_lin: int
    v_ang: int
    buzzer: int         # None salvo en la transición que lo dispara
    estado: str
    motivo: str         # por qué este comando — para el log y la demo

    def __str__(self):
        b = "" if self.buzzer is None else "  buzzer=%d" % self.buzzer
        return "%-11s v_lin=%+4d v_ang=%+4d%s  (%s)" % (
            self.estado, self.v_lin, self.v_ang, b, self.motivo)


PARADO = Comando(0, 0, None, ENCONTRADO, "sin novedad")


class Maquina:
    """La máquina de estados de §6. Un objeto, un robot."""

    def __init__(self, estado_inicial=BUSCAR, azar=None):
        self.estado = estado_inicial
        # El único azar de la máquina: el sentido del barrido después de huir
        # (config.BUSCAR_SENTIDO_AZAR_TRAS_HUIR). Se puede pasar un
        # random.Random con semilla para que una prueba sea repetible.
        self._azar = azar if azar is not None else random.Random()
        # Cuándo se entró al estado actual. None hasta el primer paso(): con 0.0
        # y el reloj monotónico de main.py, la fase inicial de BUSCAR salía al
        # azar y el robot podía arrancar con el pulso de avance (2026-09-30).
        self.entrado_en = None
        self.fase_huir = 0          # 1 retroceso, 2 giro, 3 avance (sólo informativo)
        self.lado_amenaza = 1.0     # signo de error_x de la mochila al entrar a HUIR
        self.huida_termino_en = float("-inf")   # para el refractario (regla 4)
        # Hacia dónde barre BUSCAR: +1 derecha, -1 izquierda. Cambia cuando se
        # pierde el objetivo: se lo busca por el lado donde se lo vio por última
        # vez. En el piso (2026-10-01) el oso se fue por el borde izquierdo a
        # 55 cm, y el barrido —siempre a la derecha— tardó 23 s y casi una
        # vuelta entera en volver a encontrar algo que tenía a 20° a la izquierda.
        # Y después de una huida se sortea (ver _huir).
        self.sentido_barrido = 1
        self._ultimo_ex_objetivo = None
        self._buzzer_pendiente = None
        # Última vez que el ultrasónico dio algo adelante (ver _hay_obstaculo):
        # a menos de DIST_OBSTACULO_CM y a menos de DIST_PARADA_CM.
        self._obstaculo_visto_en = float("-inf")
        self._pegado_visto_en = float("-inf")

    # -- utilidades -------------------------------------------------------
    def _ir_a(self, estado, ahora, buzzer=None):
        if estado != self.estado:
            self.estado = estado
            self.entrado_en = ahora
            if estado == HUIR:
                self.fase_huir = 1
            self._buzzer_pendiente = buzzer

    def _tomar_buzzer(self):
        b, self._buzzer_pendiente = self._buzzer_pendiente, None
        return b

    def _cmd(self, v_lin, v_ang, motivo):
        return Comando(int(v_lin), int(v_ang), self._tomar_buzzer(), self.estado, motivo)

    def tiempo_en_estado(self, ahora):
        return ahora - self.entrado_en

    def _en_refractario(self, ahora):
        """¿Está todavía sorda a la amenaza tras completar una huida?

        Regla 4: al terminar la fase 3 el robot ya giró 180° y la mochila no
        está en cámara, pero el Confirmador la sostiene M_PERDER frames más.
        Sin esta ventana, esa inercia dispara una segunda huida idéntica —una
        amenaza que ya nadie está viendo— y el robot queda huyendo en bucle.
        """
        return (ahora - self.huida_termino_en) < config.HUIR_REFRACTARIO_S

    def _hay_obstaculo(self, ahora, pegado=False):
        """¿Hay algo adelante? Con retención: una lectura libre suelta no alcanza.

        Girando frente a una pared el eco se pierde de a ratos (la pared de
        costado refleja para otro lado) y el sensor da un "libre" entre dos
        "pegado". Creerle a esa lectura es avanzar un ciclo contra la pared:
        en corrida_20261002_103658 leyó 16 cm, 150, 11 — y con el 150 avanzó.

        Dos umbrales (config): para esquivar, DIST_OBSTACULO_CM; con
        `pegado`, el de llegada (DIST_PARADA_CM), que es el que usa APROXIMAR
        — ahí al objetivo hay que poder acercarse.
        """
        visto_en = self._pegado_visto_en if pegado else self._obstaculo_visto_en
        return (ahora - visto_en) < config.SONAR_RETENCION_S

    @staticmethod
    def _dist_txt(estado_esp):
        """La distancia para el motivo; con retención puede no haber lectura."""
        return "%.0f cm" % estado_esp.dist_cm if estado_esp.hay_distancia else "sin eco"

    # -- el ciclo ---------------------------------------------------------
    def paso(self, confirmadas, detecciones, estado_esp, ahora):
        """Un ciclo de decisión. Devuelve el `Comando` a ejecutar.

        `confirmadas` es el set que devuelve `vision.Confirmador`: la
        confirmación temporal N=3 / M=5 ya está aplicada, así que acá una clase
        presente significa "está de verdad", no "apareció en un frame".
        """
        if self.entrado_en is None:
            self.entrado_en = ahora
        if estado_esp.obstaculo(config.DIST_OBSTACULO_CM):
            self._obstaculo_visto_en = ahora
        if estado_esp.obstaculo():
            self._pegado_visto_en = ahora
        amenaza = config.CLASE_AMENAZA in confirmadas
        objetivo = config.CLASE_OBJETIVO in confirmadas

        # De qué lado está el objetivo, mientras se lo vea: es por donde se lo
        # va a buscar si se pierde (ver sentido_barrido).
        visto = mejor(detecciones, config.CLASE_OBJETIVO)
        if visto is not None:
            self._ultimo_ex_objetivo = visto.error_x

        # Regla 1: la amenaza interrumpe cualquier cosa, salvo una huida en
        # curso (regla 2) o una recién terminada (regla 4).
        if amenaza and self.estado != HUIR and not self._en_refractario(ahora):
            det = mejor(detecciones, config.CLASE_AMENAZA)
            # Si la mochila se confirmó pero no está en ESTE frame, el lado no
            # se puede leer: se conserva el último conocido.
            if det is not None:
                self.lado_amenaza = 1.0 if det.error_x >= 0 else -1.0
            self._ir_a(HUIR, ahora, buzzer=config.BUZZER_ALARMA)
            return self._huir(estado_esp, ahora)

        if self.estado == BUSCAR:
            return self._buscar(objetivo, detecciones, estado_esp, ahora)
        if self.estado == APROXIMAR:
            return self._aproximar(objetivo, detecciones, estado_esp, ahora)
        if self.estado == HUIR:
            return self._huir(estado_esp, ahora)
        return self._encontrado()

    # -- §6.1 BUSCAR ------------------------------------------------------
    def _buscar(self, objetivo, detecciones, estado_esp, ahora):
        """Rota en el lugar, con pulsos de avance cada tanto.

        La nota de §6.1: rotar siempre en el mismo punto barre la misma escena
        para siempre. Si el oso está fuera del alcance visual desde acá, no
        aparece por más que se siga girando. El pulso de avance cambia el punto
        de vista.

        ⚠️ Ojo con la asimetría de los motores: BUSCAR rota a ciegas, sin la
        cámara cerrando el lazo, así que es —junto con la fase 2 de HUIR— donde
        la diferencia entre ruedas más se nota. Ver HARDWARE.md §0.5.
        """
        if objetivo:
            self._ir_a(APROXIMAR, ahora)
            return self._cmd(0, 0, "objetivo confirmado, cambio a APROXIMAR")

        # Visto pero todavía sin confirmar: se deja de girar para que los frames
        # que lo confirman salgan quietos (config.BUSCAR_FRENAR_AL_VER).
        if (config.BUSCAR_FRENAR_AL_VER
                and mejor(detecciones, config.CLASE_OBJETIVO) is not None):
            return self._cmd(0, 0, "posible objetivo, freno a confirmar")

        # Lo mismo con la amenaza. Al principio se dejó afuera a propósito ("una
        # mochila sin confirmar no frena el barrido"), y en el piso costó la
        # primera prueba de HUIR (2026-10-01): el robot arrancó con la mochila
        # enfrente, la vio en los dos primeros frames, el barrido empezó a girar
        # igual, el tercer frame salió movido y no llegó a confirmarla nunca.
        # Durante el refractario no: ahí la amenaza se ignora a propósito (regla 4).
        amenaza_vista = mejor(detecciones, config.CLASE_AMENAZA)
        if amenaza_vista is not None:
            if self._en_refractario(ahora):
                # No dispara nada, pero dice hacia dónde NO barrer. En el piso
                # (corrida_20261002_135039) cada huida terminaba con la mochila
                # otra vez a la vista, a la derecha; el barrido salía hacia la
                # derecha, la centraba, y apenas vencía el período sordo huía
                # de nuevo: seis huidas en un minuto. Barriendo hacia el otro
                # lado, en un paso la mochila sale del cuadro.
                self.sentido_barrido = -1 if amenaza_vista.error_x >= 0 else 1
            elif config.BUSCAR_FRENAR_AL_VER:
                return self._cmd(0, 0, "posible amenaza, freno a confirmar")

        ciclo = config.BUSCAR_GIRO_S + config.BUSCAR_AVANCE_S
        t = self.tiempo_en_estado(ahora) % ciclo

        if t < config.BUSCAR_GIRO_S:
            # Barrido a pasos: girando de corrido la imagen sale movida y YOLO
            # no ve nada (medido en el piso, 2026-09-30). Se mira quieto y se
            # gira un tramo; ver config.BUSCAR_PASO_*.
            #
            # Primero mirar, después girar (2026-10-01): con el orden inverso,
            # lo primero que hacía el robot al entrar a BUSCAR era apartar la
            # vista de lo que tenía enfrente, antes de haberlo mirado.
            if config.BUSCAR_PASO_MIRAR_S > 0:
                paso = config.BUSCAR_PASO_GIRO_S + config.BUSCAR_PASO_MIRAR_S
                if t % paso < config.BUSCAR_PASO_MIRAR_S:
                    return self._cmd(0, 0, "mirando")
            return self._cmd(0, config.V_ANG_BUSCAR * self.sentido_barrido, "barriendo")

        # El pulso de avance es el único tramo de BUSCAR que avanza, y lo hace
        # sin objetivo a la vista: sin el ultrasónico era ir contra lo que
        # hubiera. Con algo adelante no se avanza; se gira lo que dura el pulso,
        # así el próximo sale para otro lado.
        if self._hay_obstaculo(ahora):
            return self._cmd(0, config.V_ANG_BUSCAR * self.sentido_barrido,
                             "reubicando: obstáculo (%s), giro" % self._dist_txt(estado_esp))
        return self._cmd(config.V_LIN_BUSCAR, 0, "reubicando")

    # -- §6.2 APROXIMAR ---------------------------------------------------
    def _aproximar(self, objetivo, detecciones, estado_esp, ahora):
        if not objetivo:
            if self._ultimo_ex_objetivo is not None:
                self.sentido_barrido = -1 if self._ultimo_ex_objetivo < 0 else 1
            self._ir_a(BUSCAR, ahora)
            return self._cmd(0, 0, "objetivo perdido, vuelvo a BUSCAR")

        det = mejor(detecciones, config.CLASE_OBJETIVO)
        if det is None:
            # Confirmado pero ausente de este frame: el Confirmador todavía no
            # lo dio por perdido. Mantener el rumbo sería andar a ciegas, así
            # que se frena y se espera al próximo frame.
            return self._cmd(0, 0, "confirmado pero sin caja en este frame")

        llego_por_area = det.area_ratio >= config.AREA_OBJETIVO
        llego_por_sonar = estado_esp.obstaculo() and self._el_obstaculo_es_el_objetivo(det)

        if llego_por_area or llego_por_sonar:
            self._ir_a(ENCONTRADO, ahora, buzzer=config.BUZZER_HALLAZGO)
            return self._cmd(0, 0, "llegué (%s)" % ("área" if llego_por_area else "sonar"))

        # §6.2: obstáculo cercano que NO es el objetivo → desviar.
        if self._hay_obstaculo(ahora, pegado=True):
            return self._cmd(0, config.V_ANG_MAX * self._lado_libre(det),
                             "obstáculo ajeno (%s), desvío" % self._dist_txt(estado_esp))

        v_lin, v_ang = control.perseguir(det)
        return self._cmd(v_lin, v_ang,
                         "ex=%+.2f ar=%.3f" % (det.error_x, det.area_ratio))

    def _el_obstaculo_es_el_objetivo(self, det):
        """¿Lo que ve el ultrasónico es el oso, o es otra cosa en el camino?

        El sensor mira al frente y no distingue qué tiene delante. Heurística:
        si el objetivo está razonablemente centrado y ya ocupa buena parte de
        la imagen, lo que hay enfrente es él. Si el oso todavía se ve chico o
        está muy al costado, lo que el sonar detecta es otra cosa.

        Los dos umbrales salen de la geometría del cono del sensor y del campo
        visual; el de centrado se ajustó en el piso (config.SONAR_CENTRADO).
        """
        return (abs(det.error_x) < config.SONAR_CENTRADO
                and det.area_ratio >= config.AREA_OBJETIVO * config.SONAR_FRACCION_AREA)

    @staticmethod
    def _lado_libre(det):
        """Hacia dónde desviar: al lado contrario del objetivo, para no perderlo
        de vista más de lo necesario y para no pisarlo."""
        return -1 if det.error_x >= 0 else 1

    # -- §6.3 HUIR --------------------------------------------------------
    def _huir(self, estado_esp, ahora):
        """Tres fases secuenciales. No se reevalúa la amenaza (regla 2).

        Un solo reloj, medido desde la entrada a HUIR, contra umbrales
        acumulados. La alternativa —reiniciar un cronómetro en cada cambio de
        fase— obliga a que el instante del cambio y el ciclo siguiente midan
        contra orígenes distintos, y ahí las fases se pisan.
        """
        t = self.tiempo_en_estado(ahora)
        fin_1 = config.HUIR_RETROCESO_S
        fin_2 = fin_1 + config.HUIR_GIRO_S
        fin_3 = fin_2 + config.HUIR_AVANCE_S

        if t < fin_1:
            self.fase_huir = 1
            # Retrocede girando al lado OPUESTO de donde está la mochila:
            # yendo marcha atrás, eso aleja el frente de la amenaza.
            giro = int(config.HUIR_GIRO_RETROCESO * -self.lado_amenaza)
            return self._cmd(-config.HUIR_V_RETROCESO, giro, "fase 1: retroceso")

        if t < fin_2:
            self.fase_huir = 2
            # Para el MISMO lado que giró en el retroceso. Antes giraba siempre
            # a la derecha, y con la mochila a la derecha la fase 1 gira a la
            # izquierda: la fase 2 empezaba deshaciendo lo que la 1 había
            # girado, volvía a pasar por delante de la mochila y quedaba muy
            # corta de los 180° (medido en el piso, 2026-10-01).
            giro = int(config.V_ANG_MAX * -self.lado_amenaza)
            return self._cmd(0, giro, "fase 2: giro ~180 grados")

        if t < fin_3:
            self.fase_huir = 3
            if self._hay_obstaculo(ahora):
                # §6.3: el ultrasónico sigue activo. Chocar escapando sería
                # cambiar un problema por otro.
                return self._cmd(0, config.V_ANG_MAX, "fase 3: obstáculo, esquivo")
            return self._cmd(config.HUIR_V_AVANCE, 0, "fase 3: avance")

        self.fase_huir = 0
        self.huida_termino_en = ahora       # arranca el refractario (regla 4)
        # El barrido que sigue arranca para un lado al azar. Con el sentido
        # fijo el robot repetía el mismo recorrido: huía, barría para el mismo
        # lado, volvía a dar con lo mismo y huía otra vez igual (2026-10-02).
        if config.BUSCAR_SENTIDO_AZAR_TRAS_HUIR:
            self.sentido_barrido = self._azar.choice((-1, 1))
        self._ir_a(BUSCAR, ahora, buzzer=config.BUZZER_OFF)
        return self._cmd(0, 0, "escape completo, vuelvo a BUSCAR")

    # -- §6.4 ENCONTRADO --------------------------------------------------
    def _encontrado(self):
        return self._cmd(0, 0, "detenido")
