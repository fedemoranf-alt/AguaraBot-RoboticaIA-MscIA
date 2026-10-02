"""
TPF Robótica IA — Parámetros del sistema
==============================================================================
Regla del proyecto (PLAN.md §12): TODOS los parámetros calibrables viven acá.
Nada de constantes mágicas dispersas en el código.

Cada valor lleva de dónde salió: medido, calculado o pendiente de calibrar.
Los marcados ⬜ todavía no se midieron y son los que se tocan en el Día 5.
"""

from pathlib import Path

# ==============================================================================
# 0. Rutas
# ==============================================================================
RAIZ = Path(__file__).resolve().parent.parent
DIR_LOGS = RAIZ / "logs"
DIR_MEDIA = RAIZ / "media"
DIR_MODELOS = RAIZ / "modelos"


# ==============================================================================
# 1. Cámara
# ==============================================================================
# Webcam USB, decidido el 2026-09-22: la Arducam UC-609 (IMX219, 15 pines) no
# llegó a ser vista por el Pi 5 —ni por I2C ni por dmesg— y la vía CSI quedó
# descartada por tiempo, no por diseño. Fijo y no "auto": así el arranque no
# gasta el intento de Picamera2 en cada corrida.
FUENTE_CAMARA = "usb"       # "auto" | "csi" (Picamera2) | "usb" (OpenCV/V4L2)
INDICE_CAMARA = 0           # ✅ /dev/video0 (LifeCam Studio 045e:0811), 2026-09-22

# Formato en que la webcam manda la imagen por USB. None = el que elija el
# driver, que para la LifeCam a 640x480 es YUYV (sin comprimir).
#
# 🔴 MJPG es OBLIGATORIO con los motores andando (medido 2026-09-30, en el piso).
# Con YUYV y los motores girando, los frames llegaban destrozados en franjas
# —paquetes USB perdidos rellenados con restos del frame anterior—, el lazo
# caía a 2,3 FPS con lecturas de hasta 2 s, y YOLO no detectaba nada. Con los
# motores quietos la imagen era perfecta. El ruido de los motores corrompe la
# transmisión, y YUYV ocupa casi todo el ancho de banda USB sin tolerancia a
# pérdidas. MJPG transmite ~10 veces menos: con los motores girando dio 10,7
# FPS, lecturas de 61 ms como máximo e imagen limpia (rayado 0,12 → 0,01).
# Quedan avisos "Corrupt JPEG data" de libjpeg: frames con algún bloque dañado,
# no destrozados. La causa de fondo —el ruido— sigue ahí; esto la tolera.
FORMATO_CAMARA = "MJPG"

# Resolución de captura. No es lo mismo que el tamaño de inferencia (§2):
# la captura fija el ancho de banda de la cámara, la inferencia fija el costo
# de la red. Se barren por separado en bench_vision.py.
ANCHO_CAPTURA = 640
ALTO_CAPTURA = 480

# Alto y ancho de referencia para la ley de control (§7 del PLAN). El error
# lateral y el area_ratio se calculan siempre contra el frame real, así que
# esto es sólo documentación de con qué se calibró.
FPS_CAMARA_SOLICITADO = 30

# Campo visual horizontal. ⬜ NO MEDIDO. La LifeCam Studio declara 75° en
# diagonal para su sensor 16:9; a 640x480 da ~67° si la imagen es el sensor
# entero reescalado y ~53° si es un recorte 4:3 del centro. Se toma el medio.
# Sólo lo usa simular_piso.py: la ley de control trabaja en error_x
# normalizado y no necesita grados.
#
# 🟡 ESTIMADO EN EL PISO el 2026-10-01: ~52°. En la prueba de paso_giro.py el
# oso volvió a aparecer en el mismo lugar de la imagen después de 5 + 5 + 5
# pasos y casi uno más, que sumaron ~4400 px de corrimiento: 360° / 4400 px da
# ~12,2 px por grado, o sea 640 px ≈ 52°. Coincide con la hipótesis del recorte
# 4:3 (~53°) y no con el 60 que se había tomado. Es una cuenta lineal sobre
# corrimientos grandes, así que vale ±3°.
FOV_H_GRAD = 52


# ==============================================================================
# 2. Detección — YOLOv8n sobre COCO (PLAN.md §5 D2, D3)
# ==============================================================================
PESOS_MODELO = "yolov8n.pt"   # o el directorio "yolov8n_ncnn_model" tras exportar
# Tamaño de inferencia. MEDIDO en el Pi 5 el 2026-09-09, con YOLOv8n sobre
# imagen sintética (sin cámara todavía). `predict()` incluye letterbox +
# inferencia + NMS; lo único que falta para el lazo completo es la captura:
#
#     tam    FPS     ms
#     640    3,22   310   ✗ muy por debajo del objetivo de 5 FPS
#     480    5,26   190   ✗ trampa: "cumple" hasta que se le suma la captura
#     320   11,49    87   ✓ 2,3× el objetivo, con margen
#     256   17,65    57     innecesario: resigna alcance de detección de gratis
#
# Escala casi con los píxeles (310 → 87 ms es 0,28, contra 0,25 teórico), así
# que el costo es la red y no un overhead fijo.
#
# ✅ CONFIRMADO CON CÁMARA REAL el 2026-09-22: 640 → 3,20 · 480 → 5,17 · 320 →
# 11,33 FPS. La captura resultó costar 0,6 ms contra 88 de inferencia, así que
# el cuello es la red y la estimación sin cámara acertó por 1,4 %. NCNN no hizo
# falta. Lazo completo con estados y enlace real: 11,2 FPS.
#
# ⚠️ El otro eje de esta decisión, que no se midió hasta después: el ALCANCE DE
# DETECCIÓN. A 320 el corte está en ~85×90 px de caja; a 480 y 640 se detectan
# objetos más chicos, o sea más lejanos. Se eligió 320 igual porque el alcance
# se arregló mejor agrandando el objetivo (§3) que subiendo esto, pero el
# criterio "el mayor que cumple el FPS" ignoraba ese eje por completo.
TAM_INFERENCIA = 320
UMBRAL_CONFIANZA = 0.35       # ⬜ a calibrar contra falsos positivos (§10)
UMBRAL_IOU = 0.45

# Las clases se declaran POR NOMBRE, no por ID. Los IDs de COCO (backpack 24,
# teddy bear 77) se resuelven en runtime contra model.names: hardcodearlos es
# frágil si algún día cambia el modelo o el dataset (PLAN.md §5 D3).
CLASE_OBJETIVO = "teddy bear"   # → APROXIMAR
CLASE_AMENAZA = "backpack"      # → HUIR (prioridad incondicional, D4)
CLASES_DE_INTERES = (CLASE_OBJETIVO, CLASE_AMENAZA)

# Otros nombres con los que el modelo ve al MISMO objeto. Lo que entra por un
# alias sale de vision.Detector ya con el nombre de la derecha, así que el resto
# del sistema (confirmación, estados, registro) no se entera.
#
# 🔴 MEDIDO EN EL PISO el 2026-10-01: la mochila de la demo (negra, de tapa
# enrollable), parada a 1 m y vista desde la altura del robot, NO es "backpack"
# para YOLOv8n: es "suitcase" con confianza 0,60 en 15 de 15 frames, y
# "backpack" en ninguno (scripts_pi/piso/que_ve.py). El modelo aprendió
# mochilas colgadas de una espalda, vistas a la altura de una persona; una
# mochila apoyada en el piso y mirada desde 10 cm de alto se parece más a una
# valija. La etiqueta es correcta en el contexto donde se entrenó, no en éste.
ALIAS_CLASES = {"suitcase": CLASE_AMENAZA}

# Umbral de confianza propio por clase (después de aplicar los alias). Las que
# no figuran usan UMBRAL_CONFIANZA.
#
# 🔴 MEDIDO EN EL PISO el 2026-10-01: la mochila a ~1,2 m da confianza 0,35-0,41
# con el robot quieto, o sea AL BORDE del umbral general de 0,35 (a 1 m justo
# daba 0,60). En dos pruebas de HUIR seguidas el robot la tuvo enfrente, no
# juntó 3 frames por encima del umbral y no huyó. Del otro lado, en los 742
# frames de las tres corridas sin mochila la clase no aparece NI UNA VEZ por
# encima de 0,15. Con ese hueco, 0,20 detecta la mochila con margen y sigue sin
# dar falsas alarmas en esta escena. Vale para ESTA mochila y ESTE lugar: con
# otro fondo (valijas, cajas oscuras) hay que volver a contar.
UMBRAL_POR_CLASE = {CLASE_AMENAZA: 0.20}

# Confirmación temporal (PLAN.md §5 D6): una detección aislada no cambia
# el estado. N frames consecutivos para confirmar, M para dar por perdido.
N_CONFIRMAR = 3
M_PERDER = 5


# ==============================================================================
# 3. Ley de control (PLAN.md §7)
# ==============================================================================
# 🟡 KP_ANG bajado de 0,8 a 0,3 el 2026-10-01, en el piso. Con 0,8 el robot se
# pasó de largo al centrar: el oso entró con ex = +0,48, cruzó el centro en 1 s
# y siguió hasta -0,46 (corrida_20261001_162319). La cuenta que lo explica: la
# velocidad de giro es ω ≈ 7,1·KP_ANG·(error en radianes), o sea una ganancia
# de lazo de 5,7 1/s con 0,8; y entre que la cámara toma el frame y las ruedas
# responden pasan ~0,25 s. Ganancia × retardo = 1,4, al borde de oscilar (el
# límite es π/2). Con 0,3 queda en 0,5: centra en ~0,5 s sin pasarse.
#
# 🟡 ...y de 0,3 a 0,5 el mismo día. Con 0,3 centró bien un oso que entró por
# la derecha (corrida_20261001_162944), pero con uno a la izquierda no alcanzó:
# ex bajó de -0,50 a -0,26, se estancó, y al acercarse volvió a crecer hasta
# salirse por el borde (-0,79) — objetivo perdido a 55 cm
# (corrida_20261001_170756). Dos cosas que la cuenta de arriba no tenía:
#   - el giro REAL avanzando es más o menos la mitad del que predice la trocha
#     medida girando en el lugar, así que la ganancia efectiva era ~1 1/s;
#   - el robot se tuerce solo: a la izquierda mientras acelera (~3,5°/s) y a la
#     derecha mientras frena (~5°/s), medido con v_ang = 0 en
#     corrida_20261001_160226. La rueda izquierda, de menor reducción, tarda
#     más en tomar velocidad y más en perderla.
# 0,5 es el compromiso: ganancia efectiva ~1,8 1/s, producto con el retardo
# ~0,45 (o 0,9 si el giro se realizara entero), lejos del límite en los dos casos.
KP_ANG = 0.5            # agresividad del giro. Alto → oscila; bajo → no centra
KP_LIN = 2.4            # 🟡 2026-10-01: rampa de frenado desde ~1 m (ver abajo)
AREA_OBJETIVO = 0.35    # 🟡 2026-10-01: para quedar a ~30 cm (ver abajo)

# 🟡 AJUSTE DEL 2026-10-01, EN EL PISO — el robot tiene que quedar a ~30 cm del
# oso (antes: 50), y el número que va acá NO es el `ar` de esa distancia:
#
# En la primera aproximación completa (corrida_20261001_160226, con 4,5 y 0,222)
# decidió frenar con ar = 0,223 y quedó quieto con ar = 0,333: **37 cm con
# cinta**. Se pasó unos 13 cm entre la decisión y la detención — el frame con
# el que decide ya tiene ~0,15 s, y el robot venía frenando desde 0,30 m/s con
# su inercia. O sea: AREA_OBJETIVO es dónde DECIDE frenar, no dónde queda.
#
# Para quedar a ~30 cm (ar ≈ 0,51 según el barrido de abajo) se decide antes,
# con ar = 0,35 (~39 cm), y se baja KP_LIN a 2,4 para que la rampa de frenado
# empiece cerca de 1 m (ar ≈ 0,05) y llegue despacio: con 4,5 y este objetivo
# la rampa habría empezado recién a ~55 cm. Sigue mandando V_LIN_MAX
# (2,4 · 0,35 · 100 = 84 > 72). ⬜ Verificar con cinta y corregir.

# CALIBRACIÓN ANTERIOR (2026-09-22: KP_LIN = 4,5 y AREA_OBJETIVO = 0,222, para
# frenar a 50 cm). Se deja porque el barrido de distancias sigue valiendo y es
# de donde salen los números de arriba:
#
# MEDICIÓN (barrido de distancias, no un punto solo):
#
#     30 cm -> 0,510      70 cm -> 0,097      110 cm -> 0,073  (límite: más
#     50 cm -> 0,222     100 cm -> 0,095       lejos no detecta)
#
# Se eligió **50 cm como distancia de frenado**, y su `ar` MEDIDO —0,222— es el
# que va acá. No se extrapoló: los puntos de 100 y 110 cm dan `ar·d²` del doble
# que los tres primeros (950 y 883 contra 459-555), así que la ley del cuadrado
# inverso NO se sostiene en todo el rango medido y una extrapolación habría
# heredado ese error. Los 30/50/70 cm sí son consistentes dentro de ±10 %.
#
# ⚠️ EL CONTEXTO ES PARTE DEL NÚMERO. `ar` no mide distancia: mide TAMAÑO
# APARENTE. El objetivo calibrado es el **oso impreso ocupando una hoja A4
# (~20 cm)**. Con el impreso anterior, de 6,5 cm, el alcance de detección era de
# ~45 cm y `AREA_OBJETIVO` valía 0,066: los dos números cambian juntos. Si se
# cambia el objetivo, se vuelve a medir con `bench_vision.py --en-vivo`.
#
# ALCANCE DE DETECCIÓN con este objetivo: **~110 cm** (medido). Con eso BUSCAR
# tiene sentido: el robot ve el objetivo desde más de un metro.
#
# KP_LIN sale de AREA_OBJETIVO, no se elige aparte: el techo de la ley es
# KP_LIN · AREA_OBJETIVO · 100 (ver control.py §5). Con 4,5 da 100, o sea que
# **el que limita es V_LIN_MAX = 72** y no la ganancia — que es lo que se
# quiere. Basta KP_LIN ≥ 3,24 para eso; se eligió 4,5 para que el robot vaya a
# velocidad máxima desde que detecta (a 110 cm) y empiece a frenar a ~90 cm,
# llegando a 0 en los últimos centímetros. Con los valores viejos (2,0 y 0,15)
# el techo real era 30 y el clamp de 72 no actuaba nunca.

# Zona muerta alrededor del centro. No es un ajuste fino: el robot no tiene
# arranque suave (§4), así que sin esto oscila alrededor del objetivo.
ZONA_MUERTA_ERROR_X = 0.08   # ⬜ |error_x| menor a esto → v_ang = 0

# Techo de velocidad lineal, en unidades del protocolo [0, 100].
#
# 🔴 OJO: el `v_max = 0.34` de PLAN.md §7 quedó OBSOLETO con la calibración del
# 2026-08-27. Ese 0,34 se dedujo cuando el duty escalaba desde cero (0,34 × 0,87
# m/s ≈ 0,30 m/s). Hoy el mapa calibrado es lineal EN VELOCIDAD entre 0,091 y
# 0,380 m/s, así que la cuenta es otra:
#
#     u = (v_deseada − V_MIN_MS) / (V_MAX_MS − V_MIN_MS)
#     u = (0,30 − 0,0915) / (0,3806 − 0,0915) = 0,72
#
# Con 34 el robot andaría a 0,19 m/s, no a 0,30. Ver scripts_auxiliares/01.
#
# 🟡 Bajado de 72 a 55 (≈ 0,25 m/s) el 2026-10-01, en el piso: a 0,30 m/s el
# robot recorre 1,4 m en menos de 5 s, y el centrado lateral no llega a
# corregir antes de estar encima del oso (ver KP_ANG). Más despacio hay más
# frames por metro para girar, y la torcedura al frenar es menor. Con este
# techo la rampa de frenado de KP_LIN empieza en ar ≈ 0,12 (~65 cm), no a 1 m.
V_LIN_MAX = 55         # ≈ 0,25 m/s con la calibración vigente
V_ANG_MAX = 60          # ⬜ tope de giro, a calibrar para que no trompee

# Velocidad de rotación en BUSCAR (§6.1). Baja, pero por encima del escalón.
V_ANG_BUSCAR = 35       # ⬜ a calibrar en piso

# BUSCAR alterna barrido con pulsos de avance (nota de §6.1): rotando siempre
# en el mismo punto se barre la misma escena para siempre, y si el oso está
# fuera del alcance visual desde ahí, no aparece nunca. El pulso mueve el punto
# de vista. Que el barrido dure bastante más que el pulso es a propósito: el
# objetivo es cubrir los 360° del lugar antes de cambiarlo.
#
# ✅ MEDIDO en el piso el 2026-09-30: con V_ANG_BUSCAR = 35 da 4 vueltas + 45°
# en 12 s, o sea ~124°/s y una vuelta cada ~2,9 s girando de corrido.
#
# 🔴 Pero girando de corrido la cámara NO VE: a 124°/s la imagen sale tan
# movida que YOLO no reconoció el oso en ningún frame, aunque le pasó por
# delante varias veces (medido 2026-09-30, ya con MJPG). Por eso el barrido va
# A PASOS: gira BUSCAR_PASO_GIRO_S (~40°, contra 60° de campo visual: las vistas
# se solapan), se queda quieto BUSCAR_PASO_MIRAR_S mirando con la imagen nítida,
# y repite. 0,6 s son ~6 frames: alcanzan para confirmar con N_CONFIRMAR = 3
# aunque el primero después de frenar todavía salga movido.
# Con BUSCAR_PASO_MIRAR_S = 0 vuelve el giro continuo.
#
# ✅ PASO MEDIDO CON LA CÁMARA el 2026-10-01 (scripts_pi/piso/paso_giro.py:
# cuánto se corre la escena entre una pausa y la siguiente):
#
#     v_ang  pulso    corrimiento por paso
#      35    0,40 s   390 px = 61 % del ancho de la imagen   ← lo que había
#      35    0,25 s   222 px = 35 %                          ← lo que queda
#      10    0,40 s   247 px = 39 %
#      10    0,25 s   142 px = 22 %
#
# Con 0,40 s cada paso renovaba el 61 % de la imagen. El oso a 1 m ocupa ~20 %
# del ancho y tiene que entrar ENTERO para que YOLO lo reconozca, así que el
# margen era mínimo, y con el retardo del enlace (hasta 0,1 s por punta, ver
# enlace_esp32.mover) algunos pasos lo saltaban: en la Aproximación 1 el robot
# le pasó por delante sin verlo. Con 0,25 s (35 %) el oso queda entero en dos
# pausas seguidas. Los grados dependen de FOV_H_GRAD, que sigue sin medir:
# ~22° por paso si son 60°, ~18° si son 50°.
BUSCAR_PASO_GIRO_S = 0.25
BUSCAR_PASO_MIRAR_S = 0.6
# Duración del barrido antes del pulso de avance: una vuelta entera a pasos.
# Con pasos de 18-22° son 16-20 pasos de 0,85 s → 14-17 s. Se toma el largo:
# pasarse de los 360° no cuesta nada, quedarse corto deja un sector sin mirar
# (con 9,0 s y pasos de 0,4 s el barrido se quedaba en ~260°, medido a ojo).
BUSCAR_GIRO_S = 17.0
BUSCAR_AVANCE_S = 1.0   # ⬜
V_LIN_BUSCAR = 30       # ⬜ avance del pulso — lento, hay que poder frenar

# Frenar el barrido apenas aparece el objetivo, SIN esperar a confirmarlo.
#
# Lo encontró simular_piso.py el 2026-09-30, antes de la demo en piso: girando a
# V_ANG_BUSCAR = 35 (~103°/s con la trocha medida) el oso cruza el campo
# visual en ~6 frames, confirmarlo pide N_CONFIRMAR = 3 SEGUIDOS, y entre el
# primer avistamiento y el frenado el robot sigue girando ~28° — casi la mitad
# del campo visual. Con detección perfecta alcanza (100 % simulado, con la
# trocha medida); si la imagen se barre al girar, cada frame perdido corta la
# racha y el éxito cae al 78-84 %. Frenando al primer avistamiento, los frames
# que confirman se toman con el robot quieto: 96-100 %.
#
# No debilita la confirmación temporal (§5 D6): frenar no cambia de estado.
# Un falso positivo aislado cuesta una pausa de un par de frames, no una
# aproximación.
# ✅ Encendido el 2026-09-30, junto con el barrido a pasos: en el piso la imagen
# movida resultó ser el problema real, no una hipótesis del simulador. Con los
# pasos, esto cubre el caso de que el oso aparezca durante el tramo de giro.
# ✅ Desde el 2026-10-01 vale también para la AMENAZA (salvo en el refractario):
# con la mochila enfrente desde el arranque, el barrido giraba antes de juntar
# los 3 frames y el robot no huía (corrida_20261001_164016).
BUSCAR_FRENAR_AL_VER = True

# Después de una huida, ¿hacia qué lado arranca el barrido?
#
# Con el sentido fijo el robot entra en un ciclo: huye, barre siempre para el
# mismo lado, vuelve a dar con lo mismo, huye otra vez igual. Lo vio el
# usuario operando el robot solo, el 2026-10-02. Con esto en True, al terminar
# cada huida el sentido se sortea: unas veces barre primero la mitad de la
# sala donde está la mochila, y otras la otra mitad.
# No toca los otros dos casos: al arrancar barre a la derecha, y si pierde el
# oso lo busca hacia el lado donde lo vio por última vez.
#
# El sorteo vale cuando al terminar de huir la mochila NO está a la vista. Si
# está (pasó en corrida_20261002_135039: el esquive de la fase 3 gira el robot
# hasta dejarla otra vez en el cuadro), no se sortea: estados.py barre hacia
# el lado contrario al de la mochila, con este parámetro en True o en False.
# ⬜ Sin medir en el piso: es un sorteo, no garantiza salir del ciclo en la
# primera vuelta.
BUSCAR_SENTIDO_AZAR_TRAS_HUIR = True


# ==============================================================================
# 4. Tracción — calibrado y cargado en el ESP32 (HARDWARE.md §0.5)
# ==============================================================================
# Estos valores NO los usa el Pi: viven en firmware/esp32_control/src/main.cpp.
# Se replican acá porque la ley de control necesita saber en qué velocidades
# reales se traduce lo que manda, y para poder loguear en m/s.
#
# Análisis completo en scripts_auxiliares/01_calibracion_motores.ipynb.
V_MIN_MS = 0.0915       # velocidad a u → 0⁺. Medido 2026-08-27
V_MAX_MS = 0.3806       # velocidad a u = 1. Medido 2026-08-27

# Copia INFORMATIVA de la calibración cargada en el firmware (nadie la usa
# desde Python). ✅ Es la de PISO, flasheada el 2026-09-30 (HARDWARE.md §0.6);
# hasta el 2026-10-01 acá seguían figurando los valores de banco de agosto
# (125/112, 238/352, 290/220 y 80 ms), con los que la rueda izquierda no se
# mueve apoyada. Para saber qué tiene cargado el ESP32: `demo.sh firmware`.
PWM_MIN_IZQ, PWM_MIN_DER = 300, 230        # piso de la recta, por rueda
PWM_TOP_IZQ, PWM_TOP_DER = 413, 470        # techo de la recta, por rueda
PWM_BREAKAWAY_IZQ, PWM_BREAKAWAY_DER = 380, 280
BREAKAWAY_MS = 150      # duración del pulso de arranque

DIAM_RUEDA_M = 0.060    # medido 2026-07-24

# Trocha EFECTIVA: la que fija cuánto gira el robot por cada m/s de diferencia
# entre ruedas, ω = (v_izq − v_der) / TROCHA_M. Sólo la usa simular_piso.py.
#
# Son dos números distintos, medidos el mismo día (2026-09-30):
#   - geométrica, con regla entre centros de rueda: 21,5 cm;
#   - efectiva, la que reproduce los giros medidos en el piso: ~0,18 m.
#     (v_ang 35 → 124°/s y v_ang 60 → 165°/s, con las ruedas a la velocidad
#     que confirmó el avance de 57 cm). Las dos dan 2·v/ω ≈ 0,18.
# Hipótesis: la goma (2,7 cm de ancho) apoya sobre su borde interno, y entre
# bordes internos hay 18,8 cm. La estimación de la foto (0,19) predecía mejor
# el giro que la regla: medía otra cosa, pero se parecía más a la que importa.
TROCHA_M = 0.18


def velocidad_real(u):
    """Velocidad en m/s para un comando normalizado u ∈ [0, 1].

    ⚠️ Discontinua en cero por diseño: u > 0 nunca da menos de V_MIN_MS.
    Para parar hay que mandar exactamente 0 (HARDWARE.md §0.5).
    """
    if u <= 0:
        return 0.0
    return V_MIN_MS + (V_MAX_MS - V_MIN_MS) * min(u, 1.0)


def comando_para_velocidad(v_ms):
    """Inversa de velocidad_real(): qué u pedir para una velocidad objetivo."""
    if v_ms <= 0:
        return 0.0
    u = (v_ms - V_MIN_MS) / (V_MAX_MS - V_MIN_MS)
    return min(max(u, 0.0), 1.0)


# ==============================================================================
# 5. Ultrasónico y estados (PLAN.md §6)
# ==============================================================================
DIST_PARADA_CM = 20         # 🟡 umbral de LLEGADA al objetivo (APROXIMAR)
# Umbral para ESQUIVAR: la fase 3 de HUIR y el pulso de avance de BUSCAR, los
# dos tramos que avanzan sin objetivo a la vista. Aparte del de llegada porque
# piden cosas distintas: al oso hay que acercarse; a una pared, no.
# ✅ Medido en el piso el 2026-10-02 con un solo umbral de 20 cm: avanzando a
# 40 queda parado a 16 cm (freno_sonar.py), pero en HUIR va a 60 y al cortar
# no frena, pivotea — el frente barre un arco y la lectura llegó a 16, 11 y
# 12 cm en tres huidas. No tocó, pero sin margen. Con 30 se ganan esos 10 cm.
DIST_OBSTACULO_CM = 30
DIST_INVALIDA = -1          # lo que manda el ESP32 cuando no hay lectura válida

HUIR_RETROCESO_S = 1.5      # ⬜ fase 1
# 🟡 HUIR_GIRO_S: 1,1 → 1,3 el 2026-10-01. El 1,1 salía de "165°/s girando de
# corrido" (medido el 2026-09-30 sobre varias vueltas), pero la fase 2 arranca
# desde la marcha atrás: en la primera huida en el piso (corrida_20261001_165059)
# 1,07 s dieron ~110°, no 180° — el robot terminó de costado y avanzó hacia un
# escritorio. Los 165°/s valen en régimen, no en el primer segundo. Con la fase
# 2 girando para el mismo lado que el retroceso (que ya aporta ~25°) hacen
# falta ~155°. Con 1,3 s (corrida_20261001_165457) giró MÁS de media vuelta,
# visto por el usuario: girando para el mismo lado que el retroceso no hay que
# invertir el sentido y casi no se pierde tiempo en arrancar. Se baja a 1,2.
# ⬜ Sigue siendo a ojo, y depende del lado: girando a la izquierda en marcha
# atrás el robot rota más rápido que a la derecha (asimetría de los motores).
HUIR_GIRO_S = 1.2
HUIR_AVANCE_S = 2.5         # ⬜ fase 3

# Velocidades de cada fase de HUIR (§6.3), en unidades del protocolo.
# El retroceso va más lento que el avance: marcha atrás es a ciegas — el
# ultrasónico mira adelante y la cámara también.
HUIR_V_RETROCESO = 40       # ⬜
HUIR_GIRO_RETROCESO = 25    # ⬜ giro leve durante el retroceso, para no
                            #    quedar de frente a la amenaza
HUIR_V_AVANCE = 60          # ⬜ fase 3: alejarse rápido, ya mirando para otro lado

# Tiempo sordo a la amenaza después de completar una huida.
#
# 🔴 Sin esto las huidas se reencadenan solas, y no por ver la mochila de nuevo:
# por el eco del propio Confirmador. Al terminar la fase 3 el robot ya giró 180°
# y la mochila no está en cámara, pero `M_PERDER` = 5 frames la mantiene
# CONFIRMADA un rato más. La máquina vuelve a BUSCAR, ve la clase todavía
# confirmada y dispara otra huida idéntica, con su alarma incluida.
#
# El piso es el tiempo que tarda el confirmador en soltarla: M_PERDER / FPS.
# ✅ Con el FPS MEDIDO (11,2 del lazo completo, 2026-09-22) ese piso es
# 5/11,2 = 0,45 s, así que los 2,0 s dan 4,4× de margen — más holgado todavía
# que con los 5 FPS supuestos. No hace falta tocarlo. Ojo si alguna vez baja el
# FPS: el piso sube con él, porque lo que manda son FRAMES y no segundos.
HUIR_REFRACTARIO_S = 2.0

# Cuándo el eco del ultrasónico ES el objetivo y no un obstáculo ajeno (§6.2).
# El sensor (un Parallax PING))), HARDWARE.md §9) mira al frente y no distingue
# qué tiene delante, así que hay que cruzarlo con la cámara: si el oso está
# razonablemente centrado y ya ocupa buena parte de la imagen, lo que hay
# enfrente es él.
# Los dos salen de la geometría del cono del sensor contra el campo visual de
# la cámara. SONAR_FRACCION_AREA sigue ⬜: en el piso el robot frena por área
# antes de que el sensor baje de DIST_PARADA_CM, así que no llegó a decidir.
#
# 🟡 SONAR_CENTRADO: 0,35 → 0,7 el 2026-10-02, con el PING))) ya montado. El
# cono del sensor es de unos ±20° y el semicampo de la cámara de 26°
# (FOV_H_GRAD/2): lo que el sensor ve llega hasta |error_x| ≈ 20/26 = 0,77.
# Con 0,35 se le pedía al oso estar mucho más centrado de lo que el sensor
# distingue, y el robot llega descentrado seguido (ex −0,39 y +0,53 al frenar
# en las corridas del 01/10 y del 02/10). En corrida_20261002_103435 quedó a
# 2 cm de dispararse el caso malo: oso grande a la derecha (ex +0,53), 22 cm
# al frente — con 20 cm lo habría tomado por un obstáculo ajeno y habría
# girado a tope para el otro lado, justo al llegar. Frenó por área un ciclo
# antes.
SONAR_CENTRADO = 0.7         # |error_x| por debajo de esto cuenta como centrado

# Cuánto se sigue dando por cierto un obstáculo después de la última lectura
# que lo vio. Girando frente a una pared el eco se pierde de a ratos y aparece
# un "libre" suelto entre dos "pegado" (corrida_20261002_103658: 16 cm, 150,
# 11): sin esto, el robot avanza un ciclo contra la pared. 0,3 s son ~3 ciclos
# del lazo y ~5 disparos del sensor. 🟡 A ojo, por una sola corrida.
SONAR_RETENCION_S = 0.3
SONAR_FRACCION_AREA = 0.6    # fracción de AREA_OBJETIVO que ya es "casi llegando"

BUZZER_OFF, BUZZER_HALLAZGO, BUZZER_ALARMA = 0, 1, 2


# ==============================================================================
# 6. Enlace serie con el ESP32 (PLAN.md §8)
# ==============================================================================
PUERTO_SERIE = "/dev/ttyUSB0"   # ✅ confirmado 2026-09-22: CP2102 de Silicon Labs
BAUDIOS = 115200
TIMEOUT_SERIE_S = 0.05

# El ESP32 frena si no recibe un comando M durante 500 ms. Se manda a 10 Hz
# para tener margen de sobra aunque el lazo de visión baje a 5 FPS.
PERIODO_COMANDO_S = 0.10
WATCHDOG_ESP32_MS = 500

# Cuánto vale un comando antes de considerarse vencido.
#
# El latido de 10 Hz desacopla el enlace del jitter del lazo de visión, pero
# reenviar el último comando para siempre anularía el watchdog del ESP32: si el
# lazo principal se cuelga, el hilo del enlace seguiría diciendo "andá" y el
# robot no frenaría nunca. Por eso el latido sólo repite comandos FRESCOS: si
# la máquina de estados no actualiza el comando en este tiempo, el enlace manda
# M,0,0 por su cuenta.
#
# Tiene que ser holgado contra el peor frame y estrecho contra el watchdog del
# ESP32 (500 ms). ✅ Con el FPS MEDIDO (11,2, o sea 89 ms por ciclo; p95 de
# latencia 89 ms) los 0,40 s dan 4,5× de margen sobre el peor frame y quedan
# 100 ms por debajo del watchdog. Verificado en hardware el 2026-09-22: con el
# programa vivo pero callado, las ruedas frenan en menos de un segundo.
VIGENCIA_COMANDO_S = 0.40


# ==============================================================================
# 7. Métricas (PLAN.md §10)
# ==============================================================================
FPS_OBJETIVO = 5.0          # criterio de aceptación del lazo de visión
