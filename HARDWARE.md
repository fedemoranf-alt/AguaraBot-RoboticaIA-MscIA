# Análisis de alimentación y cableado

> Documento técnico de la etapa de bring-up. Derivado de:
> - `l298.pdf` — ST L298, DS0218 Rev 5 (driver, chip desnudo; se usa el módulo comercial en PCB)
> - Hoja de datos **GM25-370CA** de TT Motor (fabricante) — ver §0
> - `12cpr_encoder_spec_sheet_14.pdf` — ⚠️ **corresponde a otro motor**, ver §3

---

## 0. El motor: GM25-370, 12 V, 350 rpm

Motor de 25 mm con caja reductora metálica y motor de base tamaño 370. Datos de la hoja del fabricante (TT Motor, familia GM25-370CA):

### 0.1 Motor de base a 12 V

| Parámetro | TRK-370CA-15360 | TRK-370CA-12560 |
|---|---|---|
| Tensión nominal | 12 V | 12 V |
| Velocidad sin carga | 5600 rpm | 3700 rpm |
| Corriente sin carga | 25 mA | 20 mA |
| Velocidad nominal | 4800 rpm | 3000 rpm |
| Corriente nominal | **160 mA** | 90 mA |
| Potencia de salida | 1,18 W | 0,62 W |
| Par de arranque | 186 g·cm | 125 g·cm |
| **Corriente de stall** | **1,06 A** | 0,46 A |

> La variante de 6 V de la misma familia tiene stall de 2,1 A. Al ser de 12 V, la corriente es la mitad para la misma potencia — buena noticia para el L298 (ver §2.2).

### 0.2 Relación de reducción — a verificar

Las reducciones estándar de la familia son 4, 10, 21, 34, 45, 47, 78, 103, 130, 172, 227, 378 y 499. Con el motor de base a 5600 rpm, **ninguna da exactamente 350 rpm** (la de 10:1 da 510 rpm y la de 21:1 da 245 rpm).

Esto significa que el motor es de otro fabricante de la misma familia genérica — los "GM25-370" los hace mucha gente con bobinados y reducciones distintas. Los números de arriba sirven como referencia de orden de magnitud, no como dato exacto del motor que tenés.

**Cómo medir la reducción real (2 minutos, sin instrumental):** marcar el eje de salida con cinta, alimentar el motor a baja tensión, y contar cuántas vueltas da el eje trasero del motor por cada vuelta del eje de salida. O directamente: con el encoder conectado, contar pulsos por vuelta completa del eje de salida.

**Completar cuando se sepa:**

| Parámetro | Valor medido |
|---|---|
| Relación de reducción | ⬜ |
| Corriente sin carga (real, con ruedas al aire) | **~115 mA por motor** (2026-07-24) |
| Corriente de stall (real) | ⬜ |
| Diámetro de rueda | **60 mm** (2026-07-24) |

### 0.3 El motor es demasiado rápido para el lazo de visión — recalculado con medidas reales

> **Revisado 2026-07-24 con datos del bring-up.** La versión original de esta sección suponía rueda de 65 mm y los 350 rpm plenos de la hoja de datos. Las dos suposiciones eran pesimistas.

Datos medidos que entran en el cálculo:

| Dato | Valor medido |
|---|---|
| Diámetro de rueda | **60 mm** → circunferencia 18,85 cm |
| Tensión en bornes del motor al 100 % PWM | **9,5 V** (no 12 — ver §2) |
| Velocidad estimada del eje | 350 × 9,5/12 ≈ **277 rpm** |

**Velocidad real al 100 % de PWM: 0,87 m/s**, contra los 1,19 m/s que estimaba la versión anterior. La rueda más chica y la caída del L298 se acumulan a favor.

Sigue siendo demasiado rápido: con la inferencia a 5 FPS (`PLAN.md` §10) son 17 cm entre frame y frame. El objetivo de ~0,3 m/s (6 cm entre frames) se mantiene.

**Consecuencia de diseño, corregida:**

```
0,30 m/s / 0,87 m/s = 34 %  →  PWM 88
```

`v_max` de `PLAN.md` §7 pasa de **0,25 a 0,34**. El 0,25 anterior era demasiado restrictivo y además colisionaba con el `v_min` de la rueda izquierda (ver §0.4).

> ⚠️ Los 0,87 m/s son **sin carga, ruedas al aire**. Con el robot apoyado la velocidad va a ser algo menor. Verificar empíricamente cronometrando 1 m en el piso antes de cerrar los parámetros del control.

Efecto secundario positivo que se mantiene: trabajando en el tercio inferior del rango de PWM las corrientes son bajas y el L298 queda holgado.

### 0.4 ⚠️ Los dos motores no arrancan al mismo PWM

Medido en el bring-up (2026-07-24), con la rampa del firmware de prueba:

| Rueda | PWM de arranque | Rango útil hasta `v_max` = 88 |
|---|---|---|
| Derecha | **32** | 56 cuentas |
| Izquierda | **64** | **24 cuentas** |

Una asimetría de 2:1 en la fricción de arranque. Consecuencias:

1. **`v_min` deja de ser un escalar.** `PLAN.md` §7 lo definía como un solo número; tiene que pasar a ser **uno por rueda**.
2. **La compensación de zona muerta pasa a ser obligatoria**, no opcional: el comando normalizado `u ∈ (0, 1]` se mapea a `pwm = v_min_rueda + (v_max − v_min_rueda) · u`. Sin esto, a comandos bajos la derecha gira y la izquierda no, y el robot se va de trompa.
3. **La rueda izquierda queda con un cuarto de la resolución** de la derecha. Es el argumento más fuerte a favor de cerrar el lazo con los encoders (`PLAN.md` §5 D5, hoy marcados como extensión opcional): en lazo abierto la marcha recta a baja velocidad va a curvarse.

**Causa aislada (2026-07-24).** Se intercambiaron los dos motores entre canales del L298 y **el `v_min` alto viajó con el motor**. El driver, el firmware y el cableado quedan descartados: es una característica del motor, probablemente fricción del reductor. Se acepta como dato de hardware y no se persigue más.

#### El robot igual puede andar lento

Que un motor no *arranque* por debajo de PWM 64 no significa que no pueda *girar* por debajo de 64. Cuatro palancas, todas de firmware y ninguna con costo de hardware:

**A. Subir la resolución del PWM de 8 a 10 bits.** Las "24 cuentas de rango" son un artefacto de la resolución, no una limitación física. Físicamente la banda va del 25 % al 34 % de la velocidad máxima: una relación de 1,36:1, perfectamente utilizable. Lo que falta no es rango, es granularidad.

| Resolución | `v_min` izq. | `v_max` | Cuentas útiles |
|---|---|---|---|
| 8 bits (actual) | 64 | 88 | **24** |
| 10 bits | 256 | 352 | **96** |
| 12 bits | 1024 | 1408 | **384** |

El LEDC del ESP32 a 1 kHz admite hasta 16 bits (80 MHz / 1 kHz). Cambio: `PWM_RES_BITS` 8 → 10 y `PWM_MAX` 255 → 1023. Obliga a remedir los `v_min` en la escala nueva.

**B. Medir el `v_min` cinético, no el estático.** Los 32/64 son el umbral **desde parado**, gobernado por fricción estática. El umbral para **seguir girando** es menor. Método: arrancar la rueda a PWM 100, después bajar de a poco y anotar dónde se detiene. Ese es el número que importa para la ley de control, y va a estar bastante por debajo de 64.

**C. Pulso de arranque (*breakaway*).** Al pasar de reposo a movimiento, aplicar 30–50 ms al PWM de arranque y recién después caer al duty objetivo. Rompe la fricción estática y deja al motor operando por debajo de su propio umbral de arranque. Es técnica estándar y es puro firmware.

**D. Bajar la frecuencia de PWM.** Con ~11 Ω de bobinado y unos pocos mH, la constante de tiempo eléctrica es τ ≈ 0,1–0,3 ms. A 1 kHz el pulso de encendido con duty bajo dura ~0,25 ms, o sea del orden de τ: **la corriente no llega a establecerse** y el par de arranque se resiente. A 100–200 Hz el pulso es diez veces más largo, la corriente se desarrolla del todo y el par de arranque mejora. Es un cambio de una línea (`PWM_FREQ_HZ`) y vale la prueba. Contra: más ruido audible y marcha más áspera. El `f_C` de 25 kHz del datasheet (§1) es un techo, no un piso.

**Residual que no se va con nada de esto:** la rueda izquierda mantiene menos resolución de control que la derecha, y en lazo abierto la marcha recta a baja velocidad va a curvarse. La corrección propia es cerrar el lazo con los encoders (`PLAN.md` §5 D5).

> **Precisión de la medición:** la rampa del firmware de prueba avanza de a 15 cuentas, así que 32 y 64 tienen ±15 de incertidumbre. Conviene remedir con pasos finos —y en cinético, según (B)— antes de fijar los parámetros del Día 5.


### 0.5 ⚠️ Compensar solo el piso no alcanza: `v_max` también es por rueda

Observado el 2026-08-27, con el firmware de control ya andando: **con la compensación de zona muerta activa y comando al 20 %, la rueda derecha gira bastante más lento que la izquierda.**

Los duty que aplica la fórmula `pwm = v_min + (v_max − v_min)·u` en ese punto:

| Rueda | `v_min` | Cuenta | Duty a 20 % |
|---|---|---|---|
| Izquierda | 256 | `256 + 96×0,20` | **275** |
| Derecha | 128 | `128 + 224×0,20` | **172** |

La izquierda recibe 60 % más duty que la derecha, y la derecha es justamente la que *menos* fricción tiene. La compensación no corrige de menos: **corrige de más**. Hay dos causas encadenadas.

**Causa 1 — los `v_min` cargados son los estáticos, no los cinéticos.** La fórmula asume velocidad cero en `v_min`, y eso es falso: `v_min` es el duty al que la rueda se despega *desde parado*. Una rueda ya en movimiento a ese duty gira a una velocidad real y apreciable. Como el umbral estático de la izquierda es el doble, la fórmula la lanza a una velocidad de arranque mucho mayor. Es exactamente la palanca B de §0.4, que había quedado diferida al Día 5.

**Causa 2 — la fórmula iguala los extremos del *duty*, no los de la *velocidad*.** Cuando `u = 1` las dos ruedas reciben el mismo `v_max`, y no hay ninguna razón para que a ese duty corran igual. Compensar el piso arregla el arranque y no arregla la pendiente.

#### Medición (2026-08-27) — y la hipótesis que la medición desmintió

Ventanas de 10 s a duty crudo (comando `V`), contando vueltas del eje de salida:

| duty | vueltas izq. | vueltas der. |
|---|---|---|
| 141 | 0 | 0 |
| 211 | **16** | 11 |
| 282 | **27** | 16 |
| 352 | **35** | 20 |

Ajuste lineal `vueltas/10 s = k · (duty − piso)`, que reproduce los seis puntos con menos de 1 vuelta de error:

| Rueda | `k` (vueltas/10 s por cuenta) | Piso extrapolado |
|---|---|---|
| Izquierda | **0,1348** | 89 |
| Derecha | **0,0639** | 36 |

🔴 **La izquierda da 2,11 veces más velocidad por cuenta de duty que la derecha.** Es más rápida en *todos* los puntos medidos, no solo abajo.

Esto **desmiente la hipótesis** con la que se había escrito esta sección. Se había supuesto que los dos motores eran iguales y solo diferían en fricción, y de ahí se dedujo que la rueda de menor fricción —la derecha, la que arranca a 128— iba a ser la más rápida. Es exactamente al revés. La diferencia no es de fricción sino de **constante del conjunto motor + reductor**, y afecta a la pendiente, no al offset.

#### Los dos motores probablemente no tienen la misma reducción

La combinación de hechos es peculiar y una sola causa los explica a los dos:

| Hecho | Rueda izquierda | Rueda derecha |
|---|---|---|
| Cuesta más arrancar | **sí** (estático 256) | no (estático 128) |
| Anda más rápido | **sí** (2,11×) | no |

Un reductor más "libre" daría *menos* umbral de arranque y *más* velocidad; acá van al revés. Lo que sí explica las dos cosas a la vez es una **relación de reducción menor en la izquierda**: menos reducción → eje de salida más rápido *y* menos par en la rueda, o sea más duty necesario para vencer la misma fricción de arranque. La relación entre reducciones sería del orden de **2,1 : 1**.

Encaja además con el bring-up: al intercambiar los motores entre canales del L298, la propiedad viajó con el motor (§0.4).

Extrapolando el ajuste a duty 1023 (fuera del rango medido, solo referencial): izquierda ~756 rpm, derecha ~378 rpm en el eje de salida. **La derecha es consistente con la chapa de "GM25-370, 350 rpm"; la izquierda no.** La identificación del motor de §0 vale para una de las dos unidades.

**Cómo confirmarlo:** mirar la etiqueta de cada motor — estos suelen traer la reducción impresa o un sufijo distinto de parte. No cambia el plan, pero sí tiene dos consecuencias: la velocidad calculada de §0.3 vale por rueda y no para el robot, y si algún día se agrega odometría, **las cuentas por metro son distintas para cada rueda**.

#### Calibración cargada en el firmware

La rueda **lenta manda**: se queda en 352 y la rápida se baja hasta dar las mismas vueltas.

| Constante | Izquierda | Derecha |
|---|---|---|
| `PWM_MIN_*` (piso de la recta) | **125** | **112** |
| `PWM_BREAKAWAY_*` (umbral estático) | **290** | **220** |
| `PWM_TOP_*` (`v_max` por rueda) | **238** | **352** |

Con esos valores las dos ruedas siguen la misma recta en todo el rango, con menos de 1 % de error:

| `u` | duty izq. → vueltas | duty der. → vueltas |
|---|---|---|
| 0,2 | 148 → 7,93 | 160 → 7,90 |
| 0,6 | 193 → 14,02 | 256 → 14,03 |
| 1,0 | 238 → 20,11 | 352 → 20,16 |

Rango útil resultante: **0,091 a 0,380 m/s**, o sea 4,2:1 — entre 1,8 y 7,6 cm de avance entre frames a 5 FPS. Ambos extremos dentro del presupuesto del lazo de visión.

#### Los umbrales estáticos del bring-up estaban bajos

Como efecto secundario, las ventanas de 10 s acotan el umbral de arranque mucho mejor que la rampa de 15 cuentas del bring-up, porque cada corrida arranca desde parado:

| Rueda | Arranca sola | Umbral estático |
|---|---|---|
| Izquierda | no a 211, **sí a 282** | (211, 282] |
| Derecha | no a 141, **sí a 211** | (141, 211] |

Los valores del bring-up eran 256 y 128 (en 10 bits), los dos por debajo del techo del intervalo — el de la derecha, muy por debajo. **Con `PWM_BREAKAWAY_RIGHT` en 128 el pulso de arranque no habría despegado la rueda**, o sea que a comando chico no arrancaba. Corregidos a 290 y 220. Se pueden bajar después si el tirón de arranque molesta.

#### 🔴 El piso de la recta NO es el corte con cero

Los `PWM_MIN_*` se cargaron primero con el **corte con cero** del ajuste lineal (89 y 36). Fue un error, y la rampa `K` lo destapó midiendo el duty de calado directo:

| Rueda | Corte con cero de la recta | Duty de calado medido (`K`) | Diferencia |
|---|---|---|---|
| Izquierda | 89 | ~106 | +17 |
| Derecha | 36 | **~98** | **+62** |

El corte con cero es una extrapolación matemática de una recta ajustada entre duty 211 y 352. **La rueda se planta mucho antes de llegar ahí**, porque cerca de velocidad cero la fricción crece más que lineal. La recta describe bien el régimen medido y no dice nada sobre dónde se cala.

Con los cortes con cero cargados como piso, la rueda derecha quedaba **por debajo de su duty de calado para todo `u < 0,22`**: a comando chico arrancaba con el pulso de breakaway y se plantaba. El síntoma no había aparecido en la prueba porque se probó a `u = 0,2`, que da duty 99 — justo en el borde.

**Lo que va en el piso es el duty de la mínima velocidad que las dos ruedas pueden sostener.** Medido:

| Rueda | Velocidad mínima sostenible |
|---|---|
| Izquierda | 2,6 vueltas/10 s (0,049 m/s) |
| Derecha | **4,5 vueltas/10 s (0,084 m/s)** ← manda esta |

La derecha no puede ir más lento, así que fija el piso del par. De ahí salen los 125 / 112, con margen sobre el calado medido (19 y 14 cuentas).

⚠️ **Consecuencia para la ley de control:** `u > 0` garantiza al menos **0,091 m/s**. No hay arranque suave desde cero — hay un escalón. Para parar, el Pi tiene que mandar exactamente 0, no un valor chico.

**Consecuencia — la misma lección de §0.4, un nivel más arriba:**

> `v_min` dejó de ser un escalar en el bring-up. Ahora **`v_max` también deja de ser un escalar.**

Cada rueda necesita su propia recta, con piso *y* techo propios. Se elige como velocidad máxima común la de la rueda más lenta a su tope, y se baja el techo de la otra hasta que dé la misma velocidad real. El firmware ya tiene `PWM_TOP_LEFT` y `PWM_TOP_RIGHT` separados; hoy los dos valen 352, o sea sin corregir.

#### Procedimiento de medición

En el firmware hay un modo de calibración (`K`, `V`, `C`) que trabaja sobre **duty crudo**, sin compensación ni pulso de arranque, porque acá se caracteriza el motor y no la ley de control. Procedimiento en [RUNBOOK.md](RUNBOOK.md) §"Calibración".

| Medición | Rueda izq. | Rueda der. | Fecha |
|---|---|---|---|
| `v_min` estático (bring-up, ±15 en 8 bits) | 256 | 128 | 2026-07-24 |
| rpm eje de salida a duty 352 | **210** | **120** | 2026-08-27 |
| pendiente `k` (vueltas/10 s por cuenta) | **0,1348** | **0,0639** | 2026-08-27 |
| `v_max` corregido | **238** | **352** | 2026-08-27 |
| corte con cero de la recta (extrapolado) | 89 | 36 | 2026-08-27 |
| **duty de calado** medido con `K` | **~106** | **~98** | 2026-08-27 |
| `PWM_MIN_*` cargado (piso comun + margen) | **125** | **112** | 2026-08-27 |

#### Cuándo esto igual no alcanza

La calibración en lazo abierto vale **solo para las condiciones en que se midió**. Si la desviación cambia con la batería descargándose, con el tipo de piso o con peso encima, el arreglo es cerrar el lazo con encoders (`PLAN.md` §5 D5). Antes no: un PID sobre una planta descompensada arranca peor que sobre una calibrada.

#### Dónde duele realmente

Vale acotar el alcance del problema antes de invertirle tiempo. En `APROXIMAR` la asimetría **casi no importa**: la cámara cierra el lazo de rumbo frame a frame (`v_ang = Kp·error_x`), así que una trayectoria curvada se corrige sola. Donde duele es en los estados **sin realimentación visual**: `BUSCAR` rotando en el lugar, y la fase 3 de `HUIR` avanzando a ciegas.

### 0.6 🔴 En el piso, la calibración al aire no alcanza (2026-09-30)

**Primera vez apoyado en el piso: la rueda izquierda se calaba con cualquier comando.** Pitaba, que es el PWM de 1 kHz sobre un motor quieto, y no giraba ni con `v_ang` = 100. Con una secuencia de escalones por el protocolo se vio que sólo giraba la derecha, pivoteando sobre la izquierda.

**Por qué justo la izquierda.** Es la de reducción ~2,1 veces menor (§0.5), o sea la que da **la mitad de par en la rueda**. Y la calibración al aire, para igualar velocidades, le daba además el **menor** duty: techo 238 (23 %) contra 352 (34 %). Sin carga alcanzaba; con el peso del robot, no. El párrafo de arriba lo advertía —*la calibración en lazo abierto vale sólo para las condiciones en que se midió*— y aun así el firmware llegó al piso con los números del banco.

**Medición en el piso** con el modo `C` (duty crudo), una rueda por vez, con el robot pivoteando sobre la otra. Pivotear es más exigente que andar derecho, así que los valores son conservadores:

| | Izquierda | Derecha |
|---|---|---|
| Arranca desde parado | entre 300 y 350 | entre 200 y 250 |
| Sigue girando hasta (rampa descendente, 1 s por escalón) | entre 260 y 290 | entre 190 y 220 |
| Calado al aire (§0.5, para comparar) | ~106 | ~98 |

**Modelo con que se armaron los valores nuevos:** la carga **suma un escalón de duty** (hace falta corriente para dar par) y **no cambia la pendiente** (la velocidad la fija la fuerza contraelectromotriz). Entonces piso y techo suben **la misma cantidad** en cada rueda, y se conserva el span de la calibración al aire, que es el que iguala las velocidades:

| Constante del firmware | Al aire (2026-08-27) | En el piso (2026-09-30) |
|---|---|---|
| `PWM_MIN_LEFT` / `_RIGHT` | 125 / 112 | **300 / 230** |
| `PWM_TOP_LEFT` / `_RIGHT` | 238 / 352 | **413 / 470** (+175 / +118) |
| `PWM_BREAKAWAY_LEFT` / `_RIGHT` | 290 / 220 | **380 / 280** |
| `BREAKAWAY_MS` | 80 | **150** |

**Verificación, con los comandos que usa el comportamiento:**

- Sin pitidos. **Avance derecho**, y `M,30,0` 1,5 s + `M,72,0` 1 s = **57 cm, exactamente lo predicho** con las velocidades medidas al aire. El modelo se sostiene: en el piso, el robot recuperó el rango 0,091–0,380 m/s y las dos ruedas siguen iguales.
- **Giro:** `v_ang` 35 → **~124°/s** (4 vueltas + 45° en 12 s) y `v_ang` 60 → **~165°/s** (4 vueltas + 45° en 9 s). Es ~20 % más rápido que lo predicho con la trocha de 21,5 cm entre centros. La trocha **efectiva** que reproduce los dos giros es **~0,18 m**; la hipótesis es que la goma (2,7 cm de ancho) apoya sobre su borde interno.

**Cómo se flashea ahora** (el ESP32 queda enchufado al Pi): se compila en la PC con `pio run`, se copian los 4 binarios al Pi, y se graba desde el Pi con esptool **con los 12 V desenchufados**, porque durante la grabación los pines del ESP32 flotan. El procedimiento está en [RUNBOOK.md](RUNBOOK.md) §"Flashear desde el Pi".

### 0.7 🔴 El ruido de los motores rompe la imagen de la webcam (2026-09-30)

Con la tracción ya recalibrada, el robot **no vio al oso en ninguna de dos corridas**: cero detecciones en cientos de frames. Un frame tomado con el robot quieto mostró la causa: **la imagen llegaba en franjas**, pedazos de frames distintos mezclados. Es lo que pasa cuando se pierden paquetes USB y el driver rellena con restos del frame anterior. Hubo además lecturas de cámara de hasta 2,2 s.

Medido con `scripts_pi/piso/diag_camara.py`, en el mismo minuto y con la misma escena:

| Formato | Motores | Rayado¹ | FPS | Lectura más lenta |
|---|---|---|---|---|
| YUYV (sin comprimir, el de siempre) | quietos | 0,02 | — | 36 ms |
| YUYV | girando | **0,12** (máx 0,25) | **2,3** | **1972 ms** |
| **MJPG** (comprimido) | girando | **0,01** (máx 0,07) | **10,7** | 61 ms |

¹ Fracción de bordes entre filas consecutivas con un salto grande de brillo: una imagen sana tiene pocos, una en franjas, muchos.

**Lectura:** el ruido que meten los motores —más corriente que nunca, ahora que trabajan con carga y el doble de duty— corrompe la transmisión USB. YUYV ocupa casi todo el ancho de banda del USB 2.0 y no tolera pérdidas. **MJPG transmite ~10 veces menos datos** y un paquete perdido daña un bloque del JPEG, no el frame entero. Quedan avisos de libjpeg (`Corrupt JPEG data`), que son frames con algún bloque dañado.

**Lo que se hizo:**
- `FORMATO_CAMARA = "MJPG"` en `config.py`.
- **Webcam y ESP32 en controladores USB distintos del Pi 5**: webcam en el puerto **azul de abajo** (bus 1) y ESP32 en el **negro de abajo** (bus 3). Antes compartían controlador. Esto solo no alcanzó, pero no hay razón para volver atrás.
- `demo.sh` filtra los avisos de libjpeg para que no tapen la pantalla.

**Lo que no se hizo, y ataca la causa en vez del síntoma:**
- capacitores cerámicos de 100 nF entre los bornes de cada motor (y de cada borne a la carcasa);
- una ferrita en el cable de la webcam;
- cables de motor trenzados, lejos del cable de la cámara.

La **hipótesis del camino del ruido**: el ESP32 comparte GND con el L298 y está conectado por USB al Pi, así que el ruido de los motores tiene un camino directo hasta el bus USB. No se verificó.

**La otra mitad del problema era óptica, no eléctrica.** Ya con MJPG, girando a 124°/s **la imagen sale tan movida que YOLO no reconoció el oso en ningún frame**, aunque se lo ve borroneado en la grilla. Es el riesgo que el simulador había anticipado a la mañana, y en el piso resultó peor: no "algunos frames perdidos", sino todos. La solución va en el comportamiento, no en el hardware: `BUSCAR` pasó a girar **a pasos** (gira ~40°, se queda quieto 0,6 s mirando, repite). Ver `config.BUSCAR_PASO_*` y [PLAN.md](PLAN.md) §13, Día 13.

### 0.8 🔴 La imagen también se rompe con los motores PARADOS, de a ratos (2026-10-01)

El título de §0.7 dice "el ruido de los motores", y al día siguiente resultó ser sólo una parte. La primera corrida de la segunda jornada en el piso terminó **sin una detección en 242 frames**, y buscando por qué apareció esto: con el robot **quieto**, mirando al oso a 1 m, los frames MJPG llegaban con **franjas grises horizontales** — tramos del JPEG perdidos, que libjpeg rellena con gris hasta el siguiente marcador de reinicio.

Medido con `scripts_pi/piso/franjas_quieto.py` (no toca el ESP32 ni los motores). "Rotos" = más del 10 % de las filas en franja:

| Hora | Condición | Frames rotos | Frames con oso |
|---|---|---|---|
| 15:18 | sobre el escritorio, 12 V desenchufados | 0 | todos (conf. 0,91) |
| 15:28 | piso, 12 V enchufados, motores parados | **69 de 71** | 4 de 71 |
| 15:30 | ídem | 5 de 48 | 45 de 48 |
| 15:32 | ídem | **41 de 50** | 14 de 50 |
| 15:40 | **12 V desenchufados** | **48 de 72** | 26 de 72 |
| 15:41 | ídem | 18 de 69 | 60 de 69 |
| 15:43 | sin 12 V, **sin YOLO** (sólo captura) | 9 de 82 | — |
| 15:43 | sin 12 V, con YOLO, diez segundos después | **71 de 71** | 14 de 71 |
| 15:52 | 12 V enchufados, 60 s seguidos | **0 de 606** | 606 de 606 |

Después de las 15:50 no volvió a aparecer en el resto de la tarde: **0 frames con franjas en las ocho corridas siguientes (2104 frames)**, y 10 de 889 en la novena, en dos ráfagas de medio segundo que no afectaron la corrida (y que podrían ser una pared gris de cerca: la medida cuenta filas grises uniformes, no paquetes perdidos).

**Lo que las mediciones descartan:**

- **El PWM de los motores**: pasa con los motores parados.
- **La fuente de 12 V**: con la UPS desenchufada sigue igual.
- **La carga del procesador**: hay frames rotos capturando sin YOLO, y con YOLO una medición salió limpia y la siguiente rota entera.
- **La alimentación del Pi**: `get_throttled = 0x0` siempre, `EXT5V_V` entre 4,97 y 5,14 V.
- **El ancho de banda USB**: la webcam negocia el *alternate setting* 24 (el máximo, 3×1024 bytes por microframe) y los JPEG de esta escena pesan ~100 kB, o sea ~25 Mbit/s contra ~196 disponibles.
- **La cámara en sí**: en los ratos buenos entrega 150 de 150 frames sanos (`franjas_crudo.py`, captura con `v4l2-ctl`).

**Lo que sí se sabe:** son **paquetes USB isócronos perdidos**. Con la traza del driver encendida (`echo 128 | sudo tee /sys/module/uvcvideo/parameters/trace`), en los ratos malos el kernel registra cientos de `uvcvideo: USB isochronous frame lost`, y en los buenos ninguno. También aparecieron timeouts de control (`Failed to set UVC probe control : -110`) que dejaron colgadas dos capturas.

**Lo que NO se sabe: la causa.** Quedan en pie el cable o el conector de la webcam (un falso contacto encaja con que vaya y venga), y el límite de corriente de los puertos USB: con el cargador portátil el Pi informa `usb_max_current_enable=0`, o sea 600 mA para todos los puertos, y la webcam declara 500 mA y el ESP32 100 mA — justo el total. Ninguna de las dos se probó: el problema desapareció solo antes de poder aislarlo, y el usuario confirmó que no movió ningún cable.

**Lo que se hizo, que no arregla la causa pero la vuelve visible:** cada corrida de `main.py` mide ahora, frame por frame, la fracción de filas en franja (`vision.franjas()`, 1,7 ms por ciclo) y la guarda en la columna `franjas` del CSV; `analizar_corrida.py` la resume en una línea y avisa "CÁMARA A CIEGAS" si más del 20 % de los frames están muy dañados. Así una corrida que "no vio el oso" dice por sí sola si la cámara estaba rota.

**Pendiente, por orden de costo:** reasentar o cambiar el cable de la webcam, `usb_max_current_enable=1` en `/boot/firmware/config.txt` (el cargador da 3 A; sube el límite USB a 1,6 A), y la ferrita y los capacitores de §0.7. El procedimiento paso a paso, con cómo deshacer cada cosa, está en [RUNBOOK.md](RUNBOOK.md), **Paso 24**. Para medir en 6 segundos si la imagen está sana: `bash ~/TPF/scripts_pi/demo.sh imagen`.

Las imágenes están en `media/2026-10-01_imagen_rota/`, con un README que dice qué es cada una.

🟡 **2026-10-02: cero franjas en seis corridas (3675 frames), pero sin aislar la causa.** No se hizo el Paso 24 en orden: ese día cambiaron **dos cosas a la vez**, y cualquiera de las dos lo explica.

- **El enchufe de la webcam se reinsertó.** Al bajar el robot al piso se había soltado del todo: el Pi no veía la cámara (`lsusb` sólo mostraba el ESP32) y la primera corrida falló con "No se pudo abrir la cámara USB". Un conector que se suelta entero es el mismo que el día anterior pudo haber hecho falso contacto.
- **Las baterías estaban recién cargadas.** A la mañana, con las baterías puestas en sus cargadores, el Pi marcaba **bajo voltaje en reposo**: `get_throttled = 0x50005` de a ratos y `EXT5V_V` entre 4,75 y 4,80 V. Después de desconectarlas de los cargadores y reiniciar: `0x0` y 5,10 V en todas las corridas. (El día de las franjas, en cambio, las mediciones daban `0x0` y 4,97–5,14 V; por eso la alimentación figura arriba entre lo descartado. Sigue descartada para ese día, no en general.)

Lo que queda como recomendación práctica: **antes de cada corrida, `demo.sh chequeo`** (ve si la cámara está) **y `demo.sh imagen`** (ve si llega sana), y no correr con las baterías enchufadas al cargador.

⬜ Sigue pendiente el Paso 24 hecho en orden, una cosa por vez, si las franjas vuelven.

### 0.9 El robot se tuerce solo al acelerar y al frenar (2026-10-01)

Con las dos ruedas calibradas para ir a la misma velocidad **en régimen** (§0.5 y §0.6), el robot igual no avanza derecho mientras **cambia** de velocidad. Salió del registro de la primera aproximación completa (`corrida_20261001_160226`), mirando cómo se corría el oso en la imagen en los tramos en que la ley de control **no pedía ningún giro** (`v_ang` = 0, dentro de la zona muerta):

| Tramo | Comando | Lo que hizo el oso en la imagen | Giro del robot |
|---|---|---|---|
| Acelerando y a velocidad constante (0,5 a 1,5 s) | `v_lin` = 72, `v_ang` = 0 | se corrió a la derecha (`ex` de −0,05 a +0,07) | **~3,5°/s a la izquierda** |
| Frenando (1,7 a 2,5 s) | `v_lin` de 71 a 49, `v_ang` = 0 | se corrió a la izquierda (`ex` de +0,05 a −0,08), aun descontando que el ángulo crece al acercarse | **~5°/s a la derecha** |

Las cifras son estimaciones sobre **una** corrida: del error lateral en la imagen, con un campo visual de ~52° y la distancia sacada del tamaño aparente. El sentido, en cambio, se repitió en todas las aproximaciones del día: al frenar, el oso termina a la izquierda del centro (`ex` ≈ −0,3, unos 9°).

**Lectura (hipótesis, sin verificar):** es la misma asimetría de §0.5, ahora en la dinámica. La rueda izquierda tiene la mitad de reducción: le cuesta más arrancar, así que al acelerar se atrasa (el robot se va a la izquierda), y al cortar la potencia la frena menos su caja, así que sigue rodando más (el robot se va a la derecha).

**Consecuencias, ya incorporadas:**

- La ley de giro tiene que vencer una perturbación de ~5°/s, además de centrar. Con `KP_ANG` = 0,3 no alcanzaba cuando el oso estaba a la izquierda (el lado contra el que hay que pelear al frenar) y sí cuando estaba a la derecha. Quedó en 0,5 ([PLAN.md](PLAN.md) §13, Día 14).
- El **giro realizado mientras avanza es más o menos la mitad** del que predice la trocha efectiva de 0,18 m, que se midió girando en el lugar (§0.6). Otra trocha más: la de la regla (21,5 cm), la de pivotar (18 cm) y la de doblar andando (del orden del doble).
- Girando en **marcha atrás**, el robot rota más rápido hacia la izquierda que hacia la derecha: en la fase 1 de `HUIR`, con el mismo comando, la mochila se salió de la imagen girando a la izquierda y apenas llegó a medio camino girando a la derecha. Por eso `HUIR_GIRO_S` depende del lado.

**Lo que lo resolvería de fondo:** un lazo de velocidad por rueda con los **encoders** (segunda versión, [PLAN.md](PLAN.md) §5 D5). Era el caso previsto en §0.5, "Cuándo esto igual no alcanza": la calibración en lazo abierto empareja las velocidades de régimen, no las transiciones.

---

## 1. Lo que dice el datasheet del L298 (datos duros)

Extraído de las tablas 1 y 4 del DS0218 Rev 5:

| Parámetro | Símbolo | Valor | Consecuencia práctica |
|---|---|---|---|
| Tensión de potencia | V_S (pin 4) | máx. 46 V oper. / 50 V abs.; mín. = V_IH + 2,5 V | Amplio margen; el problema no es el techo |
| Tensión de lógica | V_SS (pin 9) | 4,5 V mín — **5 V típ** — 7 V máx | La lógica del chip va a 5 V, no a 3,3 V |
| Corriente por canal | I_O | **2 A DC**, 2,5 A repetitivo, 3 A pico no repetitivo | Suficiente para estos motores |
| **Caída total en el puente** | **V_CEsat** | **1,80 V mín – 3,2 V máx @ 1 A**; hasta **4,9 V @ 2 A** | ⚠️ **El punto crítico — ver §2** |
| Consumo en reposo | I_S / I_SS | 50–70 mA / 24–36 mA | Despreciable frente a los motores |
| Umbral de entrada alto | V_IH | **mín. 2,3 V** | ✅ **El ESP32 a 3,3 V maneja las entradas directo, sin level shifter** |
| Disipación total | P_tot | 25 W (con encapsulado a 75 °C) | Teórico; el límite real es térmico, ver §2.2 |
| Resistencia térmica | Rth j-amb | 35 °C/W (Multiwatt15 sin disipador) | Con 1,5 W → +52 °C sobre ambiente |
| Frecuencia de conmutación | f_C | 25 kHz típ / 40 kHz máx | PWM de 1–10 kHz es terreno seguro |

---

## 2. El problema central del L298: la caída de tensión

El L298 es un driver **bipolar** (no MOSFET). Sus transistores de salida no saturan a cero: entre el lado alto y el lado bajo se pierden **entre 1,8 V y 3,2 V** a 1 A.

### ⚠️ Medición real (2026-07-24) — 2,5 V, no 1,4 V

| | Valor |
|---|---|
| V_S en la fuente | 12,0 V (no cae al arrancar los motores) |
| Tensión en bornes del motor al 100 % PWM | 9,5 V |
| **Caída real del puente** | **2,5 V** |
| Corriente por canal en ese punto | ~115 mA |

**La versión anterior de esta sección estimaba 1,4–1,6 V y estaba equivocada.** El error conceptual vale la pena registrarlo porque es genérico:

> Se supuso que a 115 mA la caída escalaría hacia abajo desde el valor a 1 A. **No lo hace.** La etapa de salida del L298 es **Darlington**: su V_CEsat tiene un componente fijo de juntura base-emisor (~0,7 V por transistor, dos en serie entre V_S y el motor) que está presente sin importar la corriente. Un MOSFET con R_DS(on) sí escala linealmente con la corriente; un bipolar en saturación, no.

Los 2,5 V medidos **caen dentro de la banda de 1,8–3,2 V del datasheet**, así que la hoja de datos estaba bien y la extrapolación optimista era nuestra.

> **Confusor a descartar:** si los 12 V se leyeron en el display de la fuente y no con las puntas sobre los tornillos del módulo, el cableado y los contactos están incluidos en los 2,5 V. A 340 mA, un par de ohm de cable son ~0,7 V. Remedir V_S en la bornera para separar chip de cableado.

**La regla general** sería `V_batería = V_nominal_motor + ~2 V`, o sea 14 V para estos motores de 12 V.

**Pero en este proyecto no hace falta perseguir los 12 V en bornes**, porque el motor ya es demasiado rápido (§0.3) y de todos modos vamos a limitar el PWM al ~25 %. La caída del L298, que sería un problema con un motor de 6 V, acá es inofensiva.

Recalculado con la caída medida de **2,5 V**:

| Fuente para V_S | El motor recibe | Velocidad resultante | Veredicto |
|---|---|---|---|
| **3S LiPo (11,1 V nom.)** | ~8,6 V | ~250 rpm → 0,79 m/s | ✅ **Recomendado** |
| Fuente de 12 V | **9,5 V** (medido) | **277 rpm → 0,87 m/s** | ✅ Ideal para banco |
| 4S LiPo (14,8 V) | ~12,3 V | ~360 rpm | ⚠️ Por encima de nominal, innecesario |
| 2S LiPo (7,4 V) | ~4,9 V | ~145 rpm | ⚠️ Poco par; con `v_min` izq. en 64 queda sin margen |

> Como el proyecto limita el PWM al ~34 % (§0.3), perder 2,5 V en el puente no molesta para la velocidad. Sí molesta para el **par de arranque**, que es lo que empuja el `v_min` de la rueda izquierda hasta 64 (§0.4). Con una 3S descargada el margen se achica todavía más.

### 2.1 Restricción adicional del módulo comercial

El módulo en PCB trae un regulador lineal **78M05** con un jumper (típicamente rotulado `5V_EN` o `12V_JMP`):

- **Jumper puesto:** el módulo genera sus propios 5 V para la lógica del L298 a partir de V_S. **Requiere V_S ≥ 7 V** (el 78M05 necesita ~2 V de dropout). El pin `5V` del header pasa a ser una **salida**.
- **Jumper sacado:** hay que alimentar el pin `5V` desde afuera con 5 V.

🔴 **Peligro que hay que evitar sí o sí:** con el jumper puesto, **nunca** conectar el pin `5V` del módulo al 5 V de la Pi o del ESP32. Serían dos reguladores enfrentados alimentando el mismo nodo. Es el error de cableado más común con este módulo y puede dañar ambas fuentes.

### 2.2 Verificación térmica

Con Rth j-amb = 35 °C/W sin disipador (el módulo trae uno chico que lo baja bastante), y con las corrientes reales del GM25-370 de 12 V:

| Escenario | Corriente/canal | Caída | Disipación total | ΔT sin disipador | Veredicto |
|---|---|---|---|---|---|
| Marcha normal (PWM 25 %) | ~0,16 A | ~1,4 V | ~0,45 W | +16 °C | ✅ Frío |
| Carga alta | 0,4 A | ~1,5 V | ~1,2 W | +42 °C | ✅ Cómodo |
| Stall de ambos motores | 1,06 A | ~1,9 V | ~4,0 W | +140 °C | ⚠️ Solo momentáneo |

**Margen frente a los límites del L298:**

| Límite del L298 | Demanda del GM25-370 | Margen |
|---|---|---|
| 2 A DC por canal | 1,06 A en stall | **47 %** ✅ |
| 4 A total | 2,1 A (ambos en stall) | **47 %** ✅ |

**Conclusión:** el L298 queda holgado para esta aplicación. Los motores de 12 V consumen la mitad que sus equivalentes de 6 V para la misma potencia, y como además vamos a limitar el PWM al 25 %, la corriente típica va a rondar los 160 mA por canal — un octavo del límite del driver.

El único escenario incómodo sigue siendo el stall prolongado (robot empujando una pared a PWM alto). Con protección de sobretemperatura integrada, el fallo sería "se apaga", no "se quema", pero igual conviene que el firmware no insista contra un obstáculo.

---

## 3. El encoder

⚠️ **El PDF `12cpr_encoder_spec_sheet_14.pdf` no corresponde a este motor.** Describe un *Micro Metal Gearmotor* de 10 × 12 mm con eje Ø3 mm y montaje 2×M1.6 — un motor mucho más chico. El GM25-370 tiene caja de **Ø25 mm**, eje **Ø4 mm** y montaje 2×M3.

La hoja del GM25-370CA confirma que esta familia admite encoders de **3 ppr y 12 ppr**, así que las características eléctricas de abajo son representativas de la clase de encoder que lleva, pero **hay que verificar el pinout real** contra los cables del motor antes de conectar nada.

| Parámetro | Valor | Consecuencia |
|---|---|---|
| Tipo | Hall efecto, 2 canales en cuadratura (90° ± 1/6 T) | Permite sentido de giro además de velocidad |
| Resolución | 12 CPR **en el eje del motor** | Resolución real = 12 × relación de reducción, por vuelta del eje de salida |
| V_CC sensor Hall | **mín. 3,5 V** – máx. 20 V | 🔴 **3,3 V está por debajo del mínimo** — no alimentarlo del riel de 3,3 V |
| Corriente | 5 mA típ / 10 mA máx | Despreciable |
| Salida | **Colector abierto**, requiere pull-up externo (1 kΩ según hoja) | ✅ Ver el truco de abajo |
| V_CE(sat) salida | 300 mV típ / 700 mV máx | Nivel bajo bien definido |

### 3.1 Level shifting gratis

La salida es de **colector abierto**: el nivel alto lo define el riel al que se conecte el pull-up, no la alimentación del sensor. Esto resuelve el conflicto de tensiones sin ningún componente extra:

```
V_CC del sensor Hall  →  5 V     (dentro de spec, ≥ 3,5 V)
Pull-up de A y B      →  3,3 V   (define el nivel alto)
Salidas A y B         →  0 a 3,3 V  →  seguro para el ESP32 ✅
```

🔴 **Lo que NO hay que hacer:** poner el pull-up a 5 V. Metería 5 V en un GPIO del ESP32, que **no es tolerante a 5 V**, y lo daña.

**Valor del pull-up:** la hoja sugiere 1 kΩ, pero eso consume 3,3 mA por canal cuando la salida está en bajo (13 mA por los 4 canales de ambos encoders). Con **10 kΩ** alcanza de sobra para las frecuencias de este encoder y baja el consumo a 0,33 mA por canal. Usar 10 kΩ salvo que se vean flancos redondeados en el osciloscopio.

**Antes de agregar resistencias:** medir con el multímetro entre la salida A y V_CC del encoder. Si da ~1 kΩ, el módulo ya trae el pull-up puesto y hay que sacarlo o replantear (porque estaría referido a la alimentación del sensor, no a 3,3 V).

### 3.2 Pinout de referencia (6 hilos)

Convención habitual en estos encoders — **verificar contra el motor real antes de conectar**, porque los colores varían entre fabricantes:

| Color | Señal |
|---|---|
| Negro | Motor − |
| Rojo | Motor + |
| Marrón | V_CC sensor Hall |
| Verde | GND sensor Hall |
| Azul | Salida Hall A |
| Violeta | Salida Hall B |

**Verificación con multímetro antes de energizar:** los dos cables del motor deben dar continuidad entre sí (resistencia baja, unos pocos ohm, a través del bobinado). Los cuatro del encoder no. Eso identifica el par de potencia sin ambigüedad.

### 3.3 Resolución esperada

Con 12 ppr en el eje del motor y una reducción del orden de 16:1, la resolución en el eje de salida sería ~192 pulsos por vuelta por canal, o **~768 cuentas por vuelta** decodificando la cuadratura en x4. Sobra para odometría.

Frecuencia de pulsos a máxima velocidad: ~1,1 kHz por canal, ~4,5 kHz de flancos por motor. Nada problemático para las interrupciones del ESP32.

> Los encoders son **extensión opcional** según `PLAN.md` §5 D5. No se cablean para la prueba de hoy.

---

## 4. Presupuesto de consumo

### Riel de motores (batería → V_S del L298N)

| Consumidor | Continuo | Pico |
|---|---|---|
| 2 × GM25-370 en marcha (PWM ~25 %) | ~0,3 A | — |
| 2 × GM25-370 en arranque/stall | — | ~2,1 A |
| L298 en reposo | 0,07 A | — |
| 78M05 (si jumper puesto) | ~0,04 A | — |
| **Total a dimensionar** | **~0,4 A** | **≥ 2,5 A** |

**Medido 2026-07-24, ruedas al aire, ambos motores al 100 %: 340 mA totales.** Desglose:

| Consumidor | Corriente |
|---|---|
| L298 en reposo (I_S) | 50–70 mA |
| 78M05 + lógica | ~40 mA |
| **Overhead del módulo** | **~110 mA** |
| Dos motores con reductor, sin carga | ~230 mA (~115 mA c/u) |
| **Total medido** | **340 mA** |

> ⚠️ La versión anterior de esta nota decía "~50 mA los dos motores juntos" y estaba mal por un factor de 7. Ese número salía de la corriente sin carga del **motor pelado** de §0.1 (25 mA), que **no incluye la fricción del reductor metálico** ni el consumo propio del módulo. 115 mA por motor con caja reductora es normal.
>
> No cambia ninguna conclusión de dimensionamiento: 340 mA contra el límite de 1,5 A de la fuente de banco y los 4 A totales del L298 sigue siendo holgadísimo.

### Riel de 5 V (Raspberry Pi 5)

| Consumidor | Consumo |
|---|---|
| Pi 5 con cámara + inferencia | 1,5–2 A típico, con picos mayores |
| ESP32 (alimentado por USB desde la Pi) | ~0,25 A pico |
| Ultrasónico PING))) (del pin VIN del ESP32) | ~30–35 mA |
| Buzzer activo (de un GPIO a 3,3 V) | ~20 mA, sólo mientras suena |
| **Total** | **5 V @ 3 A mínimo — 5 A recomendado** |

> La Pi 5 pide oficialmente una fuente de 5 V/5 A para habilitar toda la corriente de USB. Con 3 A funciona, pero limita periféricos.

---

## 5. Topología de alimentación

### 5.1 Hoy — banco de pruebas (objetivo: mover los motores)

```
   Notebook ──USB──> ESP32          (alimentación + programación + monitor serie)
                       │
                       │ GPIOs 3,3 V (van directo, V_IH = 2,3 V ✅)
                       v
   Fuente 12 V ──────> L298N  ──> Motores
   (o 3S LiPo)
        │                │
        └────────────────┴──────── GND COMÚN con el ESP32  ⚠️ obligatorio
   
   Pin "5V" del módulo ──> SIN CONECTAR
```

Sin GND común, las señales de control no tienen referencia y el driver hace cualquier cosa (o no hace nada). Es el segundo error más frecuente después del jumper de 5 V.

### 5.2 Robot final

```
   Batería 3S LiPo (11,1 V)
        ├──────────────────> V_S del L298N ──> Motores
        │
        └──> Buck 5V/5A ───> Raspberry Pi 5
                                   │
                                   └──USB──> ESP32
                                             (alimentación + enlace serie de PLAN.md §8)
   
   GND de batería, buck, Pi y ESP32 todos unidos.
```

**Detalle elegante:** el ESP32 colgado del USB de la Pi resuelve alimentación y enlace serie con un solo cable, que es exactamente el canal que especifica `PLAN.md` §8.

Esto cumple el requisito de `PLAN.md` §3.2 (alimentación separada, GND común): los motores y la Pi comparten batería pero están desacoplados por el buck, que absorbe los picos de corriente de los motores y evita que la Pi se reinicie.

> Alternativa aún más segura para la demo: power bank USB independiente para la Pi. Desacople total, cero riesgo de reinicio, a costa de llevar dos baterías.

---

## 6. Tabla de cableado ESP32 ↔ L298N

Pines elegidos evitando los de entrada exclusiva (34, 35, 36, 39), los del flash (6–11) y los de strapping (0, 2, 5, 12, 15).

| Módulo L298N | GPIO ESP32 | Función |
|---|---|---|
| ENA | **25** | PWM canal A |
| IN1 | **26** | Dirección canal A |
| IN2 | **27** | Dirección canal A |
| ENB | **13** | PWM canal B |
| IN3 | **33** | Dirección canal B |
| IN4 | **32** | Dirección canal B |
| GND | GND | ⚠️ Obligatorio |
| 5V | — | **Sin conectar** (ver §2.1) |
| V_S / +12V | + batería | |
| GND (potencia) | − batería | Mismo nodo que el GND del ESP32 |
| OUT1 / OUT2 | **Motor DERECHO** | Ver §6.3 |
| OUT3 / OUT4 | **Motor IZQUIERDO** | Ver §6.3 |

### 6.1 Jumpers del módulo

- **ENA y ENB:** el módulo trae jumpers que los atan a 5 V. **Sacar ambos** — si quedan puestos no hay control de velocidad, solo encendido/apagado a fondo.
- **5V_EN:** dejarlo puesto si V_S ≥ 7 V.

### 6.2 Mejora de seguridad recomendada

Entre el boot del ESP32 y la primera instrucción del firmware, los GPIO quedan flotando y las entradas de habilitación del L298 no tienen nivel definido → posible sacudón de los motores al encender.

**Mitigación:** resistencias de **10 kΩ a GND** en ENA y ENB. Mantienen los puentes deshabilitados hasta que el firmware toma control. El firmware además pone todo en bajo como primera acción.

### 6.3 Los canales quedaron cruzados respecto de las ruedas

Verificado durante el bring-up: **el canal A del módulo (ENA/IN1/IN2 → OUT1/OUT2) maneja la rueda derecha**, y el canal B (ENB/IN3/IN4 → OUT3/OUT4) la izquierda. Es al revés de lo que asumía la tabla original.

El sentido de giro de cada motor **sí** quedó correcto con su cableado actual: con el comando `w` ambas ruedas empujan hacia adelante. Lo único cruzado es la asignación izquierda/derecha.

**Se corrige por firmware, no recableando.** En `main.cpp` hay un bloque de mapeo dedicado:

```c
#define PIN_LEFT_PWM  PIN_ENB
#define PIN_LEFT_A    PIN_IN3
#define PIN_LEFT_B    PIN_IN4

#define PIN_RIGHT_PWM PIN_ENA
#define PIN_RIGHT_A   PIN_IN1
#define PIN_RIGHT_B   PIN_IN2
```

Los `#define PIN_ENA`…`PIN_IN4` siguen describiendo el cableado físico real y no hay que tocarlos. Si algún día se mueven los cables en la bornera, el bloque de mapeo de arriba es lo único que cambia.

⚠️ **Trampa al mover un motor de canal:** el pin de enable y el canal LEDC tienen que viajar juntos. En el core 2.x de Arduino-ESP32 `ledcWrite()` recibe el canal, no el pin; si se cambia uno y no el otro, el PWM sale por el puente equivocado. En `setup()` esto se resuelve con `pwm_init(PIN_LEFT_PWM, PWM_CH_LEFT)`.

---

## 7. Checklist previo a energizar

- [ ] Jumpers de ENA y ENB **retirados**
- [ ] Jumper 5V_EN puesto **y** V_S ≥ 7 V (o jumper sacado y 5 V externos)
- [ ] Pin `5V` del módulo **sin conectar** a la Pi ni al ESP32
- [ ] GND del ESP32 unido al GND de la batería
- [ ] Polaridad de la batería verificada con multímetro **antes** de conectar
- [ ] Tensión de batería medida y dentro de lo esperado
- [ ] Motores conectados a OUT1/OUT2 y OUT3/OUT4
- [ ] Ninguna conexión entre 3,3 V del ESP32 y nada del lado de potencia
- [ ] Chasis apoyado con **las ruedas al aire** (no en el piso) para la primera prueba

---

## 8. Bitácora de mediciones

Completar durante el bring-up:

| Medición | Valor | Fecha |
|---|---|---|
| Tensión de fuente en reposo | 12,0 V (fuente de banco) | 2026-07-24 |
| Tensión de fuente con ambos motores al 100 % | 12,0 V — **sin caída apreciable** | 2026-07-24 |
| Tensión en bornes del motor al 100 % PWM | **9,5 V** | 2026-07-24 |
| Caída real del L298 (V_S − V_motor) | **2,5 V** — ver §2, mayor que lo estimado | 2026-07-24 |
| Corriente en marcha libre (ambos motores + módulo) | **340 mA** — ver desglose en §4 | 2026-07-24 |
| Corriente de stall (un motor, 1 s) | ⬜ pendiente | |
| Temperatura del L298 tras 5 min de marcha | ⬜ pendiente | |
| PWM mínimo de arranque — rueda derecha | **32** (±15) | 2026-07-24 |
| PWM mínimo de arranque — rueda izquierda | **64** (±15) — ver §0.4 | 2026-07-24 |
| Diámetro de rueda | **60 mm** | 2026-07-24 |
| Velocidad calculada al 100 % PWM | **0,87 m/s** — ver §0.3 | 2026-07-24 |
| Velocidad real en piso (cronometrar 1 m) | ⬜ pendiente | |

### 8.1 Qué salió distinto de lo previsto

Tres suposiciones del análisis previo al bring-up quedaron desmentidas por la medición. Las tres son material directo para la sección de resultados del informe:

| Parámetro | Estimado | Medido | Por qué falló la estimación |
|---|---|---|---|
| Caída del L298 | 1,4–1,6 V | **2,5 V** | Se extrapoló la caída hacia abajo con la corriente. En un Darlington la V_CEsat tiene un piso fijo de juntura que no escala (§2) |
| Consumo ruedas al aire | ~50 mA | **340 mA** | Se usó la corriente del motor pelado, sin fricción de reductor ni consumo del módulo (§4) |
| Velocidad al 100 % | 1,19 m/s | **0,87 m/s** | Rueda real de 60 mm (se supuso 65) y el motor recibe 9,5 V, no 12 (§0.3) |

Los dos primeros errores empeoran el balance, el tercero lo mejora. Ninguno compromete el dimensionamiento del driver, pero el primero explica el `v_min` alto de §0.4 y el tercero permite subir `v_max`.


---

## 9. Cableado del ultrasónico, el buzzer y los encoders

✅ **Cableado real, del 2026-10-02.** El plan de agosto era un HC-SR04 en los GPIO 18/19 y el buzzer en el 4; lo que se montó es otra cosa, por dos razones: el sensor que había es un **Parallax PING)))** de tres pines, y en la protoboard **sólo queda accesible una fila de pines del ESP32** (la de los motores). De esa fila, los únicos libres que pueden ser salida son el 12 y el 14.

| Señal | GPIO ESP32 | Notas |
|---|---|---|
| PING))) **SIG** | **12** | 🔴 **Divisor resistivo obligatorio** — ver abajo. Disparo y eco por el mismo pin |
| PING))) **5V** | VIN (5 V) | Se alimenta a 5 V; el USB del Pi entrega ~4,6–5 V en ese pin |
| PING))) **GND** | GND | Mismo nodo que el GND del ESP32 |
| Buzzer **+** | **14** | Buzzer **activo** de dos patas, directo al pin |
| Buzzer **−** | GND | |

Pines que quedaron libres: 4, 18 y 19 (del plan original) y los cuatro de sólo entrada, reservados para los encoders (§9.3).

### 9.1 🔴 El PING))) trabaja a 5 V y el ESP32 no los tolera

El PING))) usa **un solo pin, SIG**, para las dos cosas: el ESP32 le manda un pulso corto (el disparo) y enseguida el sensor contesta por el mismo cable con un pulso cuyo ancho es el tiempo de ida y vuelta del sonido. Ese pulso de respuesta sale a **5 V**, y un GPIO del ESP32 conectado directo se daña.

**Divisor resistivo en SIG, entre el sensor y el GPIO 12:**

```
SIG ──[ R1 = 1 kΩ ]──┬── GPIO 12
                     │
                [ R2 = 2 kΩ ]
                     │
                    GND
```

- **Del sensor al ESP32** (el eco): `5 V × R2/(R1+R2) = 5 × 2/3 = 3,33 V`, justo el riel del ESP32.
- **Del ESP32 al sensor** (el disparo): los 3,3 V llegan a SIG a través de la de 1 kΩ sin caída apreciable, porque la entrada del sensor casi no toma corriente. Alcanza: el umbral es TTL.

🔴 **El orden de las resistencias importa.** Cruzadas (2 kΩ en serie, 1 kΩ a GND) el eco llega a 1,7 V y el ESP32 no lo lee: el sensor parece mudo. Sin la de 2 kΩ, al pin le llegan 5 V.

Con 2 kΩ se puede usar 2×1 kΩ en serie. Lo que **no** sirve es un divisor de valores muy altos (100 kΩ): con la capacidad de entrada del pin redondea los flancos y el ancho del pulso medido queda mal.

**Tiempos del PING)))** (hoja de datos): disparo de 2 µs mínimo (5 µs típico); el sensor espera 750 µs y recién entonces levanta SIG; el eco dura entre 115 µs y 18,5 ms. Mide de 2 cm a 3 m. Cuando no hay nada adelante devuelve el pulso más largo, que el firmware informa como ~370 cm: **"370" es "libre", no una distancia real.**

**El GPIO 12 es un pin de arranque** (MTDI): si está en alto en el instante en que el ESP32 sale del reset, el módulo alimenta la memoria flash a 1,8 V y no arranca. En reposo la resistencia de 2 kΩ lo tiene en bajo, así que al encender no hay problema; el riesgo sería un reinicio en medio de un eco. Medido el 2026-10-02: **abrir el puerto serie desde el Pi no reinicia este ESP32** (el contador de disparos sigue de largo), con lo que en una corrida normal no hay reinicios. Si el D14 no estuviera ocupado por el buzzer, sería mejor pin.

### 9.2 Buzzer: activo, en el GPIO 14

Es un buzzer **activo** de dos patas: suena solo, a su propio tono, cuando se le da nivel alto. En `main.cpp`, `BUZZER_PASSIVE` está en `0` (con uno **pasivo**, al que hay que generarle el tono, va en `1` y usa LEDC en el canal 2).

Va directo al pin, sin transistor. Alimentado desde un GPIO de 3,3 V suena algo más bajo que a 5 V; el usuario confirmó que se escucha. Un buzzer grande (>20 mA) necesitaría transistor: el límite recomendado por pin del ESP32 es 20 mA y el absoluto 40 mA.

🔴 **No puede ir en el 34, 35, 36 ni 39**: son pines de sólo entrada. El 2026-10-02 se lo conectó primero al 35 y no hay firmware que lo haga sonar ahí.

El GPIO 14 saca una señal PWM unos milisegundos al arrancar (es así de fábrica), así que el buzzer puede dar un chasquido al encender. Es inofensivo.

**Qué suena y cuándo** (lo decide el Pi, `PLAN.md` §6 y §8): alarma intermitente —150 ms sí, 150 ms no— durante toda la huida, y un tono largo de 1,2 s, una vez, al llegar al oso.

### 9.3 Pines reservados para los encoders

No se cablean todavía (extensión opcional, `PLAN.md` §5 D5), pero quedan reservados para que el día que se agreguen no haya que mover nada:

| Señal | GPIO |
|---|---|
| Encoder izquierdo A / B | **34 / 35** |
| Encoder derecho A / B | **36 / 39** |

Los cuatro son de **entrada exclusiva**, que es exactamente lo que hace falta, y **no tienen pull-up interno** — lo cual encaja con el pull-up externo de 10 kΩ a 3,3 V que ya pide §3.1 para las salidas de colector abierto del encoder. Un pin normal con pull-up interno habría sido peor: el pull-up interno del ESP32 es de ~45 kΩ, demasiado débil para estos flancos.

### 9.4 Estado

⬜ Nada de esto está cableado al 2026-08-27. El firmware `esp32_control` funciona igual sin el sensor conectado: la telemetría reporta `dist_cm = -1` ("sin lectura") en vez de colgarse esperando el eco.

✂️ **2026-10-01: el ultrasónico y el buzzer quedan fuera del alcance de esta versión**, por falta de tiempo. *(Decisión revertida al día siguiente.)*

✅ **2026-10-02: los dos entraron.** Cableados como dice la tabla de arriba, con el firmware adaptado y probados en el piso. Los encoders siguen para una segunda versión.

**Lo medido ese día:**

| Qué | Resultado |
|---|---|
| Robot quieto frente a una pared a 1,5 m | 153 cm, estable, 100 % de lecturas válidas. Sin ecos del piso |
| Avance a velocidad 40 hasta leer ≤ 20 cm (`freno_sonar.py`) | Mandó frenar leyendo 19 cm, quedó parado a 16 cm: 3 cm de inercia |
| Huida a velocidad 60, umbral de esquivar en 20 cm | Cortó a 17–18 cm y giró; la lectura bajó hasta 11–16 cm |
| Huida a velocidad 60, umbral de esquivar en 30 cm | Cortó a 29 cm; no bajó de 27 |
| Acercamiento al oso | Sin desvíos falsos; frena por tamaño con el sensor en 28 cm y queda quieto a 22 |
| Buzzer | Suena en los dos patrones (confirmado de oído por el usuario) |

**Lo que el sensor no arregla, visto en esas corridas:**

- **Sólo mira adelante.** El retroceso y el giro de la huida siguen a ciegas. Las lecturas más bajas del día (7 y 13 cm) aparecieron al terminar el giro, con el robot ya pegado a algo antes de empezar a avanzar. Ahí gira en el lugar hasta tener el camino libre, pero la cercanía no la evita.
- **Una pared muy de costado no la ve** hasta estar encima: el eco rebota para otro lado. En una huida no vio nada hasta los 23 cm.
- **Girando frente a una pared da lecturas falsas de "libre"** entre dos de "pegado" (16 cm, 150, 11). Por eso el Pi sostiene el obstáculo 0,3 s después de la última lectura que lo vio (`SONAR_RETENCION_S`).

**El primer módulo estaba muerto.** Con el cableado bien (3,3 V medidos en SIG con la línea en alto, 5 V en la alimentación) no contestaba a ningún disparo; con otro igual anduvo al instante. Costó 20 minutos descartar el firmware. Las herramientas que quedaron de esa búsqueda están en `RUNBOOK.md`, Paso 25.

**Si el sensor se desconecta, el robot anda igual pero a ciegas** (pasó el mismo día: se soltó un cable al mover el del buzzer y una corrida entera salió sin lectura). `main.py` lo avisa al arrancar, y `demo.sh sonar` lo muestra sin mover el robot.
