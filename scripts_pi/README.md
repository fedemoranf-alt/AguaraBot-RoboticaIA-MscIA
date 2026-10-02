# `scripts_pi/` — poner el Pi en marcha y operar el robot

Dos familias de scripts: los que corren **en la PC** (PowerShell, `.ps1`) y los
que corren **en el Pi** (`.sh` y `piso/`). Para operar el robot el día de la
presentación, la hoja es [GUIA_PRESENTACION.md](../GUIA_PRESENTACION.md): usa
sólo `entrar.ps1`, `demo.sh` y `traer_corrida.ps1`.

## En la PC

> **Los tres de uso diario se llaman por su `.cmd`**: `.\scripts_pi\entrar.cmd`,
> `.\scripts_pi\traer_corrida.cmd` y `.\scripts_pi\provisionar_pi.cmd`, con los
> mismos parámetros que el `.ps1`. La carpeta del proyecto está en Google
> Drive (`G:`), que Windows trata como ubicación remota: ahí PowerShell exige
> firma digital y `.\scripts_pi\entrar.ps1` falla con **"no está firmado
> digitalmente"** (pasó el 2026-10-02, la primera vez que el usuario lo corrió
> solo). El `.cmd` llama al `.ps1` salteando esa regla, sin cambiar la
> configuración de la PC. Para cualquier otro `.ps1` de esta carpeta:
> `powershell -ExecutionPolicy Bypass -File .\scripts_pi\<nombre>.ps1`.

| Script | Qué hace |
|---|---|
| `entrar.ps1` | ✅ Probado el 2026-10-02 buscando el Pi en el hotspot (`-SoloBuscar`). **Encuentra el Pi en la red y abre la sesión SSH.** Prueba el nombre `pi-MB.local`, la última IP con la que entró (`ultima_ip.txt`), la tabla ARP (por la placa de red del Pi) y, en redes chicas como un hotspot, barre todas las direcciones. `-SoloBuscar` sólo dice la IP; `-Ip` la fuerza; `-Comando "..."` corre un comando y sale |
| `provisionar_pi.ps1` | Copia `src/` y `scripts_pi/` al Pi, les saca los finales de línea de Windows, **corre las verificaciones del comportamiento allá** y hace el inventario. Sin `-Equipo`, busca el Pi con `entrar.ps1`. Se puede repetir. ✅ Probado el 2026-10-02 (`-Equipo` acepta ahora una IP pelada: antes entraba con el usuario de Windows y quedaba esperando una contraseña) |
| `traer_corrida.ps1` | Trae a `logs\` de la PC el CSV y el JSON de las últimas corridas (`-Cuantas N`) y, con `-Video`, el video (el `.mp4` si existe). ✅ Probado el 2026-10-02, después de dos arreglos: no copiaba nada por la ruta con espacios, y elegía el `.avi` en vez del `.mp4` |
| `verificar_sd.ps1` | Con la SD puesta en la PC: la lee **después de grabar y antes del primer arranque**. Confirma hostname, usuario, hash de contraseña, `ssh_pwauth`, WiFi y país. Sólo lee; nunca imprime contraseñas |
| `escribir_cloudinit.ps1` | Con la SD puesta en la PC: **repara** una SD que quedó sin personalizar, escribiendo el `user-data` / `network-config` a mano. Respalda los originales como `.orig` |

## En el Pi

| Script | Qué hace |
|---|---|
| `demo.sh` | **Los comandos de todos los días**, uno por acción (tabla de abajo) |
| `inventario_pi.sh` | Checklist de salida del Paso 11.5 del RUNBOOK, con veredicto por punto. Lo lanza `provisionar_pi.ps1` |
| `piso/` | Pruebas con el robot en el piso y diagnósticos de la cámara. Ver [piso/README.md](piso/README.md) |

### `demo.sh`

Se llama como `bash ~/TPF/scripts_pi/demo.sh <comando>`, desde una sesión SSH.

| Comando | Qué hace | Probado en el Pi |
|---|---|---|
| `chequeo` | Alimentación, temperatura, cámara, ESP32, las verificaciones del software y el disco. Termina con **LISTO** o con la lista de problemas y qué hacer | sí. El 2026-10-02 detectó bien el bajo voltaje y la cámara desenchufada |
| `imagen` | ¿Los frames llegan enteros? 6 s de captura sin motores ni YOLO; termina con un veredicto (SANA / DAÑADA A RATOS / ROTA). Llama a `piso/franjas_quieto.py` | sí, 2026-10-02: SANA con la cámara puesta, y el error de la cámara cuando estaba desenchufada |
| `ver` | Lo que detecta la cámara, frame a frame, y la foto anotada en `logs/vivo.jpg` | sí |
| `fondo` | Con el oso y la mochila fuera de la vista: ¿algo de la sala se confunde con ellos? Llama a `piso/que_ve.py` | ⬜ el comando no; el script que llama, sí |
| `sonar` | ¿Qué distancia mide el ultrasónico? 5 s sin motores. Si dice SIN LECTURA, se soltó un cable del sensor. Llama a `piso/sonar.py` | sí, 2026-10-02 |
| `correr [seg] [nota]` | La corrida: 5 s de espera, límite de tiempo (60 s por defecto) y, al terminar, el análisis. Si el programa falla antes de arrancar lo dice, en vez de mostrar el análisis de una corrida vieja | sí, 2026-10-02: cuatro corridas en el piso |
| `grabar [seg] [nota]` | Lo mismo, guardando el video de lo que ve el robot y pasándolo a MP4. Baja el lazo de ~10,6 a ~9,9 FPS | sí, 2026-10-02 |
| `ultima` | Vuelve a mostrar el análisis de la última corrida | sí |
| `parar` | Corta una corrida colgada (como Ctrl+C) | 🟡 sólo el caso "no hay corrida". Una corrida real se cortó a mano con la misma señal |
| `firmware` | Le pide al ESP32 sus parámetros de motores y los contadores del ultrasónico | sí |
| `red` | En qué WiFi está el Pi y qué redes tiene guardadas | sí, 2026-10-02 |
| `hotspot "NOMBRE" "CLAVE"` | Guarda el hotspot del celular, con prioridad sobre las otras redes. No cambia de red en el momento: el Pi lo toma al reiniciar | sí, 2026-10-02: el Pi arrancó en el hotspot y se entró por él |
| `apagar` | Apaga el Pi ordenadamente | sí |

Casi todos se escribieron el 2026-10-01 a la noche, con el Pi apagado, y se
estrenaron en el robot al día siguiente. El estreno encontró tres fallas, ya
corregidas: `correr` y `grabar` mostraban el análisis de la corrida anterior
cuando el programa moría antes de empezar; `firmware`, en su primer uso
después de encender el Pi, contestaba "comando desconocido"; y
`traer_corrida.ps1` no copiaba nada (más abajo). Queda sin estrenar `fondo`.

⚠️ **Cortar la sesión no corta la corrida.** Si se cierra la ventana o se
interrumpe el `ssh` mientras corre `demo.sh correr`, `main.py` puede seguir
andando en el Pi con el robot en movimiento (pasó el 2026-10-02). Parar siempre
con Ctrl+C dentro de la sesión, o entrar de nuevo y `demo.sh parar`.

## Orden de la primera puesta en marcha de un Pi

```powershell
cd "G:\Mi unidad\Maestria - IA\Cursos\5.Robotica-IA\TPF"

Update-HostStorageCache          # el Imager desmonta la SD al terminar
.\scripts_pi\verificar_sd.ps1    # antes de arrancar el Pi
# si sale "user-data es la plantilla de fabrica":
#   .\scripts_pi\escribir_cloudinit.ps1   y verificar de nuevo

# ... poner la SD en el Pi, alimentar, esperar 3-5 min ...
.\scripts_pi\provisionar_pi.cmd
```

Valores por defecto (lo grabado el 2026-09-04): hostname **`pi-MB`**, usuario
**`admin`**, país **`PY`**. La clave SSH es `~\.ssh\id_ed25519_pi`.

## Entrar al Pi cuando el nombre no resuelve

El 2026-10-01 `pi-MB.local` no resolvió aunque el Pi estaba prendido y en la
red de siempre. Desde entonces **no se confía sólo en el nombre**:

```powershell
.\scripts_pi\entrar.cmd                       # lo busca y entra
.\scripts_pi\entrar.cmd -Ip 192.168.43.57     # si ya se sabe la IP
```

Para reconocer al Pi en la tabla ARP, `entrar.ps1` usa la dirección de su
placa WiFi. La del robot propio se anota en `scripts_pi\mac_pi.txt` (una
línea, tal como la muestra `arp -a`); ese archivo **no se versiona**. Sin él,
busca por el prefijo del fabricante, que sirve mientras no haya otra Raspberry
Pi en la misma red.

A mano: `ssh -i $env:USERPROFILE\.ssh\id_ed25519_pi -o HostKeyAlias=pi-mb.local admin@<IP>`.
El alias hace que la huella se compare contra la ya conocida del Pi, así que si
en esa IP contesta otro equipo, `ssh` lo dice en vez de entrar. En un hotspot,
la IP del Pi aparece en la lista de dispositivos conectados del celular.

## Por qué existen los scripts de la SD

El Pi arranca **headless**: no hay cable micro-HDMI, así que la red es el único
camino de entrada. Eso invierte el costo de los errores — un SSH sin activar o
un país de WiFi mal puesto no dan ningún síntoma, el Pi simplemente no aparece,
y el diagnóstico cuesta más que el chequeo. `verificar_sd.ps1` mira eso mientras
la tarjeta todavía está en la PC, que es el último momento en que es barato.

Y no es hipotético: **el 2026-09-04 el Imager 2.0.8 grabó la tarjeta sin aplicar
la personalización** — la había guardado en el registro, pero con imagen
personalizada y en modo Offline nunca la escribió. La SD parecía correcta.
`escribir_cloudinit.ps1` nació de ahí. El detalle completo está en el RUNBOOK,
sección *"La trampa del Imager 2.x"*.

`inventario_pi.sh` resuelve además dos cosas que el proyecto tenía abiertas:

- **Si la Arducam es CSI o USB**, comparando `rpicam-hello --list-cameras`
  contra `v4l2-ctl --list-devices`. (La Arducam nunca funcionó; quedó una
  webcam USB.)
- **El rayo amarillo de bajo voltaje sin monitor**, vía `vcgencmd get_throttled`:
  `0x0` es todo bien, el bit 0 es bajo voltaje ahora mismo y el bit 16 que lo
  hubo desde el arranque.

## Notas para quien lea el código

- `verificar_sd.ps1` usa funciones `Bien` / `Mal` y no `Si` / `No`: en PowerShell
  en español **`si` es un alias de `Set-Item`**, y los alias ganan sobre las
  funciones en la resolución de comandos.
- Los `.ps1` nuevos **no llevan tildes ni eñes**: PowerShell 5.1 lee los
  archivos sin marca de orden de bytes como ANSI, y los mensajes saldrían rotos.
- En el Pi, cuidado con `pkill -f <patrón>` y `pgrep -f <patrón>` dentro de un
  `ssh ... "comando"`: el patrón aparece en la línea de comando del propio
  shell, y se mata o se encuentra a sí mismo. Escribir el patrón como
  `'[p]ython main.py'`.
