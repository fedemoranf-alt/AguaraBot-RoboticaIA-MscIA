---
title: "Guía de operación del robot — día de la presentación"
subtitle: "TPF Robótica e IA · vehículo autónomo con visión (YOLOv8n + Raspberry Pi 5 + ESP32)"
date: "Versión del 2026-10-02: manual para operar el robot sin ayuda (con ultrasónico y buzzer)"
lang: es
header-includes: |
  ```{=latex}
  \renewcommand{\labelitemi}{$\bullet$}
  \renewcommand{\arraystretch}{1.3}
  \usepackage{needspace}
  \usepackage{etoolbox}
  \pretocmd{\section}{\Needspace{12\baselineskip}}{}{}
  ```
---

> **Para qué es esta hoja.** Operar el robot de punta a punta **sin depender
> de nadie ni de un asistente de IA**: armarlo, encontrarlo en la red,
> chequearlo, correr la demo, entender lo que dice la pantalla, resolver los
> problemas conocidos, ajustar un parámetro si hace falta, traer el video y
> apagarlo. Cada paso es un comando corto y dice **qué tiene que salir**.
>
> **Qué está probado y qué no** (al 2026-10-02). Probados en el robot: todo el
> comportamiento (dieciséis corridas en el piso, las seis últimas con el
> ultrasónico y el buzzer); de `demo.sh`: `chequeo`, `imagen`, `ver`, `sonar`,
> `correr`, `grabar`, `ultima`, `firmware`, `red`, `hotspot` y `apagar`; y en
> la notebook, copiar el código al Pi y traer las corridas. El **hotspot
> `FedeAP` ya está cargado en el Pi y probado**: el Pi arranca en él y la
> notebook lo encuentra. **Sin probar en el robot:** `demo.sh fondo`;
> `demo.sh parar` sólo sin corrida que parar; y los tres lanzadores `.cmd` de
> la notebook, que se agregaron el 2026-10-02 cuando se vio que los `.ps1` no
> corren desde esta carpeta (se probó el mecanismo, no cada uno contra el Pi).
> **Y nunca se hizo el recorrido entero de esta hoja por el hotspot: el ensayo
> de §2 no es opcional.**

**Lo mínimo, en 7 pasos** (el resto de la hoja es el detalle):

1. Cargador → Pi por **USB-A**, **desenchufado de la pared**. Webcam **firme** en el USB **azul de abajo**, ESP32 en el **negro de abajo**. UPS 12 V → L298 **desenchufada**. Notebook y Pi en el mismo hotspot.
2. PowerShell, en la carpeta del proyecto: `.\scripts_pi\entrar.cmd`
3. `bash ~/TPF/scripts_pi/demo.sh chequeo` → tiene que decir **LISTO**
4. `bash ~/TPF/scripts_pi/demo.sh imagen` → **imagen SANA**; y `bash ~/TPF/scripts_pi/demo.sh sonar` → una distancia creíble, no **SIN LECTURA**
5. `bash ~/TPF/scripts_pi/demo.sh ver` → ¿aparece `teddy bear`? ¿y `backpack` con la mochila? Ctrl+C
6. Enchufar los **12 V**, robot en el piso, oso a ~1 m:
   `bash ~/TPF/scripts_pi/demo.sh correr 60 "aproximacion"`
7. Parar: **Ctrl+C**. Emergencia: **desenchufar los 12 V** (no el Pi).

# 1. Qué hace el robot (para contarlo en 20 segundos)

| Ve | Hace | Estado en pantalla |
|--------|---------------------|----------|
| nada | mira quieto ~0,6 s, gira **un saltito** (~18°) y repite; una vuelta entera tarda **~17 s**. Después avanza ~18 cm y vuelve a empezar | `BUSCAR` |
| el **oso** (impreso en A4) | se queda quieto hasta confirmarlo (~0,3 s), se acerca centrándolo, **frena a ~30 cm** y da **un pitido largo** | `APROXIMAR` → `ENCONTRADO` |
| una **mochila** | se queda quieto hasta confirmarla y **huye, con la alarma sonando**: retrocede ~30 cm girando, sigue girando hasta darle la espalda y avanza ~65 cm | `HUIR` |
| oso **y** mochila | huye: **la amenaza tiene prioridad** | `HUIR` |
| **algo a menos de 30 cm adelante**, cuando va a avanzar sin el oso a la vista | **no avanza: gira en el lugar** hasta tener el camino libre | `HUIR` o `BUSCAR` |

La cámara reconoce el oso de hoja A4 hasta **~1,3 m**. Más lejos no lo ve: lo
encuentra recién cuando los avances cortos de `BUSCAR` lo acercan. Si pierde
el oso, lo busca **hacia el lado donde lo vio por última vez**. Después de
huir, el barrido arranca **hacia un lado sorteado** (o hacia el contrario de
la mochila, si quedó a la vista), para no repetir siempre el mismo recorrido.
Después de
`ENCONTRADO` el robot **se queda quieto**, salvo que vea la mochila.

**El ultrasónico** (al frente) mide la distancia a lo que tenga adelante.
Sirve para dos cosas: que el robot **no avance contra una pared** al huir o al
buscar, y dar por alcanzado el oso si llega a menos de 20 cm antes de frenar
por tamaño. **Lo que no hace:** sólo mira **adelante** —el retroceso y el giro
de la huida siguen a ciegas— y una pared a la que el robot se acerca **muy de
costado** no la ve hasta estar encima. El área igual tiene que estar despejada.

**El buzzer** suena en dos momentos: **alarma intermitente** durante toda la
huida, y **un tono largo** (algo más de un segundo) al llegar al oso. Al
encender el robot puede dar un chasquido corto: es normal.

# 2. Antes del día (una sola vez, con tiempo)

Todo esto se hace en un lugar donde el Pi ya tenga red (la de siempre).

- [ ] **Código al día en el Pi.** Desde la PC, en PowerShell, en la carpeta
      del proyecto: `.\scripts_pi\provisionar_pi.cmd`. Busca el Pi solo, copia
      `src/` y `scripts_pi/`, y corre las verificaciones allá: tiene que decir
      **"todas en orden"**.
- [x] **Cargar el hotspot del celular en el Pi.** *Hecho el 2026-10-02 con la
      red `FedeAP`; sólo hay que repetirlo si cambia el nombre o la clave.* En la sala no va a estar el
      WiFi de siempre, y el Pi no tiene pantalla: sin red **no hay forma de
      entrar**. Ya adentro del Pi (§5), con el nombre y la clave del hotspot
      entre comillas:

      bash ~/TPF/scripts_pi/demo.sh hotspot "NOMBRE_DEL_HOTSPOT" "CLAVE"

  En iPhone, activar antes "Maximizar compatibilidad" en el punto de acceso.
  `demo.sh red` muestra las redes que el Pi tiene guardadas.
- [x] **Probar el hotspot** (*hecho el 2026-10-02: arrancó en él y se entró*): `demo.sh apagar`, prender el hotspot, conectar la
      notebook al hotspot, prender el Pi, esperar 2 minutos y entrar con
      `.\scripts_pi\entrar.cmd`. Si no lo encuentra, ver §5.
- [ ] **Probar lo que falta estrenar** en el robot: `demo.sh fondo`. (El
      2026-10-02 ya corrieron `correr`, `grabar`, `sonar`, `imagen`, `red`,
      `hotspot` y la traída del video a la notebook.)
- [ ] **Ensayo completo con esta hoja, sin ayuda**, con el hotspot. Lo que no
      esté claro, se corrige acá.
- [ ] **Video de respaldo** (plan B, §13). Hay tres, vistos desde el robot y
      **sin sonido**: dos en la carpeta `media/` (89 s del 01/10, y 90 s del
      02/10 ya con el ultrasónico) y un clip de 20 s en `presentacion_10min/`.
      Llevarlos copiados en la notebook. Falta uno filmado desde afuera, con el
      celular, que es el único donde se va a escuchar el buzzer.
- [ ] Anotar **aparte** la contraseña del usuario `admin` del Pi (por si se usa
      otra notebook, que no tiene la clave SSH).
- [ ] Cargar las dos baterías **y desenchufarlas de sus cargadores antes de
      usar el robot**: con las baterías cargándose el Pi marca bajo voltaje.
      Imprimir esta hoja.

# 3. Qué llevar

- [ ] Robot armado, con webcam y ESP32 conectados al Pi
- [ ] **Cargador portátil 20 000 mAh** (cargado) + cable **USB-A** → USB-C para el Pi
- [ ] **UPS** (cargada) con su cable de 12 V al L298
- [ ] **Oso impreso en hoja A4** (~20 cm): el mismo con el que se calibró
- [ ] **La mochila negra con la que se probó** (la amenaza). Otra mochila puede
      no ser reconocida: ver §10
- [ ] Notebook cargada, con la carpeta del proyecto · celular con datos para el hotspot
- [ ] Respaldo: fuente de pared del Pi, cables USB de repuesto
- [ ] Cinta métrica y cinta de papel para marcar el piso

# 4. Armado en la sala (5 minutos)

1. **Espacio**: unos 2 × 2 m despejados, piso liso. **Sin bolsos, mochilas ni
   valijas a la vista** de la cámara, y mejor sin **objetos oscuros grandes**
   (sillones negros, marcos de puerta oscuros de cerca): el robot los puede
   tomar por la amenaza y huir. `demo.sh fondo` lo revisa (§6).
2. **Webcam en el USB azul de abajo** del Pi y **ESP32 en el negro de abajo**:
   así quedan en controladores USB distintos. Cable de la webcam sujeto al
   chasis, sin tirar del conector, y **el enchufe empujado a fondo**: se suelta
   al mover el robot (pasó el 2026-10-02). GND común ESP32–L298 conectado.
3. **Ultrasónico al frente**, con los dos "ojos" despejados, y sus tres cables
   firmes en la protoboard: si se suelta uno, el robot anda igual pero **sin
   ver obstáculos**. El buzzer, con sus dos patas en su lugar.
4. **UPS 12 V → L298: todavía DESENCHUFADA.** Así los motores no tienen
   potencia mientras se prepara todo.
5. **Cargador → Pi por la salida USB-A.** **Nunca por USB-C**: el Pi entra en
   bucle de reinicios con el LED rojo parpadeando. Y **las baterías sin
   enchufar a la pared**: cargándose, al Pi le llega poco voltaje.
6. Prender el hotspot del celular, dejar el celular **cerca del robot** y
   conectar la notebook al hotspot. Esperar **1–2 minutos** a que el Pi arranque.

# 5. Conectarse

En la notebook abrir **PowerShell** (Win+X → Terminal), ir a la carpeta del
proyecto y correr:

    .\scripts_pi\entrar.cmd

**Escribirlo tal cual**: empieza con punto y barra invertida (`.\`), y termina
en `.cmd`. Con `.ps1` PowerShell contesta "no está firmado digitalmente" (la
carpeta está en Google Drive y Windows no confía en los scripts de ahí); sin
el `.\` contesta "no se reconoce como nombre de un cmdlet". Y hay que estar
parado en la carpeta del proyecto, no adentro de `scripts_pi`.

Busca el Pi (por nombre, por la última dirección con la que entró, y mirando
quién está en la red) y abre la sesión. Cuando dice `Pi encontrado en ...` y
aparece `admin@pi-MB:~ $`, ya se está **adentro del Pi**: los comandos
`demo.sh` se escriben ahí.

**Si dice "No encontré el Pi":**

1. ¿El Pi está prendido hace más de 2 minutos? ¿La notebook está en el
   **mismo** hotspot?
2. En el celular, abrir la lista de **dispositivos conectados al hotspot**.
   Si aparece `pi-MB`, anotar su dirección (cuatro números con puntos) y:

       .\scripts_pi\entrar.cmd -Ip 192.168.43.57        (con la dirección anotada)

3. Si el Pi **no aparece** en el celular: ¿el hotspot se sigue llamando
   `FedeAP`, con la misma clave? El Pi sólo conoce ése. Si cambió, hay
   que volver a una red que conozca, o conectarle monitor y teclado, y correr
   `demo.sh hotspot` (§2).
4. A mano, sin el script (la misma dirección del paso 2):

       ssh -i $env:USERPROFILE\.ssh\id_ed25519_pi admin@192.168.43.57

   Si pregunta `Are you sure you want to continue connecting`, escribir `yes`.
   Si pide contraseña, es la del usuario `admin` anotada aparte.

Para salir del Pi: `exit`. Si la sesión se congela: cerrar la ventana y volver
a entrar. **Ojo: una corrida en curso puede seguir andando en el Pi** aunque la
sesión se haya cortado (§9); al volver a entrar, `demo.sh parar`.

# 6. Chequear (cinco comandos, en este orden)

Con los **12 V todavía desenchufados**.

**a) ¿Está todo conectado y alimentado?**

    bash ~/TPF/scripts_pi/demo.sh chequeo

Revisa alimentación, temperatura, cámara, ESP32 y las verificaciones del
software. Tiene que terminar con **LISTO**. Si dice `HAY N PROBLEMA(S)`, cada
uno trae al lado qué hacer.

**b) ¿La imagen llega sana?** (6 segundos; no hace falta el oso)

    bash ~/TPF/scripts_pi/demo.sh imagen

Tiene que terminar con **`VEREDICTO: imagen SANA`**. Si dice `DAÑADA A RATOS`
o `ROTA`: desenchufar y enchufar la webcam, acomodar el cable, esperar 5 s y
repetir. Con la imagen rota el robot está casi ciego y **todo lo demás falla
sin explicación**: no seguir hasta que salga sana, o pasar al plan B (§13).

**c) ¿El ultrasónico mide?** (5 segundos; el robot no se mueve)

    bash ~/TPF/scripts_pi/demo.sh sonar

Poner algo adelante del robot a una distancia conocida (una caja a 30 cm, una
pared a 1 m): tiene que dar **ese número, estable**. Sin nada adelante da
**~370 cm**, que es "libre". Si dice **`SIN LECTURA`**, se soltó alguno de los
tres cables del sensor: reponerlo y repetir. Sin sensor el robot anda igual,
pero **no ve obstáculos**.

**d) ¿Ve el oso y la mochila?**

    bash ~/TPF/scripts_pi/demo.sh ver

Poner el oso a ~1 m, de frente. Tienen que aparecer líneas con `teddy bear`,
con su `ex` (posición: negativo = izquierda) y su `ar` (tamaño: ~0,05 a 1 m,
~0,5 a 30 cm). Sacar el oso y poner la **mochila** a ~1 m: tiene que decir
`backpack`. **Ctrl+C** para salir. La foto queda en `~/TPF/logs/vivo.jpg`.

**e) ¿Algo de la sala se confunde con ellos?** (sin el oso ni la mochila a la vista)

    bash ~/TPF/scripts_pi/demo.sh fondo

El veredicto tiene que decir que vería el OSO en **0** frames y la MOCHILA en
**0** frames. Si alguno aparece, hay algo en el fondo que se le parece: girar
el robot hacia otro lado y repetir hasta encontrar qué es, y sacarlo o taparlo.

# 7. La demo

1. Robot en el piso, **oso a ~1 m**. Dejar **1,2 m libres detrás** del robot:
   la huida arranca marcha atrás, a ciegas, y después se aleja.
2. **Ahora sí, enchufar los 12 V de la UPS al L298.** La mano queda cerca de
   ese conector.
3. Correr (60 s y una nota que diga qué escenario es):

       bash ~/TPF/scripts_pi/demo.sh correr 60 "aproximacion oso a 1 m"

   Para que además guarde el **video** de lo que ve el robot:

       bash ~/TPF/scripts_pi/demo.sh grabar 60 "demo completa"

4. Tarda **~10–15 s** en arrancar (carga la red, abre el enlace con el ESP32,
   cuenta 5 s). Durante la cuenta, **apoyar el robot y sacar las manos**.
   Si antes de la cuenta aparece **`!! ULTRASÓNICO SIN LECTURA`**, cortar con
   Ctrl+C y revisar los cables del sensor (§6 c).
5. En pantalla va saliendo una línea por segundo; cada cambio de estado se
   marca con `>>`. Al terminar sale solo el **análisis** (§8). Si en cambio
   dice **`!! La corrida NO se hizo`**, el programa falló antes de arrancar: el
   motivo está en las líneas de arriba (casi siempre, la cámara).

**Escenarios:**

| Escenario | Cómo se arma | Qué se espera |
|------|--------------|--------------|
| Aproximación | oso a ~1 m, en cualquier dirección | busca (hasta ~17 s), se acerca, frena a ~30 cm y da un pitido largo |
| Huida | mochila a **~1 m de la cámara, entera en la imagen** | se queda quieto y, con la alarma sonando, retrocede girando, le da la espalda y se aleja. **Retirar la mochila** apenas arranca, o vuelve a huir cuando la vea |
| Huida contra una pared | lo mismo, con una pared a ~80 cm **detrás** del robot (no menos de 70) | al darse vuelta avanza hacia la pared y, a unos 30 cm, **gira en el lugar** en vez de seguir |
| Conflicto | oso y mochila juntos a la vista, los dos a ~1 m | huye aunque esté viendo el oso |
| Demo completa | oso a ~1 m; cuando frena, mochila a ~1 m **a un costado**; después sacarla | encuentra, huye, vuelve a buscar y encuentra de nuevo. Usar 90 s |
| Mochila en escena desde el arranque | oso y mochila en la sala, la mochila a la vista del robot | huye en los primeros segundos y **después** busca al oso. Así salieron las corridas del 2026-10-02 |

Cuatro cosas que conviene saber antes de armar la escena:

- **El video que guarda `grabar` no tiene sonido.** Si se quiere mostrar el
  buzzer, hay que filmar desde afuera.

- **La mochila pegada al oso no sirve.** Con el robot detenido a 30 cm del
  oso, una mochila al lado **no entra en el cuadro** y no la reconoce. Tiene
  que quedar a ~1 m de la cámara.
- **El oso a más de 1,3 m no lo ve.** Lo va a encontrar igual, pero después de
  una o dos vueltas completas (cada una ~17 s más un avance de 18 cm).
- **Si se mueve el oso con la mano mientras se acerca**, lo pierde, lo vuelve
  a buscar y sigue: no es una falla.

**Parar:** **Ctrl+C** en la terminal (frena los motores).
**Emergencia:** **desenchufar los 12 V de la UPS** — no el Pi.

Para repetir: acomodar el robot y correr otra vez. Cada corrida queda guardada
en `~/TPF/logs/`; `demo.sh ultima` vuelve a mostrar el análisis de la última.

# 8. Leer la pantalla

**Durante la corrida**, cada línea es `[tiempo] ESTADO v_lin= v_ang= (motivo) dist=`.
`v_lin` es avanzar (negativo: atrás) y `v_ang` es girar (positivo: derecha).
`dist` es lo que mide el ultrasónico: **~370 cm es "libre"**, y `--` es que el
sensor no contesta.

| Motivo que aparece | Qué está pasando |
|--------------------|------------------------------------|
| `mirando` / `barriendo` / `reubicando` | busca: quieto mirando / dando un paso de giro / avanzando 18 cm para cambiar de lugar |
| `posible objetivo, freno a confirmar` | vio el oso en una imagen; se queda quieto hasta tener 3 seguidas |
| `posible amenaza, freno a confirmar` | lo mismo, con la mochila |
| `objetivo confirmado, cambio a APROXIMAR` | empieza a acercarse |
| `ex=+0.20 ar=0.063` | acercándose: dónde está el oso (`ex`) y qué tamaño tiene (`ar`) |
| `confirmado pero sin caja en este frame` | una imagen sin oso: frena un instante y sigue |
| `objetivo perdido, vuelvo a BUSCAR` | 5 imágenes seguidas sin oso: lo busca por donde lo vio |
| `llegué (área)` / `llegué (sonar)` / `detenido` | frenó frente al oso: por su tamaño en la imagen, o porque el ultrasónico lo midió a menos de 20 cm |
| `fase 1: retroceso` / `fase 2: giro` / `fase 3: avance` | las tres partes de la huida |
| `fase 3: obstáculo, esquivo` | huyendo, tiene algo a menos de 30 cm adelante: gira en el lugar hasta tener el camino libre |
| `reubicando: obstáculo (...), giro` | lo mismo en el avance corto de la búsqueda: gira en vez de avanzar |
| `obstáculo ajeno (...), desvío` | acercándose al oso apareció algo a menos de 20 cm que **no** es el oso: se desvía |
| `escape completo, vuelvo a BUSCAR` | terminó de huir; ignora la mochila 2 s |

**Al terminar**, el análisis. Lo que hay que mirar, en este orden:

| Línea | Valor normal | Si no |
|------------|-----------------|--------------------------|
| `Imagen: 0 de N frames con franjas` | **0**, o un puñado | Si dice **CÁMARA A CIEGAS**, la corrida no vale: `demo.sh imagen` y §10 |
| `Lazo: ... FPS` | **10 a 11** (9,5 a 10 grabando) | Menos de 9: `demo.sh chequeo` (voltaje, temperatura) |
| las líneas con `→` | la historia: `BUSCAR → APROXIMAR → ENCONTRADO` | ver cuál falta, y §10 |
| `confirmado 0.20 s después de verlo` | 0,2 a 0,3 s | — |
| `'objetivo perdido': 0` | 0 (o 1) | Varias: el oso se le va de la imagen; §10 |
| `ar al frenar` / `ar con el robot quieto` | ~0,36 / 0,35 a 0,65 | Mucho más de 0,65 quieto: quedó demasiado cerca |
| `decidió huir 0.20 s después de ver la mochila` | 0,2 a 0,3 s | — |
| `frames con mochila detectada` | 0 si no había mochila | Más de 0 sin mochila: falsa alarma del fondo; `demo.sh fondo` |

# 9. Seguridad

- El **corte de emergencia es el conector de 12 V** de la UPS. Cortar el Pi deja
  al ESP32 frenando por su cuenta, pero con el Pi a medio apagar.
- `demo.sh correr` y `grabar` siempre ponen límite de tiempo. **No correr
  `main.py` sin `--duracion`.**
- **El ultrasónico sólo ve lo que tiene justo adelante**, y sólo actúa cuando
  el robot va a avanzar. Marcha atrás y girando, paredes, patas de sillas y
  pies siguen siendo invisibles; y una pared muy de costado, también. Área
  despejada y una persona cerca.
- **Si se corta la conexión en plena corrida, no contar con que el robot
  frene**: el programa puede seguir andando en el Pi hasta cumplir su límite
  de tiempo (pasó el 2026-10-02, al cancelar una corrida desde la notebook).
  Lo que frena solo es el ESP32 cuando deja de recibir órdenes (500 ms), o sea
  si el **programa** muere, no si se cae la WiFi. Por eso las corridas son
  cortas y el corte de emergencia son los **12 V**. Al volver a entrar:
  `demo.sh parar`.
- La huida arranca **marcha atrás** y recorre ~1 m en total. Nadie parado
  detrás del robot.

# 10. Problemas y qué hacer

| Síntoma | Causa probable | Qué hacer |
|------------|-----------|----------------|
| al escribir el comando de entrada: **no está firmado digitalmente**, o **no se reconoce como nombre de un cmdlet** | se escribió `.ps1` en vez de `.cmd`, falta el `.\` del principio, o no se está en la carpeta del proyecto | ir a la carpeta del proyecto y escribir `.\scripts_pi\entrar.cmd`, tal cual. Si igual falla: `powershell -ExecutionPolicy Bypass -File scripts_pi\entrar.ps1` |
| `entrar.cmd` dice **No encontré el Pi** | el Pi no terminó de arrancar, no está en la misma red, o no conoce ese hotspot | §5, pasos 1 a 4 |
| el SSH **se corta** o tarda en responder | WiFi débil: el Pi va a ras del piso | acercar el celular del hotspot al robot. **La corrida en curso puede seguir andando**: si el robot se mueve, desenchufar los 12 V; volver a entrar, `demo.sh parar` y repetir |
| `Permission denied` al entrar | notebook sin la clave SSH | entrar con la contraseña de `admin` anotada aparte |
| LED rojo parpadeando, el Pi se reinicia solo | cargador por **USB-C** | pasarlo a la salida **USB-A** |
| chequeo: **bajo voltaje AHORA** | las baterías están **enchufadas a sus cargadores** (visto dos veces el 2026-10-02), el cargador está agotado, o va por USB-C | desenchufar las baterías de la pared; USB-A; si sigue, fuente de pared (robot elevado o con el cable a mano) |
| chequeo: **no hay cámara**, o `correr` dice **La corrida NO se hizo** / `No se pudo abrir la cámara` | el enchufe de la webcam se soltó (pasa al mover el robot) | desenchufar y enchufar la webcam **a fondo** (azul de abajo), esperar 5 s, repetir el chequeo |
| chequeo: **no aparece el ESP32** | cable flojo o cable "sólo carga" | reconectar; probar otro cable USB |
| `demo.sh sonar` dice **SIN LECTURA**; al correr sale **ULTRASÓNICO SIN LECTURA**; en pantalla `dist=--` | se soltó uno de los tres cables del sensor (GND, 5V o SIG) | reponerlo, con los 12 V desenchufados, y repetir `demo.sh sonar`. Si los cables están bien y sigue: `RUNBOOK.md`, Paso 25 |
| `demo.sh sonar` da siempre **~370 cm** aunque haya algo adelante | el sensor quedó apuntando al aire, torcido o tapado por un cable | enderezarlo: los dos "ojos" mirando al frente, despejados |
| el **buzzer no suena** | una pata fuera de su lugar, o el cable no está en el pin D14 | revisar las dos patas (D14 y GND). No sirve en los pines 34, 35, 36 ni 39 |
| `demo.sh imagen` dice **DAÑADA** o **ROTA**; el análisis dice **CÁMARA A CIEGAS** | se pierden paquetes USB de la webcam. Pasó el 2026-10-01 **con los motores parados**, iba y venía solo. El 2026-10-02, con el enchufe reinsertado a fondo y las baterías recién cargadas, no apareció en 3675 frames: es probable que fuera una de esas dos cosas | reenchufar la webcam a fondo y acomodar el cable; baterías fuera del cargador; repetir `demo.sh imagen` dos o tres veces. Si persiste: probar el otro USB azul, y `RUNBOOK.md`, Paso 24. Si no se va: plan B (§13) |
| **cero detecciones** sólo con los motores andando | el ruido de los motores rompe la imagen USB | en `~/TPF/src/config.py` tiene que decir `FORMATO_CAMARA = "MJPG"`; webcam en el azul de abajo y ESP32 en el negro de abajo |
| **pitan los motores y no se mueve**, o gira una sola rueda | firmware con la calibración vieja | `demo.sh firmware` (con los motores quietos) tiene que mostrar `v_min izq/der: 300 / 230`; si no, regrabar el ESP32 (`RUNBOOK.md`, "Flashear el ESP32 desde el Pi") |
| `could not open port /dev/ttyUSB0` | ESP32 desconectado, u otra corrida usando el puerto | `demo.sh parar`; reconectar el ESP32; correr de nuevo |
| la pantalla muestra `v_lin`/`v_ang` distintos de 0 pero **las ruedas no giran** | sin 12 V en el L298 | enchufar o encender la UPS; revisar los bornes del L298 |
| **gira y gira** y nunca pasa a `APROXIMAR` | no detecta el oso | primero `demo.sh imagen`. Después: oso a **menos de 1,3 m**, de frente a donde va a pasar la cámara, buena luz, sin contraluz; comprobar con `demo.sh ver` |
| gira **de corrido**, sin pausas | el barrido a pasos está apagado | en `config.py`: `BUSCAR_PASO_MIRAR_S = 0.6` |
| lo ve pero **se pasa de largo** mientras gira | pasos de giro demasiado grandes | en `config.py`: `BUSCAR_PASO_GIRO_S = 0.25` y `BUSCAR_FRENAR_AL_VER = True` (ya vienen así) |
| se acerca pero **pierde el oso por un costado** | centrado flojo, o alguien movió el oso | lo vuelve a buscar solo. Si pasa siempre: §11, `KP_ANG` |
| se acerca **cruzando el oso** de un lado al otro | centrado demasiado fuerte | §11, `KP_ANG` |
| frena **demasiado lejos o demasiado cerca** | objetivo distinto del calibrado, o hay que ajustar | usar el **oso impreso en A4**. Si es ése: §11, `AREA_OBJETIVO` |
| **no huye** de la mochila | no la reconoce: muy cerca (no entra en el cuadro), muy lejos, u otra mochila | ponerla a ~1 m, entera en la imagen; con `demo.sh ver` tiene que decir `backpack`. Si no lo dice, `demo.sh fondo` con la mochila enfrente muestra **como qué** la ve |
| **huye sin que haya mochila** | falso positivo: bolsos, valijas, mochilas del público u **objetos oscuros grandes** | `demo.sh fondo` hacia cada lado; sacar o tapar lo que aparezca. Último recurso: §11, umbral de la mochila |
| huye **una y otra vez** | la mochila sigue a la vista; o el robot está **arrinconado**: al huir se encuentra con una pared, gira para esquivarla y queda otra vez mirando a la mochila | retirar la mochila apenas arranca la huida, o darle más lugar: al menos 1,5 m libres detrás del robot. Con la mochila fija en escena va a huir cada vez que la vea: es lo esperado |
| al huir **no queda de espaldas** a la mochila | el giro de la huida está calibrado a ojo y depende del lado | §11, `HUIR_GIRO_S` |
| **gira en el lugar y no avanza**, huyendo o buscando | tiene algo a menos de 30 cm adelante: es lo que tiene que hacer | nada; si no hay nada adelante, `demo.sh sonar` (un cable sobre el sensor da lecturas cortas) |
| va **contra un obstáculo** | lo tocó marcha atrás o girando (ahí va a ciegas), entró muy de costado, o el sensor no está leyendo | desenchufar 12 V; despejar el área; `demo.sh sonar` |
| huye **apenas arranca**, antes de buscar al oso | la mochila está a la vista de la cámara desde el principio | es lo esperado. Si no se quiere, sacarla de la vista hasta que el robot llegue al oso |
| Ctrl+C no responde, o quedó una corrida colgada | — | en otra terminal: entrar y `demo.sh parar`; si nada responde, desenchufar 12 V y `sudo reboot` |
| FPS del resumen **menor a ~9,5** | bajo voltaje o temperatura alta | `demo.sh chequeo`; esperar a que se enfríe |
| **nada funciona** y no hay tiempo | — | plan B (§13) |

# 11. Ajustes rápidos, si algo no convence

Todos los números están en un solo archivo del Pi: `~/TPF/src/config.py`.
**Antes de tocar nada, guardar una copia** (una sola vez):

    cp ~/TPF/src/config.py ~/TPF/src/config.py.bueno

Para **probar un valor en una sola corrida**, sin editar nada (al terminar
vuelve solo al valor anterior):

    cd ~/TPF/scripts_pi/piso
    bash corrida_piso.sh prueba 30 "KP_ANG 0.6" KP_ANG=0.6

Para **dejarlo fijo**: `nano ~/TPF/src/config.py`, buscar el nombre con
Ctrl+W, cambiar el número, guardar con Ctrl+O y Enter, salir con Ctrl+X.
Después, **siempre**:

    cd ~/TPF/src && ../.venv/bin/python prueba_estados.py | tail -5

Tiene que decir **`Todo en orden`**. Si aparece alguna línea con `FALLA`, el
valor nuevo rompe algo: volver atrás. Para **volver atrás**:
`cp ~/TPF/src/config.py.bueno ~/TPF/src/config.py`.

| Parámetro | Hoy | Qué hace | Hacia dónde |
|------------------|----|---------------------|--------------------------|
| `KP_ANG` | 0.5 | fuerza con que gira hacia el oso | pierde el oso por un costado: subir (0.6). Lo cruza de lado a lado: bajar (0.4) |
| `AREA_OBJETIVO` | 0.35 | tamaño del oso con el que decide frenar | frena lejos: subir (0.40). Queda encima: bajar (0.30) |
| `V_LIN_MAX` | 55 | velocidad máxima al acercarse | llega muy rápido o no alcanza a centrar: bajar (45) |
| `BUSCAR_PASO_GIRO_S` | 0.25 | cuánto gira en cada paso | le pasa de largo al oso: bajar (0.20). Búsqueda lenta: no subir de 0.30 |
| `BUSCAR_PASO_MIRAR_S` | 0.6 | cuánto mira quieto entre pasos | lo ve y no llega a confirmarlo: subir (0.8) |
| `BUSCAR_GIRO_S` | 17.0 | cuánto dura una vuelta de búsqueda | avanza antes de completar la vuelta: subir |
| `HUIR_GIRO_S` | 1.2 | cuánto gira al huir | no llega a darle la espalda: subir (1.3). Se pasa: bajar (1.1) |
| `DIST_OBSTACULO_CM` | 30 | a qué distancia de algo deja de avanzar (huyendo o buscando) | queda muy cerca de las paredes: subir (40). En una sala chica gira demasiado sin avanzar: no bajar de 25 |
| `UMBRAL_POR_CLASE` (mochila) | 0.20 | confianza mínima para creer que es la mochila | huye de cosas del fondo: subir (0.30). No huye de la mochila: no bajar de 0.15 |

El umbral de la mochila es el único que no se puede probar con
`corrida_piso.sh`: se edita con `nano`, en la línea
`UMBRAL_POR_CLASE = {CLASE_AMENAZA: 0.20}`.

**Cambiar de a uno por vez**, y probar con una corrida después de cada cambio.
Si el cambio se quiere conservar, anotarlo: al volver a copiar el código desde
la PC (`.\scripts_pi\provisionar_pi.cmd`), el `config.py` del Pi se pisa con
el de la PC.

# 12. Traer el video y los registros a la notebook

Desde la PC (PowerShell, carpeta del proyecto), con el Pi prendido:

    .\scripts_pi\traer_corrida.cmd -Video          (la última corrida, con su video)
    .\scripts_pi\traer_corrida.cmd -Cuantas 10     (las últimas diez, sin video)

Quedan en la carpeta `logs\` del proyecto. El video es lo que ve el robot, con
las cajas y el estado dibujados, **sin sonido**; VLC lo abre seguro. Para volver a ver el
análisis en la PC: `cd src ; python analizar_corrida.py ..\logs\corrida_*.csv`
(con varias corridas arma una tabla y cuenta cuántas llegaron).

A mano, si el script fallara (con la dirección del Pi):

    scp -i $env:USERPROFILE\.ssh\id_ed25519_pi "admin@192.168.43.57:TPF/logs/corrida_2026*" logs\

# 13. Plan B

1. **Robot elevado** (ruedas al aire): si el piso da problemas, se ve igual cómo
   reacciona a lo que ve — las ruedas giran hacia el oso y cambian ante la
   mochila. Mismo comando `demo.sh correr`.
2. **Sin motores**: `python main.py --simular --espera 0 --duracion 60` (desde
   `~/TPF/src` con el entorno activado, §14). Percibe y decide igual, pero no
   manda nada al ESP32: se muestra moviendo el oso y la mochila frente a la
   cámara y mirando los estados en pantalla. No necesita los 12 V.
3. **Video grabado**: el clip de 20 s de la carpeta `presentacion_10min/`, o
   los dos de la carpeta `media/` (el del 01/10, de 89 s, es el más completo;
   el del 02/10 muestra la huida esquivando una pared en los primeros 8 s).

# 14. Comandos a mano (si `demo.sh` fallara)

    cd ~/TPF/src && source ../.venv/bin/activate  # siempre, antes de todo lo demás

    vcgencmd get_throttled                        # tiene que dar throttled=0x0
    vcgencmd pmic_read_adc EXT5V_V                # ~4,9 a 5,1 V
    vcgencmd measure_temp                         # menos de 75 °C
    ls /dev/video0 /dev/ttyUSB*                   # cámara y ESP32
    python prueba_estados.py | tail -5            # tiene que decir "Todo en orden"

    python ../scripts_pi/piso/franjas_quieto.py 6 # ¿imagen sana? (lo de demo.sh imagen)
    python ../scripts_pi/piso/sonar.py            # ¿mide el ultrasónico? (demo.sh sonar)
    python bench_vision.py --en-vivo              # ¿ve el oso? Ctrl+C sale
    python ../scripts_pi/piso/que_ve.py           # ¿como qué ve lo que tiene adelante?

    python main.py --espera 5 --duracion 60 --silencioso --nota "demo"
    python main.py --espera 5 --duracion 60 --silencioso --grabar --nota "con video"
    python analizar_corrida.py $(ls -t ../logs/corrida_*.csv | head -1)

    pkill -INT -f "python main.py"                # cortar una corrida colgada
    hostname -I                                   # la dirección del Pi
    sudo shutdown -h now                          # apagar

# 15. Al terminar

1. **Desenchufar los 12 V** de la UPS.
2. Si se quieren los registros o el video, traerlos ahora (§12).
3. `bash ~/TPF/scripts_pi/demo.sh apagar` (la sesión SSH se corta: es normal).
4. Esperar a que el **LED verde deje de parpadear** (~10 s) y recién ahí
   desconectar el cargador.

# 16. Números de referencia

| Qué | Valor normal |
|-------------|-------------|
| FPS del lazo completo | **~10,6** (~9,9 grabando video; mínimo aceptable: 5) |
| Línea `Imagen:` del análisis | **0 frames con franjas** |
| `get_throttled` | **0x0** |
| `EXT5V_V` | 4,9 a 5,1 V. Con las baterías enchufadas al cargador baja a ~4,7 y marca bajo voltaje |
| Ultrasónico, quieto | la distancia real, estable (30 cm a 30 cm; 153 cm a 1,5 m). Sin nada adelante: ~370 |
| Deja de avanzar (huyendo o buscando) | con algo a **30 cm** o menos; queda a ~27 cm |
| Da por alcanzado el oso por el sensor | a **20 cm** o menos (casi siempre frena antes, por tamaño) |
| Buzzer | alarma: 150 ms sí, 150 ms no, mientras huye · llegada: un tono de 1,2 s |
| Temperatura del Pi | 55–75 °C andando; a 80 °C recorta |
| Búsqueda | pasos de ~18° cada 0,85 s; una vuelta en ~17 s |
| Tiempo hasta frenar frente a un oso a 1 m | ~3 s si está de frente; 15–17 s si está a 90° a la izquierda |
| Alcance de detección (oso A4) | ~1,3 m |
| Campo visual de la cámara | ~52° |
| Distancia de frenado | **~30 cm** (decide frenar con `ar` = 0,35) |
| Confirmación del oso o de la mochila | ~0,2–0,3 s (3 frames) |
| Confianza típica | oso 0,85–0,95 · mochila 0,6 a 1 m y 0,3–0,4 a 1,2 m |
| Huida | 1,5 s atrás + 1,2 s de giro + 2,5 s adelante |
| Latencia foto → decisión | ~150 ms |
| Velocidad máxima | 0,25 m/s |
| Watchdog del ESP32 | frena a los 500 ms sin órdenes |
| Tiempo desde Enter hasta que se mueve | ~10–15 s |

# 17. Dónde está el resto

| Si hace falta... | Está en |
|--------------------------|---------------------------------|
| entender cómo funciona todo, archivo por archivo y parámetro por parámetro | `presentacion_resumen/TPF_resumen.pdf` |
| la presentación para exponer, con su guion | `presentacion_10min/` |
| regrabar el ESP32, reinstalar el Pi, recalibrar motores | `RUNBOOK.md` |
| medir las 10 corridas por escenario | `RUNBOOK.md`, Paso 23 |
| la prueba de corriente USB para la imagen rota | `RUNBOOK.md`, Paso 24 |
| el ultrasónico no contesta y los cables están bien | `RUNBOOK.md`, Paso 25 |
| cómo están cableados el ultrasónico y el buzzer | `HARDWARE.md` §9 |
| fotos del robot terminado | carpeta `Fotos del bot/` |
| qué se midió, cuándo y por qué vale cada número | `PLAN.md` §13 y `HARDWARE.md` |
| cada script de `scripts_pi/` | `scripts_pi/README.md` y `scripts_pi/piso/README.md` |

Para regenerar el PDF de esta hoja, en la PC:
`pandoc GUIA_PRESENTACION.md -o GUIA_PRESENTACION.pdf --pdf-engine=xelatex -V geometry:margin=1.6cm -V mainfont="Segoe UI" -V monofont="Consolas" -V fontsize=10pt`
