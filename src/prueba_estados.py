"""
TPF Robótica IA — Verificación de la máquina de estados (Día 4)
==============================================================================
Corre la máquina de estados de `estados.py` contra escenarios sintéticos, sin
cámara, sin ESP32 y sin robot. Es el equivalente para el Día 4 de lo que
`bench_vision.py` es para el Día 3: la forma de saber que el comportamiento es
el de PLAN.md §6 antes de que haya ruedas girando.

Se puede hacer porque `estados.py` no toca hardware y recibe el tiempo por
argumento: el reloj se puede adelantar de a saltos y una huida de 5 segundos se
verifica en microsegundos.

    python prueba_estados.py           # todos los escenarios
    python prueba_estados.py -v        # con el detalle ciclo por ciclo

Lo que NO prueba: que los tiempos de las fases de HUIR correspondan a un giro
de 180° reales, ni que V_ANG_BUSCAR alcance para rotar. Eso son constantes ⬜
que sólo se cierran midiendo en piso. Acá se verifica la LÓGICA: el orden de
las fases, las prioridades, y que el buzzer suene una vez y no cinco por
segundo.
"""

from __future__ import annotations

import random
import sys

import config
import estados
from enlace_esp32 import EstadoESP32
from vision import Deteccion


VERBOSO = "-v" in sys.argv

# Un frame llega cada 200 ms: 5 FPS, el objetivo de PLAN.md §10.
DT = 1.0 / config.FPS_OBJETIVO


# ==============================================================================
# Utilidades
# ==============================================================================
def _det(clase, error_x=0.0, area=0.02, conf=0.9):
    """Una Deteccion con los dos números que la ley usa. La caja en píxeles no
    importa acá: la ley de control sólo mira error_x y area_ratio."""
    return Deteccion(clase, conf, 0, 0, 10, 10, error_x, area)


def oso(error_x=0.0, area=0.02):
    return _det(config.CLASE_OBJETIVO, error_x, area)


def mochila(error_x=0.0, area=0.05):
    return _det(config.CLASE_AMENAZA, error_x, area)


def sonar(dist_cm=None):
    return EstadoESP32(dist_cm=dist_cm, enc_izq=0, enc_der=0, recibido_en=0.0)


SIN_SONAR = sonar(None)     # lo que manda el ESP32 con el ultrasónico desconectado


class Escenario:
    """Corre la máquina con un reloj simulado y junta lo que fue pasando."""

    def __init__(self, maquina=None, t0=100.0):
        self.maq = maquina or estados.Maquina()
        self.t = t0
        self.comandos = []

    def avanzar(self, ciclos=1, detecciones=(), estado_esp=SIN_SONAR, dt=DT):
        for _ in range(ciclos):
            confirmadas = {d.clase for d in detecciones}
            cmd = self.maq.paso(confirmadas, list(detecciones), estado_esp, self.t)
            self.comandos.append(cmd)
            if VERBOSO:
                print("      %7.2fs  %s" % (self.t, cmd))
            self.t += dt
        return self.comandos[-1]

    @property
    def estados_vistos(self):
        return [c.estado for c in self.comandos]

    @property
    def buzzers(self):
        return [c.buzzer for c in self.comandos if c.buzzer is not None]

    def motivos_con(self, texto):
        return [c for c in self.comandos if texto in c.motivo]


_fallas = []


def verificar(nombre, condicion, detalle=""):
    marca = "ok  " if condicion else "FALLA"
    print("    [%s] %s%s" % (marca, nombre, ("  -- " + detalle) if detalle and not condicion else ""))
    if not condicion:
        _fallas.append(nombre)


def titulo(t):
    print("\n%s\n%s" % (t, "-" * len(t)))


# ==============================================================================
# 1. BUSCAR (§6.1)
# ==============================================================================
def prueba_buscar():
    titulo("1. BUSCAR — barrido con pulsos de reubicación")
    e = Escenario()
    # Un ciclo completo de barrido + reubicación, muestreado fino: 50 ms es
    # bastante menos que un paso del barrido (config.BUSCAR_PASO_*).
    ciclo = config.BUSCAR_GIRO_S + config.BUSCAR_AVANCE_S
    e.avanzar(ciclos=int(ciclo / 0.05), dt=0.05)

    barriendo = e.motivos_con("barriendo")
    mirando = e.motivos_con("mirando")
    reubicando = e.motivos_con("reubicando")

    verificar("rota en el lugar mientras barre",
              all(c.v_lin == 0 and c.v_ang > 0 for c in barriendo))
    verificar("avanza derecho en el pulso de reubicación",
              all(c.v_lin > 0 and c.v_ang == 0 for c in reubicando))
    verificar("hace las dos cosas, no una sola",
              len(barriendo) > 0 and len(reubicando) > 0,
              "barriendo=%d reubicando=%d" % (len(barriendo), len(reubicando)))
    verificar("barre más tiempo del que se reubica",
              len(barriendo) + len(mirando) > len(reubicando),
              "el barrido tiene que cubrir 360 grados antes de mover el punto de vista")
    verificar("no dispara el buzzer", e.buzzers == [])

    # El barrido a pasos (2026-09-30): girando de corrido la imagen sale
    # movida y YOLO no ve nada, así que se alterna girar y mirar quieto.
    if config.BUSCAR_PASO_MIRAR_S > 0:
        verificar("a pasos: entre giro y giro se queda quieto mirando",
                  len(mirando) > 0 and all(c.v_lin == 0 and c.v_ang == 0 for c in mirando),
                  "mirando=%d" % len(mirando))
        motivos = [c.motivo for c in e.comandos
                   if c.motivo in ("barriendo", "mirando")]
        cambios = sum(1 for a, b in zip(motivos, motivos[1:]) if a != b)
        verificar("a pasos: alterna varias veces en una vuelta, no una sola",
                  cambios >= 6, "cambios=%d" % cambios)
        # Cada mirada tiene que alcanzar para confirmar con la imagen quieta,
        # al FPS medido (11,2), aun perdiendo el primer frame por el frenado.
        frames = config.BUSCAR_PASO_MIRAR_S * 11.2
        verificar("a pasos: cada mirada alcanza para confirmar (N_CONFIRMAR + 1 frames)",
                  frames >= config.N_CONFIRMAR + 1,
                  "%.1f frames por mirada" % frames)


# ==============================================================================
# 2. BUSCAR -> APROXIMAR -> ENCONTRADO (§6.2, §6.4)
# ==============================================================================
def prueba_aproximar():
    titulo("2. APROXIMAR — control proporcional y llegada")
    e = Escenario()
    e.avanzar(3)                                    # buscando
    # Las áreas de esta prueba van EN FRACCIONES de AREA_OBJETIVO, no en
    # valores fijos. Con números absolutos la prueba quedaba atada a la
    # calibración de turno, y se rompió sola el 2026-09-22: al pasar
    # AREA_OBJETIVO de 0,15 a 0,066, un área de 0,08 escrita como "todavía
    # lejos" pasó a significar "ya llegué", la máquina saltaba a ENCONTRADO y
    # fallaban tres verificaciones que no tenían nada que ver con el área.
    A = config.AREA_OBJETIVO
    e.avanzar(1, [oso(error_x=0.5, area=0.3 * A)])  # aparece el oso, lejos

    verificar("el oso confirmado saca de BUSCAR",
              e.maq.estado == estados.APROXIMAR, e.maq.estado)

    # Se acerca: el área crece frame a frame.
    v_lins = []
    for fraccion in (0.3, 0.5, 0.7, 0.85, 0.95):
        cmd = e.avanzar(1, [oso(error_x=0.2, area=fraccion * A)])
        v_lins.append(cmd.v_lin)

    verificar("frena a medida que se acerca",
              all(a >= b for a, b in zip(v_lins, v_lins[1:])), str(v_lins))
    verificar("nunca pide marcha atrás en APROXIMAR", all(v >= 0 for v in v_lins))

    cmd = e.avanzar(1, [oso(error_x=0.6, area=0.5 * A)])
    verificar("gira hacia el objetivo, con el signo de §8", cmd.v_ang > 0,
              "error_x>0 (derecha) tiene que dar v_ang>0")
    cmd = e.avanzar(1, [oso(error_x=-0.6, area=0.5 * A)])
    verificar("y al otro lado también", cmd.v_ang < 0)

    cmd = e.avanzar(1, [oso(error_x=0.02, area=0.5 * A)])
    verificar("zona muerta: casi centrado no corrige", cmd.v_ang == 0)

    # Llegada por área.
    cmd = e.avanzar(1, [oso(error_x=0.0, area=config.AREA_OBJETIVO + 0.01)])
    verificar("llega a ENCONTRADO por área", e.maq.estado == estados.ENCONTRADO)
    verificar("frena del todo al llegar", cmd.v_lin == 0 and cmd.v_ang == 0,
              "cualquier valor distinto de 0 da 0,091 m/s: no hay 'ir despacio'")
    verificar("suena el buzzer de hallazgo", cmd.buzzer == config.BUZZER_HALLAZGO)

    # ENCONTRADO es terminal y el buzzer no se repite.
    e.avanzar(10, [oso(area=0.20)])
    verificar("ENCONTRADO es terminal", e.maq.estado == estados.ENCONTRADO)
    verificar("el buzzer suena UNA vez, no una por frame",
              e.buzzers == [config.BUZZER_HALLAZGO], str(e.buzzers))


def prueba_perdida():
    titulo("3. APROXIMAR -> BUSCAR — se perdió el objetivo")
    e = Escenario()
    e.avanzar(1, [oso(area=0.03)])
    assert e.maq.estado == estados.APROXIMAR
    e.avanzar(1, [])
    verificar("sin objetivo confirmado vuelve a BUSCAR",
              e.maq.estado == estados.BUSCAR, e.maq.estado)

    # Lo busca por donde lo vio por última vez (piso, 2026-10-01): si se fue
    # por la izquierda, barrer a la derecha es dar casi una vuelta entera.
    for lado, nombre in ((-1, "izquierda"), (1, "derecha")):
        e3 = Escenario()
        e3.avanzar(1, [oso(error_x=0.7 * lado, area=0.03)])
        e3.avanzar(1, [])                               # lo pierde
        e3.avanzar(ciclos=int(2.0 / 0.05), dt=0.05)      # un par de pasos de barrido
        giros = [c.v_ang for c in e3.motivos_con("barriendo")]
        verificar("perdido por la %s, lo busca barriendo a la %s" % (nombre, nombre),
                  giros and all(g * lado > 0 for g in giros), str(giros[:3]))

    # Confirmado pero ausente de ESTE frame: el Confirmador todavía no lo dio
    # por perdido, así que la clase sigue confirmada pero no hay caja.
    e2 = Escenario()
    e2.avanzar(1, [oso(area=0.03)])
    cmd = e2.maq.paso({config.CLASE_OBJETIVO}, [], SIN_SONAR, e2.t)
    verificar("confirmado sin caja en el frame: frena, no sigue a ciegas",
              cmd.v_lin == 0 and cmd.v_ang == 0 and cmd.estado == estados.APROXIMAR)


# ==============================================================================
# 4. HUIR (§6.3) — prioridad y fases
# ==============================================================================
def prueba_prioridad():
    titulo("4. HUIR — prioridad incondicional sobre APROXIMAR")
    e = Escenario()
    e.avanzar(1, [oso(area=0.03)])
    assert e.maq.estado == estados.APROXIMAR

    e.avanzar(1, [oso(area=0.03), mochila(error_x=0.4)])
    verificar("con las dos clases a la vista, huir gana",
              e.maq.estado == estados.HUIR, e.maq.estado)
    verificar("suena la alarma, no el hallazgo",
              e.buzzers == [config.BUZZER_ALARMA], str(e.buzzers))

    # Y también gana sobre una llegada inminente.
    e2 = Escenario()
    e2.avanzar(1, [oso(area=0.03)])
    e2.avanzar(1, [oso(area=config.AREA_OBJETIVO + 0.05), mochila(error_x=-0.3)])
    verificar("gana incluso cuando el oso ya está al alcance",
              e2.maq.estado == estados.HUIR, e2.maq.estado)


def prueba_fases_huir():
    titulo("5. HUIR — las tres fases, en orden y sin reevaluar")
    e = Escenario()
    # La mochila a la derecha (error_x > 0).
    e.avanzar(1, [mochila(error_x=0.5)])
    verificar("entra a HUIR", e.maq.estado == estados.HUIR)
    verificar("recuerda de qué lado estaba la amenaza", e.maq.lado_amenaza == 1.0)

    # Recorrer la maniobra completa con la mochila SIEMPRE a la vista: si se
    # reevaluara, la maniobra se reiniciaría para siempre.
    dur = config.HUIR_RETROCESO_S + config.HUIR_GIRO_S + config.HUIR_AVANCE_S
    e.avanzar(ciclos=int(dur / DT) + 3, detecciones=[mochila(error_x=0.5)])

    f1 = e.motivos_con("fase 1")
    f2 = e.motivos_con("fase 2")
    f3 = e.motivos_con("fase 3")

    verificar("ocurren las tres fases", f1 and f2 and f3,
              "f1=%d f2=%d f3=%d" % (len(f1), len(f2), len(f3)))
    verificar("fase 1 retrocede", all(c.v_lin < 0 for c in f1))
    verificar("fase 1 gira al lado opuesto a la amenaza",
              all(c.v_ang < 0 for c in f1), "amenaza a la derecha -> girar a la izquierda")
    verificar("fase 2 gira en el lugar", all(c.v_lin == 0 and c.v_ang != 0 for c in f2))
    # Si girara para el otro lado, empezaría deshaciendo el giro del retroceso
    # y volvería a pasar por delante de la mochila (piso, 2026-10-01).
    verificar("fase 2 sigue girando para el mismo lado que la fase 1",
              all(c.v_ang < 0 for c in f2), "amenaza a la derecha -> las dos a la izquierda")
    verificar("fase 3 avanza", all(c.v_lin > 0 for c in f3))

    orden = [e.comandos.index(f1[0]), e.comandos.index(f2[0]), e.comandos.index(f3[0])]
    verificar("las fases van en orden", orden == sorted(orden), str(orden))

    verificar("con la mochila a la vista todo el tiempo, la maniobra TERMINA",
              e.maq.estado == estados.BUSCAR,
              "quedó en %s: se está reevaluando la amenaza" % e.maq.estado)
    verificar("la alarma suena una sola vez en toda la huida",
              e.buzzers.count(config.BUZZER_ALARMA) == 1, str(e.buzzers))
    verificar("al terminar apaga el buzzer", config.BUZZER_OFF in e.buzzers)

    # El lado opuesto.
    e2 = Escenario()
    e2.avanzar(1, [mochila(error_x=-0.5)])
    verificar("amenaza a la izquierda: retrocede girando a la derecha",
              all(c.v_ang > 0 for c in e2.motivos_con("fase 1")))


def prueba_refractario():
    titulo("5b. HUIR — el refractario que evita el bucle de huidas (regla 4)")
    # Este escenario es el que destapó el bug: la mochila sigue confirmada al
    # terminar la maniobra, no porque se la vea sino por la inercia del
    # Confirmador (M_PERDER = 5 frames).
    e = Escenario()
    e.avanzar(1, [mochila(error_x=0.5)])
    dur = config.HUIR_RETROCESO_S + config.HUIR_GIRO_S + config.HUIR_AVANCE_S
    e.avanzar(ciclos=int(dur / DT) + 2, detecciones=[mochila(error_x=0.5)])
    assert e.maq.estado == estados.BUSCAR, e.maq.estado

    # Justo después: la clase sigue confirmada, pero NO tiene que rehuir.
    e.avanzar(3, [mochila(error_x=0.5)])
    verificar("con la amenaza aún confirmada, no rehúye en el acto",
              e.maq.estado == estados.BUSCAR, e.maq.estado)
    verificar("y la alarma no vuelve a sonar",
              e.buzzers.count(config.BUZZER_ALARMA) == 1, str(e.buzzers))

    # Pasado el refractario, una amenaza que sigue ahí SÍ es una amenaza.
    e.t += config.HUIR_REFRACTARIO_S
    e.avanzar(1, [mochila(error_x=0.5)])
    verificar("pasado el refractario, vuelve a huir de una amenaza persistente",
              e.maq.estado == estados.HUIR, e.maq.estado)

    verificar("el refractario cubre la inercia del Confirmador",
              config.HUIR_REFRACTARIO_S > config.M_PERDER / config.FPS_OBJETIVO,
              "%.1fs no alcanza para los %.1fs que el confirmador sostiene la clase"
              % (config.HUIR_REFRACTARIO_S, config.M_PERDER / config.FPS_OBJETIVO))


def prueba_sentido_tras_huir():
    titulo("5c. BUSCAR después de huir — el barrido arranca para un lado al azar")
    # Con el sentido fijo el robot repetía el recorrido: huía, barría para el
    # mismo lado, daba con lo mismo y huía otra vez igual (piso, 2026-10-02).
    dur = config.HUIR_RETROCESO_S + config.HUIR_GIRO_S + config.HUIR_AVANCE_S

    def huir(maq):
        """Una huida completa; devuelve el escenario, ya de vuelta en BUSCAR."""
        e = Escenario(maquina=maq)
        e.avanzar(1, [mochila(error_x=0.5)])
        e.avanzar(ciclos=int(dur / DT) + 2)
        assert maq.estado == estados.BUSCAR, maq.estado
        return e

    # Las semillas hacen que la prueba dé siempre lo mismo.
    sentidos = []
    for semilla in range(40):
        maq = estados.Maquina(azar=random.Random(semilla))
        huir(maq)
        sentidos.append(maq.sentido_barrido)
    verificar("tras huir, el barrido sale a veces a la derecha y a veces a la izquierda",
              set(sentidos) == {-1, 1}, str(sentidos))
    verificar("ninguno de los dos lados es raro (al menos 1 de cada 4)",
              min(sentidos.count(-1), sentidos.count(1)) >= 10,
              "derecha %d, izquierda %d" % (sentidos.count(1), sentidos.count(-1)))

    # El comando de giro del barrido respeta el lado sorteado, para los dos.
    for buscado in (-1, 1):
        semilla = sentidos.index(buscado)
        maq = estados.Maquina(azar=random.Random(semilla))
        e = huir(maq)
        e.avanzar(ciclos=int(3.0 / 0.05), dt=0.05)
        barriendo = e.motivos_con("barriendo")
        verificar("sorteado %s: el barrido gira para ese lado"
                  % ("derecha" if buscado > 0 else "izquierda"),
                  len(barriendo) > 0 and all((c.v_ang > 0) == (buscado > 0) for c in barriendo),
                  "barriendo=%d" % len(barriendo))

    # Si al terminar la huida la mochila está a la vista, no hay sorteo que
    # valga: barre hacia el lado CONTRARIO. Se usa en cada caso una semilla
    # que había sorteado justo el lado malo.
    for lado_mochila, ex in (("derecha", 0.75), ("izquierda", -0.75)):
        hacia_ella = 1 if ex > 0 else -1
        maq = estados.Maquina(azar=random.Random(sentidos.index(hacia_ella)))
        e = huir(maq)
        assert maq.sentido_barrido == hacia_ella
        # 1,0 s más: huir() ya gastó 0,6 s del período sordo, que dura 2,0.
        e.avanzar(ciclos=int(1.0 / 0.05), detecciones=[mochila(error_x=ex)], dt=0.05)
        barriendo = e.motivos_con("barriendo")
        verificar("mochila a la %s al terminar de huir: barre para el otro lado" % lado_mochila,
                  maq.sentido_barrido == -hacia_ella and len(barriendo) > 0
                  and all((c.v_ang > 0) == (hacia_ella < 0) for c in barriendo),
                  "sentido=%d barriendo=%d" % (maq.sentido_barrido, len(barriendo)))
        verificar("y en el período sordo no vuelve a huir (mochila a la %s)" % lado_mochila,
                  maq.estado == estados.BUSCAR, maq.estado)

    # Lo que no cambia.
    verificar("al arrancar barre a la derecha, como siempre",
              estados.Maquina().sentido_barrido == 1)
    anterior = config.BUSCAR_SENTIDO_AZAR_TRAS_HUIR
    config.BUSCAR_SENTIDO_AZAR_TRAS_HUIR = False
    try:
        fijos = []
        for semilla in range(10):
            maq = estados.Maquina(azar=random.Random(semilla))
            huir(maq)
            fijos.append(maq.sentido_barrido)
    finally:
        config.BUSCAR_SENTIDO_AZAR_TRAS_HUIR = anterior
    verificar("con la opción apagada, tras huir sigue barriendo a la derecha",
              set(fijos) == {1}, str(fijos))


# ==============================================================================
# 5. Ultrasónico (§6.2) — cableado desde el 2026-10-02
# ==============================================================================
def prueba_sonar():
    titulo("6. Ultrasónico — llegada, desvío y 'no sé'")
    cerca = sonar(config.DIST_PARADA_CM - 5)

    # a) el eco ES el oso: centrado y ya grande.
    e = Escenario()
    e.avanzar(1, [oso(area=0.03)])
    e.avanzar(1, [oso(error_x=0.05, area=config.AREA_OBJETIVO * 0.8)], estado_esp=cerca)
    verificar("eco centrado y con el oso grande -> ENCONTRADO",
              e.maq.estado == estados.ENCONTRADO, e.maq.estado)

    # b) el eco NO es el oso: el oso se ve chico y lejos.
    e2 = Escenario()
    e2.avanzar(1, [oso(area=0.01)])
    cmd = e2.avanzar(1, [oso(error_x=0.8, area=0.01)], estado_esp=cerca)
    verificar("eco con el oso chico y al costado -> desvío, no llegada",
              e2.maq.estado == estados.APROXIMAR and cmd.v_lin == 0 and cmd.v_ang != 0,
              "estado=%s cmd=%s" % (e2.maq.estado, cmd))
    verificar("el desvío va al lado contrario del objetivo", cmd.v_ang < 0,
              "oso a la derecha -> esquivar por la izquierda")

    # c) sin lectura NO es distancia cero.
    verificar("dist=-1 se lee como 'no sé', no como 'pegado'",
              not SIN_SONAR.hay_distancia and not SIN_SONAR.obstaculo())
    e3 = Escenario()
    e3.avanzar(1, [oso(area=0.02)])
    cmd = e3.avanzar(1, [oso(area=0.02)], estado_esp=SIN_SONAR)
    verificar("con el ultrasónico desconectado, APROXIMAR funciona igual",
              e3.maq.estado == estados.APROXIMAR and cmd.v_lin > 0)

    # d) el pulso de avance de BUSCAR no va contra una pared.
    ciclo = config.BUSCAR_GIRO_S + config.BUSCAR_AVANCE_S
    e4 = Escenario()
    e4.avanzar(ciclos=int(ciclo / 0.05), estado_esp=cerca, dt=0.05)
    reubicando = e4.motivos_con("reubicando")
    verificar("BUSCAR con algo adelante: el pulso de reubicación gira, no avanza",
              len(reubicando) > 0
              and all(c.v_lin == 0 and c.v_ang != 0 for c in reubicando),
              "reubicando=%d" % len(reubicando))
    verificar("BUSCAR con algo adelante: el barrido no cambia",
              len(e4.motivos_con("barriendo")) > 0 and len(e4.motivos_con("mirando")) > 0)
    # e) una lectura libre suelta entre dos pegadas no hace avanzar. En el piso
    # (corrida_20261002_103658) el sensor dio 16 cm, 150, 11 girando frente a
    # una pared, y con el 150 el robot avanzó un ciclo contra ella.
    lejos = sonar(150)
    e6 = Escenario()
    e6.avanzar(1, [mochila()])
    e6.avanzar(1, dt=config.HUIR_RETROCESO_S + config.HUIR_GIRO_S)
    c1 = e6.avanzar(1, estado_esp=cerca, dt=0.09)
    c2 = e6.avanzar(1, estado_esp=lejos, dt=config.SONAR_RETENCION_S)
    c3 = e6.avanzar(1, estado_esp=lejos, dt=0.09)
    verificar("HUIR fase 3 con algo adelante: gira, no avanza",
              "fase 3" in c1.motivo and c1.v_lin == 0 and c1.v_ang != 0, str(c1))
    verificar("una lectura libre suelta NO alcanza para volver a avanzar",
              c2.v_lin == 0 and c2.v_ang != 0, str(c2))
    verificar("pasada la retención con el camino libre, avanza",
              "fase 3" in c3.motivo and c3.v_lin > 0, str(c3))

    # f) dos umbrales: entre el de llegada y el de esquivar, HUIR esquiva pero
    # APROXIMAR sigue acercándose al oso.
    medio = sonar((config.DIST_PARADA_CM + config.DIST_OBSTACULO_CM) / 2.0)
    verificar("el umbral de esquivar es más largo que el de llegada",
              config.DIST_OBSTACULO_CM > config.DIST_PARADA_CM)
    e7 = Escenario()
    e7.avanzar(1, [mochila()])
    e7.avanzar(1, dt=config.HUIR_RETROCESO_S + config.HUIR_GIRO_S)
    cmd = e7.avanzar(1, estado_esp=medio, dt=0.09)
    verificar("a media distancia, HUIR fase 3 ya esquiva",
              "fase 3" in cmd.motivo and cmd.v_lin == 0 and cmd.v_ang != 0, str(cmd))
    e8 = Escenario()
    e8.avanzar(1, [oso(area=0.02)])
    cmd = e8.avanzar(1, [oso(error_x=0.8, area=0.02)], estado_esp=medio)
    verificar("a media distancia, APROXIMAR sigue hacia el oso",
              e8.maq.estado == estados.APROXIMAR and cmd.v_lin > 0, str(cmd))

    e5 = Escenario()
    e5.avanzar(ciclos=int(ciclo / 0.05), estado_esp=sonar(config.DIST_OBSTACULO_CM + 30), dt=0.05)
    verificar("BUSCAR con el camino libre: el pulso de reubicación avanza",
              all(c.v_lin > 0 for c in e5.motivos_con("reubicando"))
              and len(e5.motivos_con("reubicando")) > 0)


# ==============================================================================
# 7. Frenar el barrido al primer avistamiento (config.BUSCAR_FRENAR_AL_VER)
# ==============================================================================
def prueba_frenar_al_ver():
    titulo("8. BUSCAR frena al ver el objetivo, antes de confirmarlo")
    # Acá hace falta separar lo VISTO de lo CONFIRMADO, que Escenario junta:
    # se llama a la máquina a mano, con el oso en las detecciones crudas y el
    # conjunto de confirmadas vacío — el primer frame de una racha.
    def ciclo(maq, t, dets, confirmadas=()):
        return maq.paso(set(confirmadas), list(dets), SIN_SONAR, t)

    # El barrido arranca MIRANDO (2026-10-01), así que el tramo de giro del
    # primer paso empieza recién pasado BUSCAR_PASO_MIRAR_S: ahí se muestrea.
    girando = 100.0 + config.BUSCAR_PASO_MIRAR_S + 0.05

    previo = config.BUSCAR_FRENAR_AL_VER
    try:
        config.BUSCAR_FRENAR_AL_VER = False
        libre = estados.Maquina()
        cmd = ciclo(libre, 100.0, [])
        verificar("el barrido arranca mirando, no girando",
                  cmd.v_lin == 0 and cmd.v_ang == 0 and cmd.motivo == "mirando", str(cmd))
        cmd = ciclo(libre, girando, [oso(error_x=0.8)])
        verificar("apagado: sigue girando con el oso visto sin confirmar",
                  cmd.estado == estados.BUSCAR and cmd.v_ang > 0, str(cmd))

        config.BUSCAR_FRENAR_AL_VER = True
        maq = estados.Maquina()
        ciclo(maq, 100.0, [])
        cmd = ciclo(maq, girando, [oso(error_x=0.8)])
        verificar("encendido: frena con el oso visto sin confirmar",
                  cmd.v_lin == 0 and cmd.v_ang == 0 and "posible objetivo" in cmd.motivo,
                  str(cmd))
        verificar("frenar no es cambiar de estado: sigue en BUSCAR",
                  cmd.estado == estados.BUSCAR and cmd.buzzer is None, str(cmd))
        cmd = ciclo(maq, girando + 0.05, [])
        verificar("si el oso no vuelve a aparecer, retoma el barrido",
                  cmd.estado == estados.BUSCAR and cmd.v_ang > 0, str(cmd))
        cmd = ciclo(maq, girando + 0.10, [mochila(error_x=0.5)])
        # Hasta el 2026-10-01 esto verificaba lo contrario ("una mochila sin
        # confirmar no frena el barrido"). En el piso, con la mochila enfrente,
        # el barrido giró antes de que se juntaran los 3 frames y no huyó nunca.
        verificar("una mochila vista sin confirmar también frena el barrido",
                  cmd.v_lin == 0 and cmd.v_ang == 0 and "posible amenaza" in cmd.motivo,
                  str(cmd))
        verificar("frenar por la mochila tampoco es cambiar de estado",
                  cmd.estado == estados.BUSCAR and cmd.buzzer is None, str(cmd))
        sorda = estados.Maquina()
        ciclo(sorda, 100.0, [])
        sorda.huida_termino_en = 100.0          # acaba de terminar una huida
        cmd = ciclo(sorda, 100.0 + DT, [mochila(error_x=0.5)])
        verificar("en el refractario la mochila no frena: se la ignora a propósito",
                  "posible amenaza" not in cmd.motivo, str(cmd))
        cmd = ciclo(maq, 100.0 + 3 * DT, [oso()], confirmadas=[config.CLASE_OBJETIVO])
        verificar("confirmado, pasa a APROXIMAR como siempre",
                  cmd.estado == estados.APROXIMAR, str(cmd))
    finally:
        config.BUSCAR_FRENAR_AL_VER = previo


# ==============================================================================
# 6. El protocolo que sale
# ==============================================================================
def prueba_rango_comandos():
    titulo("7. Todo lo que sale entra en el protocolo de §8")
    e = Escenario()
    guiones = (
        (60, [], SIN_SONAR),
        (10, [oso(error_x=1.0, area=0.0)], SIN_SONAR),
        (10, [oso(error_x=-1.0, area=0.0)], sonar(5)),
        (40, [mochila(error_x=1.0)], sonar(3)),
    )
    for ciclos, dets, esp in guiones:
        e.avanzar(ciclos, dets, esp)

    fuera = [c for c in e.comandos
             if not (-100 <= c.v_lin <= 100 and -100 <= c.v_ang <= 100)]
    verificar("v_lin y v_ang siempre en [-100, 100]", not fuera,
              str(fuera[:3]))
    verificar("todos los comandos son enteros",
              all(isinstance(c.v_lin, int) and isinstance(c.v_ang, int) for c in e.comandos))

    patrones = {config.BUZZER_OFF, config.BUZZER_HALLAZGO, config.BUZZER_ALARMA}
    verificar("los patrones de buzzer son los tres de §8",
              set(e.buzzers) <= patrones, str(set(e.buzzers)))


# ==============================================================================
def main():
    print("=" * 66)
    print("Verificación de la máquina de estados — PLAN.md §6")
    print("=" * 66)
    print("Reloj simulado a %.0f FPS (%.0f ms por ciclo)" % (config.FPS_OBJETIVO, DT * 1000))

    for prueba in (prueba_buscar, prueba_aproximar, prueba_perdida,
                   prueba_prioridad, prueba_fases_huir, prueba_refractario,
                   prueba_sentido_tras_huir, prueba_sonar,
                   prueba_rango_comandos, prueba_frenar_al_ver):
        prueba()

    print("\n" + "=" * 66)
    if _fallas:
        print("%d verificaciones FALLARON:" % len(_fallas))
        for f in _fallas:
            print("  - %s" % f)
        return 1
    print("Todo en orden. La máquina de estados hace lo que dice PLAN.md §6.")
    print("\nLo que esto NO garantiza: que los tiempos de HUIR den un giro de 180")
    print("reales, ni que V_ANG_BUSCAR alcance para rotar. Eso se mide en piso.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
