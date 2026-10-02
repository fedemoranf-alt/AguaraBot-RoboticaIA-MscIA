"""
TPF Robótica IA — Simulador cinemático del piso (predicción del Día 5)
==============================================================================
Corre la máquina de estados REAL (`estados.py`) y el Confirmador REAL
(`vision.py`) contra un robot de tracción diferencial simulado, con la
calibración medida de los motores, la latencia medida del lazo y una cámara
de campo visual acotado. Lo que se simula es el mundo; lo que decide es el
mismo código que va a correr en el Pi.

Para qué sirve: predecir ANTES de soltar el robot lo que la demo va a medir, y
tener contra qué comparar. `prueba_estados.py` verifica la lógica con el tiempo
congelado; esto agrega lo que ella no puede ver — que mientras el Pi piensa, el
robot se sigue moviendo.

    python simular_piso.py                    # 200 corridas de aproximación
    python simular_piso.py --trocha 0.17      # sensibilidad a la geometría
    python simular_piso.py --borroso 150      # detección que empeora al girar
    python simular_piso.py --csv ../logs      # guarda UNA corrida como CSV

⚠️ Es un modelo, con los números que se conocen y los que no:

    medido    calibración de motores (V_MIN_MS/V_MAX_MS), FPS del lazo (11,2),
              edad del frame (36-64 ms), inferencia (88 ms), alcance (~1,1 m),
              `ar` contra distancia (30/50/70 cm)
    estimado  TROCHA_M (de una foto), FOV_H_GRAD (de la hoja de datos)
    supuesto  inercia de los motores, probabilidad de detección, deslizamiento
              nulo de las ruedas

Sirve para comparar variantes entre sí y para saber qué mirar en el piso. Los
números absolutos se contrastan con la demo — como el proxy de reescalado del
Día 10, que predijo 138 cm de alcance y la realidad dio 110.
"""

from __future__ import annotations

import argparse
import math
import random
import statistics
from collections import deque
from dataclasses import dataclass

import config
import estados
from enlace_esp32 import ESTADO_VACIO
from vision import Confirmador, Deteccion


# ==============================================================================
# 1. El modelo del mundo
# ==============================================================================
PERIODO_S = 1 / 11.2        # ✅ medido: lazo completo a 11,2 FPS (2026-09-22)
EDAD_FRAME_S = 0.050        # ✅ medido: 36-64 ms de edad al salir de read()
DECISION_S = 0.090          # ✅ medido: 88 ms de inferencia, más serie
ALCANCE_M = 1.10            # ✅ medido con el oso de ~20 cm
K_AREA = 0.050              # ar ≈ K / d², ajuste de los puntos de 30/50/70 cm
                            #   (0,0459 · 0,0555 · 0,0475): vale en ese rango
EX_MAX = 0.85               # con el centro más afuera la caja queda cortada
TAU_MOTOR_S = 0.06          # supuesto: inercia de rueda + reductor
P_DETECCION = 0.90          # supuesto: por frame, con el oso a la vista
RADIO_OSO_M = 0.12          # medio ancho del oso impreso: menos es chocarlo
DT_SIM = 0.005


def velocidad_rueda(u):
    """Comando de rueda en [-100, 100] → m/s, con el escalón de la calibración."""
    if u == 0:
        return 0.0
    return math.copysign(config.velocidad_real(abs(u) / 100.0), u)


def mezclar(v_lin, v_ang):
    """La misma mezcla que el firmware (PLAN.md §8): escala el par, no recorta."""
    izq, der = v_lin + v_ang, v_lin - v_ang
    m = max(abs(izq), abs(der))
    if m > 100:
        izq, der = int(izq * 100 / m), int(der * 100 / m)
    return izq, der


@dataclass
class Pose:
    x: float = 0.0
    y: float = 0.0
    th: float = 0.0     # rumbo, antihorario positivo (convención matemática)


class Robot:
    def __init__(self, trocha):
        self.trocha = trocha
        self.pose = Pose()
        self.v_izq = self.v_der = 0.0
        self.historia = deque(maxlen=100)   # (t, x, y, th) para la edad del frame

    def paso(self, cmd, dt, t):
        izq, der = mezclar(cmd.v_lin, cmd.v_ang)
        a = dt / (TAU_MOTOR_S + dt)
        self.v_izq += a * (velocidad_rueda(izq) - self.v_izq)
        self.v_der += a * (velocidad_rueda(der) - self.v_der)
        v = (self.v_izq + self.v_der) / 2
        # v_ang > 0 gira a la derecha: rueda izquierda más rápida → horario.
        w = (self.v_der - self.v_izq) / self.trocha
        p = self.pose
        p.x += v * math.cos(p.th) * dt
        p.y += v * math.sin(p.th) * dt
        p.th += w * dt
        self.historia.append((t, p.x, p.y, p.th))
        return w

    def pose_en(self, t):
        """Dónde estaba el robot en el instante t (para la edad del frame)."""
        for ti, x, y, th in reversed(self.historia):
            if ti <= t:
                return x, y, th
        return self.pose.x, self.pose.y, self.pose.th


def observar(robot, objetos, t, fov_grad, w_actual, borroso, rng):
    """Lo que devolvería YOLO sobre un frame tomado EDAD_FRAME_S atrás."""
    x, y, th = robot.pose_en(t - EDAD_FRAME_S)
    mitad = math.radians(fov_grad) / 2
    dets = []
    for clase, (ox, oy) in objetos.items():
        d = math.hypot(ox - x, oy - y)
        fi = math.atan2(oy - y, ox - x) - th
        fi = (fi + math.pi) % (2 * math.pi) - math.pi       # izquierda positivo
        if abs(fi) >= math.pi / 2 or d > ALCANCE_M:
            continue
        ex = -math.tan(fi) / math.tan(mitad)                # derecha positivo
        if abs(ex) > EX_MAX:
            continue
        p = P_DETECCION
        if borroso:
            p *= max(0.0, 1 - abs(math.degrees(w_actual)) / borroso)
        if rng.random() >= p:
            continue
        ex += rng.gauss(0, 0.02)
        ar = min(K_AREA / max(d, 0.05) ** 2, 1.0)
        lado = int(math.sqrt(ar * 640 * 480))
        dets.append(Deteccion(clase, 0.8, 0, 0, lado, lado, ex, ar))
    return dets


# ==============================================================================
# 2. Una corrida
# ==============================================================================
@dataclass
class Resultado:
    encontrado: bool
    t_encontrado: float
    choco: bool
    dist_final: float
    rumbo_final_grad: float     # dónde quedó el oso respecto del frente
    perdidas: int               # APROXIMAR → BUSCAR por "objetivo perdido"
    avistamientos_buscar: int   # frames de BUSCAR con el oso crudo a la vista
    sobregiro_grad: list        # por confirmación: cuánto giró desde el 1er avistamiento


def correr(rumbo_oso_grad, dist_oso, args, rng, registro=None):
    robot = Robot(args.trocha)
    b = math.radians(rumbo_oso_grad)
    oso = (dist_oso * math.cos(b), dist_oso * math.sin(b))
    objetos = {config.CLASE_OBJETIVO: oso}

    conf = Confirmador()
    maq = estados.Maquina(azar=rng)     # el mismo azar: corridas repetibles
    cmd = estados.Comando(0, 0, None, estados.BUSCAR, "arranque")
    pendientes = deque()        # (t_aplicar, cmd): la decisión tarda en llegar

    t, t_prox_frame, w = 0.0, 0.0, 0.0
    perdidas = avist = 0
    th_primer_avist = None      # rumbo en el primer frame de la racha que confirma
    midiendo, max_giro = False, 0.0
    sobregiros = []
    estado_prev = maq.estado
    choco = False

    while t < args.duracion:
        if t >= t_prox_frame:
            t_prox_frame += PERIODO_S
            dets = observar(robot, objetos, t, args.fov, w, args.borroso, rng)
            confirmadas = conf.actualizar(d.clase for d in dets)
            nuevo = maq.paso(confirmadas, dets, ESTADO_VACIO, t)
            pendientes.append((t + DECISION_S, nuevo))

            vio = any(d.clase == config.CLASE_OBJETIVO for d in dets)
            if maq.estado == estados.BUSCAR and vio:
                avist += 1
                if th_primer_avist is None:
                    th_primer_avist = robot.pose.th
            if maq.estado == estados.BUSCAR and not vio and not confirmadas:
                th_primer_avist = None
            if estado_prev == estados.APROXIMAR and maq.estado == estados.BUSCAR:
                perdidas += 1
            if (estado_prev == estados.BUSCAR and maq.estado == estados.APROXIMAR
                    and th_primer_avist is not None):
                midiendo, max_giro = True, 0.0
            if registro is not None:
                registro.fila(t, PERIODO_S, nuevo, maq, confirmadas, dets, ESTADO_VACIO)
            estado_prev = maq.estado

        while pendientes and pendientes[0][0] <= t:
            _, cmd = pendientes.popleft()

        # Sobregiro: cuánto siguió girando (en el sentido del barrido, que es
        # horario) desde el primer avistamiento hasta que dejó de hacerlo.
        if midiendo:
            max_giro = max(max_giro, math.degrees(th_primer_avist - robot.pose.th))
            if w > -0.05:
                sobregiros.append(max_giro)
                midiendo, th_primer_avist = False, None

        w = robot.paso(cmd, DT_SIM, t)
        t += DT_SIM

        if math.hypot(oso[0] - robot.pose.x, oso[1] - robot.pose.y) < RADIO_OSO_M:
            choco = True
            break
        if maq.estado == estados.ENCONTRADO and abs(w) < 0.01 and cmd.v_lin == 0:
            break

    x, y, th = robot.pose.x, robot.pose.y, robot.pose.th
    fi = math.atan2(oso[1] - y, oso[0] - x) - th
    fi = (fi + math.pi) % (2 * math.pi) - math.pi
    return Resultado(
        encontrado=maq.estado == estados.ENCONTRADO,
        t_encontrado=t if maq.estado == estados.ENCONTRADO else float("nan"),
        choco=choco,
        dist_final=math.hypot(oso[0] - x, oso[1] - y),
        rumbo_final_grad=math.degrees(fi),
        perdidas=perdidas,
        avistamientos_buscar=avist,
        sobregiro_grad=sobregiros,
    )


# ==============================================================================
# 3. Muchas corridas
# ==============================================================================
def resumir(res, args):
    n = len(res)
    ok = [r for r in res if r.encontrado and not r.choco]
    sobreg = [s for r in res for s in r.sobregiro_grad]
    perd = [r.perdidas for r in res]
    print("\n%d corridas · oso a %.2f m en rumbo al azar · %.0f s máx"
          % (n, args.dist, args.duracion))
    print("  trocha %.3f m · FOV %.0f° · V_ANG_BUSCAR %d · KP_ANG %.2f · zona muerta %.2f%s%s"
          % (args.trocha, args.fov, config.V_ANG_BUSCAR, config.KP_ANG,
             config.ZONA_MUERTA_ERROR_X,
             " · borroso %g°/s" % args.borroso if args.borroso else "",
             " · FRENA AL VER" if config.BUSCAR_FRENAR_AL_VER else ""))
    w_buscar = 2 * velocidad_rueda(config.V_ANG_BUSCAR) / args.trocha
    print("  BUSCAR gira a %.0f°/s → vuelta entera en %.2f s (BUSCAR_GIRO_S = %.1f)"
          % (math.degrees(w_buscar), 2 * math.pi / w_buscar, config.BUSCAR_GIRO_S))
    print("  → %.0f° por frame; el oso cruza el campo visual en %.1f frames"
          % (math.degrees(w_buscar) * PERIODO_S,
             2 * EX_MAX * args.fov / 2 / (math.degrees(w_buscar) * PERIODO_S)))
    print()
    print("  ENCONTRADO sin chocar     %3d/%d  (%.0f %%)" % (len(ok), n, 100 * len(ok) / n))
    print("  chocó                     %3d" % sum(r.choco for r in res))
    if ok:
        tiempos = [r.t_encontrado for r in ok]
        print("  tiempo hasta ENCONTRADO   %.1f s ± %.1f  (mediana %.1f)"
              % (statistics.mean(tiempos), statistics.pstdev(tiempos),
                 statistics.median(tiempos)))
        print("  distancia al frenar       %.2f m ± %.2f"
              % (statistics.mean(r.dist_final for r in ok),
                 statistics.pstdev([r.dist_final for r in ok])))
        print("  oso respecto del frente   %.1f° ± %.1f al frenar"
              % (statistics.mean(abs(r.rumbo_final_grad) for r in ok),
                 statistics.pstdev([abs(r.rumbo_final_grad) for r in ok])))
    print("  'objetivo perdido'        %.2f por corrida  (%d corridas con al menos uno)"
          % (statistics.mean(perd), sum(1 for p in perd if p)))
    if sobreg:
        print("  sobregiro al confirmar    %.0f° ± %.0f  (máx %.0f°, FOV %.0f°)"
              % (statistics.mean(sobreg), statistics.pstdev(sobreg), max(sobreg), args.fov))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("-n", type=int, default=200, help="corridas")
    ap.add_argument("--dist", type=float, default=1.0, help="distancia inicial al oso [m]")
    ap.add_argument("--duracion", type=float, default=30.0, help="tope por corrida [s]")
    ap.add_argument("--trocha", type=float, default=config.TROCHA_M)
    ap.add_argument("--fov", type=float, default=config.FOV_H_GRAD)
    ap.add_argument("--borroso", type=float, default=0.0,
                    help="°/s de giro a los que la detección cae a cero (0 = sin efecto)")
    ap.add_argument("--v-ang-buscar", type=int, default=None,
                    help="pisa config.V_ANG_BUSCAR para esta simulación")
    ap.add_argument("--frenar-al-ver", action="store_true",
                    help="pisa config.BUSCAR_FRENAR_AL_VER = True")
    ap.add_argument("--semilla", type=int, default=1)
    ap.add_argument("--csv", default=None, help="directorio: guarda la primera corrida")
    args = ap.parse_args(argv)
    if args.v_ang_buscar is not None:
        config.V_ANG_BUSCAR = args.v_ang_buscar
    if args.frenar_al_ver:
        config.BUSCAR_FRENAR_AL_VER = True

    rng = random.Random(args.semilla)
    res = []
    for i in range(args.n):
        reg = None
        if args.csv and i == 0:
            from registro import Registro
            reg = Registro(directorio=args.csv, extra={"nota": "simular_piso.py",
                                                        "argv": vars(args)})
        try:
            res.append(correr(rng.uniform(-180, 180), args.dist, args, rng, reg))
        finally:
            if reg is not None:
                reg.cerrar()
                print("CSV de la primera corrida: %s" % reg.ruta)
    resumir(res, args)


if __name__ == "__main__":
    main()
