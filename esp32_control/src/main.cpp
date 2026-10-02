/*
 * TPF Robotica IA - Firmware de control (ESP32)
 * ==================================================================
 * Controlador de bajo nivel del robot. Recibe intencion de movimiento
 * desde la Raspberry Pi, la traduce a PWM, lee el ultrasonico, maneja
 * el buzzer y devuelve telemetria. NO toma decisiones de comportamiento:
 * eso vive en el Pi (PLAN.md seccion 4).
 *
 * Reemplaza a esp32_motor_test, que era solo bring-up de cableado.
 *
 * ------------------------------------------------------------------
 * PROTOCOLO (PLAN.md seccion 8) - ASCII, una orden por linea
 *
 *   Pi -> ESP32:
 *     M,<v_lin>,<v_ang>   enteros en [-100, 100]
 *     B,<patron>          0 = apagado, 1 = hallazgo, 2 = alarma
 *
 *   ESP32 -> Pi (a 20 Hz):
 *     D,<dist_cm>,<enc_izq>,<enc_der>
 *
 *   dist_cm = -1 significa "sin lectura valida" (fuera de rango o
 *   sensor no conectado). Los encoders son extension opcional
 *   (PLAN.md seccion 5, D5): mientras no esten cableados se emite 0,0.
 *
 *   Las lineas que empiezan con '#' son mensajes de diagnostico para
 *   humanos; el parser del Pi debe descartarlas.
 *
 * ------------------------------------------------------------------
 * WATCHDOG (obligatorio, PLAN.md seccion 8)
 *
 * Si no llega un comando M durante 500 ms, frena ambos motores. Cubre
 * cuelgue del proceso de vision, cable desconectado o crash del Pi.
 * Frena activo 200 ms y despues suelta a rueda libre, para no dejar el
 * puente en corto indefinidamente.
 *
 * ------------------------------------------------------------------
 * MODO MANUAL
 *
 * Las teclas sueltas (w/s/a/d/x/...) permiten manejar el robot desde el
 * monitor serie sin el Pi conectado. Mismo juego de teclas que
 * esp32_motor_test, pero a diferencia de aquel hay que apretar ENTER
 * despues de cada tecla: aca el parser trabaja por lineas, porque tiene
 * que distinguir una tecla suelta de un comando 'M,...'.
 *
 * ATENCION: el modo manual DESACTIVA el watchdog
 * (si no, cada comando se apagaria a los 500 ms). Usarlo solo en banco,
 * con las ruedas al aire. Cualquier comando M vuelve a modo protocolo y
 * reactiva el watchdog.
 * ==================================================================
 */

#include <Arduino.h>

/* ==================================================================
 * 1. Pines
 *
 * Motores: cableado real verificado en el bring-up, HARDWARE.md
 * seccion 6. Los rotulos ENA/IN1/... son los del modulo L298N, no el
 * lado del robot; el mapeo a ruedas esta mas abajo.
 * ================================================================== */
#define PIN_ENA 25 /* PWM canal A       */
#define PIN_IN1 26 /* direccion canal A */
#define PIN_IN2 27 /* direccion canal A */

#define PIN_ENB 13 /* PWM canal B       */
#define PIN_IN3 33 /* direccion canal B */
#define PIN_IN4 32 /* direccion canal B */

/* Ultrasonico HC-SR04 - HARDWARE.md seccion 9.
 *
 * OJO: el pin ECHO del HC-SR04 entrega 5 V y el ESP32 NO tolera 5 V en
 * un GPIO. Va con divisor resistivo 1k / 2k (5 V -> 3,3 V). Sin el
 * divisor se dania el pin. TRIG si acepta 3,3 V directo: el umbral de
 * entrada del HC-SR04 es TTL. */
#define PIN_TRIG 18
#define PIN_ECHO 19

/* Buzzer - HARDWARE.md seccion 9. */
#define PIN_BUZZER 4

/* Reservados para los encoders (extension opcional, PLAN.md D5).
 * Los cuatro son pines de solo entrada, que es justo lo que hace falta,
 * y no tienen pull-up interno: eso encaja con el pull-up externo de
 * 10k a 3,3 V que pide HARDWARE.md seccion 3.1 para las salidas de
 * colector abierto del encoder.
 *
 *   34 = encoder izq A    35 = encoder izq B
 *   36 = encoder der A    39 = encoder der B
 */

/* ------------------------------------------------------------------
 * Mapeo canal del modulo <-> rueda
 *
 * Verificado en el bring-up: el canal A quedo cableado a la rueda
 * DERECHA (HARDWARE.md seccion 6.3). Se corrige aca, no en la bornera.
 * Si algun dia se recablea, este bloque es lo unico que cambia.
 * ------------------------------------------------------------------ */
#define PIN_LEFT_PWM PIN_ENB
#define PIN_LEFT_A PIN_IN3
#define PIN_LEFT_B PIN_IN4

#define PIN_RIGHT_PWM PIN_ENA
#define PIN_RIGHT_A PIN_IN1
#define PIN_RIGHT_B PIN_IN2

#define WHEEL_LEFT 0
#define WHEEL_RIGHT 1

/* Canales LEDC (solo se usan en el core 2.x de Arduino-ESP32).
 * Los canales 0 y 1 comparten el timer 0, asi que ambos motores deben
 * ir a la misma frecuencia y resolucion - lo estan. El buzzer necesita
 * su propia frecuencia, por eso va al canal 2 (timer 1). */
#define PWM_CH_LEFT 0
#define PWM_CH_RIGHT 1
#define PWM_CH_BUZZER 2

/* ==================================================================
 * 2. Parametros de PWM y compensacion de zona muerta
 *
 * Resolucion de 10 bits (HARDWARE.md seccion 0.4, palanca A). Con 8 bits
 * la rueda izquierda quedaba con 24 cuentas utiles entre su v_min y
 * v_max; con 10 bits son 96. No cambia la fisica, cambia la granularidad.
 *
 * Todos los umbrales estan en cuentas de 10 bits. Los valores medidos en
 * el bring-up eran de 8 bits, asi que van multiplicados por 4.
 * ================================================================== */
#define PWM_RES_BITS 10
#define PWM_MAX 1023

/* 1 kHz es el valor validado en el bring-up. HARDWARE.md seccion 0.4
 * palanca D propone probar 100-200 Hz para mejorar el par de arranque:
 * con tau electrica de 0,1-0,3 ms, a 1 kHz y duty bajo la corriente no
 * llega a establecerse. Probar con la tecla 'f' en modo manual. */
#define PWM_FREQ_HZ 1000

/* Techo de velocidad, POR RUEDA (HARDWARE.md seccion 0.5).
 *
 * Medido el 2026-08-27 con el modo calibracion, ventanas de 10 s:
 *
 *   duty | vueltas izq | vueltas der
 *    141 |      0      |      0
 *    211 |     16      |     11
 *    282 |     27      |     16
 *    352 |     35      |     20
 *
 * Ajuste lineal vueltas/10s = k * (duty - piso):
 *   izquierda  k = 0,1348   piso = 89
 *   derecha    k = 0,0639   piso = 36
 *
 * !! Las dos ruedas NO son iguales: la izquierda da 2,11 veces mas
 * velocidad por cuenta de duty. No es friccion, es una diferencia de
 * constante del conjunto motor+reductor. Ver HARDWARE.md 0.5.
 *
 * La rueda LENTA (derecha) manda: se queda en 352 y la izquierda se
 * baja hasta dar las mismas vueltas. Con esto las dos siguen la misma
 * recta de velocidad en todo el rango (verificado, error < 1 %).
 *
 * Velocidad resultante a u = 1: 0,38 m/s (rueda de 60 mm), o sea 7,6 cm
 * entre frames a 5 FPS. Dentro del presupuesto del lazo de vision.
 * Si se quisiera exactamente 0,30 m/s: 207 / 286.
 *
 * !! 2026-09-30 - RECALIBRADO EN EL PISO. Todo lo de arriba se midio con
 * las RUEDAS AL AIRE, y en el piso la rueda izquierda se calaba a
 * cualquier comando: pitaba y no giraba, ni siquiera con v_ang = 100.
 * Es la rueda de reduccion ~2,1 veces menor, o sea la que da la mitad de
 * par en la rueda, y la calibracion al aire le daba ademas el MENOR duty
 * (techo 23 % contra 34 %). Sin carga alcanzaba; con el peso del robot no.
 *
 * Medido con el robot apoyado, pivoteando sobre la otra rueda (modo C):
 *
 *   rueda | arranca desde parado | sigue girando hasta | al aire
 *   izq   |   entre 300 y 350    |   entre 260 y 290   |  ~106
 *   der   |   entre 200 y 250    |   entre 190 y 220   |   ~98
 *
 * Modelo: la carga SUMA un escalon de duty (hace falta corriente para dar
 * par) y NO cambia la pendiente (la velocidad la fija la fuerza
 * contraelectromotriz). Por eso piso y techo suben LA MISMA cantidad en
 * cada rueda, y se conserva el span de la calibracion al aire, que es el
 * que iguala las velocidades: izquierda 113, derecha 240.
 *
 *   izq: 125..238 -> 300..413   (+175)
 *   der: 112..352 -> 230..470   (+118)
 *
 * Los valores al aire quedan en este comentario: son los correctos para
 * el banco, y el error fue usarlos fuera de el. */
#define PWM_TOP_LEFT 413
#define PWM_TOP_RIGHT 470

/* Piso de cada rueda. Los dos motores difieren 2:1 en friccion de
 * arranque (HARDWARE.md seccion 0.4): la derecha arranca en 32 y la
 * izquierda en 64, en escala de 8 bits. Sin compensar por rueda, a
 * comandos bajos solo gira la derecha y el robot se va de trompa.
 *
 * OJO - estos son los umbrales ESTATICOS (desde parado). El numero que
 * corresponde aca es el CINETICO (el minimo para SEGUIR girando), que
 * es menor y todavia no se midio: es tarea del Dia 5, HARDWARE.md
 * seccion 0.4 palanca B. Hasta entonces se usan los estaticos, que son
 * conservadores: el robot anda, pero no tan lento como podria. */
/*
 * Piso de la recta de cada rueda. MEDIDO con la rampa 'K' el 2026-08-27.
 *
 * OJO con que es este numero: NO es el corte con cero de la recta de
 * velocidad. Es el duty de la MINIMA VELOCIDAD QUE LAS DOS RUEDAS PUEDEN
 * SOSTENER. Son cosas muy distintas y confundirlas fue un error real:
 *
 *   rueda | corte con cero | duty de calado medido
 *   izq   |       89       |         ~106
 *   der   |       36       |          ~98
 *
 * El corte con cero es una extrapolacion matematica de una recta
 * ajustada entre duty 211 y 352. La rueda se planta MUCHO antes de
 * llegar ahi, porque cerca de velocidad cero la friccion crece mas que
 * lineal. En la derecha la diferencia es de 62 cuentas.
 *
 * Con los cortes con cero cargados como piso, la derecha quedaba por
 * debajo de su calado para todo u < 0,22: se plantaba a comando chico.
 *
 * Velocidad minima que sostiene cada rueda:
 *   izquierda  2,6 vueltas/10 s   (0,049 m/s)
 *   derecha    4,5 vueltas/10 s   (0,084 m/s)  <- manda esta
 *
 * La derecha no puede ir mas lento que eso, asi que fija el piso comun.
 * Estos valores son el duty al que cada rueda da esa velocidad comun,
 * con margen sobre el calado medido.
 *
 * Rango util resultante: 0,091 a 0,380 m/s, o sea 4,2:1.
 * !! u > 0 garantiza al menos 0,091 m/s: NO hay arranque suave desde
 * cero. Para parar hay que mandar exactamente 0. */
/* Al aire eran 125 / 112 (calado ~106 / ~98). En el piso, ver el
 * recalibrado del 2026-09-30 junto a PWM_TOP_*: calado entre 260-290 y
 * 190-220, medido pivoteando, que es mas exigente que andar derecho. */
#define PWM_MIN_LEFT 300  /* en el piso: gira a 290, se para a 260 */
#define PWM_MIN_RIGHT 230 /* en el piso: gira a 220, se para a 190 */

/* Pulso de arranque (HARDWARE.md seccion 0.4, palanca C). Al pasar de
 * reposo a movimiento se aplica el umbral estatico durante unos ms para
 * romper la friccion, y recien despues se cae al duty objetivo.
 *
 * Desde 2026-08-27 el pulso esta ACTIVO: los PWM_MIN_* bajaron al piso
 * cinetico estimado (89 / 36) y quedaron muy por debajo de estos
 * umbrales estaticos, asi que a comando chico la rueda no arrancaria
 * sola. El pulso la despega y despues cae al duty que corresponde.
 *
 * BREAKAWAY_MS es un compromiso a ajustar en el piso:
 *   muy corto -> la rueda no alcanza velocidad y se planta al caer
 *   muy largo -> tiron visible en cada arranque
 * 80 ms es el punto de partida, sin medir. */
/* Umbrales ESTATICOS acotados con los datos del 2026-08-27, que son mas
 * finos que la rampa de 15 cuentas del bring-up:
 *
 *   izquierda: NO arranca sola a 211, SI a 282  -> umbral en (211, 282]
 *   derecha:   NO arranca sola a 141, SI a 211  -> umbral en (141, 211]
 *
 * Los valores del bring-up (256 y 128 en 10 bits) quedaron por DEBAJO
 * del techo del intervalo, sobre todo el de la derecha: con 128 el pulso
 * no habria despegado la rueda. Se toma el techo del intervalo con algo
 * de margen. Bajarlos despues si el tiron al arrancar molesta. */
/* 2026-09-30, en el piso: al aire eran 290 / 220 durante 80 ms. Apoyado,
 * la izquierda arranca entre 300 y 350 y la derecha entre 200 y 250; se
 * toma el techo con margen. Y el pulso se alarga a 150 ms: con el peso
 * del robot la rueda tarda mas en tomar velocidad, y como el piso quedo
 * cerca del calado, si el pulso termina antes se vuelve a plantar. */
#define PWM_BREAKAWAY_LEFT 380
#define PWM_BREAKAWAY_RIGHT 280
#define BREAKAWAY_MS 150

/* ==================================================================
 * 3. Tiempos
 * ================================================================== */
#define CMD_TIMEOUT_MS 500     /* watchdog - PLAN.md seccion 8 */
#define WD_BRAKE_MS 200        /* freno activo antes de soltar a coast */
#define CONTROL_PERIOD_MS 10   /* 100 Hz */
#define TELEMETRY_PERIOD_MS 50 /* 20 Hz - PLAN.md seccion 8 */
#define PING_PERIOD_MS 60      /* HC-SR04: minimo 60 ms entre disparos */
#define ECHO_TIMEOUT_US 30000  /* ~5 m; el sensor llega a 4 */

/* ==================================================================
 * 4. Estado global
 * ================================================================== */

/* Comando vigente, ya mezclado a ruedas, en [-100, 100]. */
static int g_cmd_left = 0;
static int g_cmd_right = 0;

/* Ultimo duty aplicado a cada rueda, con signo. Sirve para detectar la
 * transicion parado -> en movimiento que dispara el breakaway. */
static int g_last_duty[2] = {0, 0};
static uint32_t g_move_start_ms[2] = {0, 0};

static uint32_t g_last_cmd_ms = 0;
static bool g_wd_tripped = false;
static uint32_t g_wd_trip_ms = 0;

static bool g_manual = false;     /* modo banco: watchdog desactivado */
static bool g_deadzone_on = true; /* 'z' lo apaga para comparar */
static int g_manual_speed = 60;   /* porcentaje */

static uint32_t g_pwm_freq = PWM_FREQ_HZ;

/* La telemetria a 20 Hz hace scrollear el monitor sin parar y tipear un
 * comando se vuelve incomodo. La tecla 't' la silencia; no afecta al
 * modo protocolo, donde el Pi la necesita siempre. */
static bool g_telemetry_on = true;

/* ------------------------------------------------------------------
 * Modo calibracion (banco, Dia 5)
 *
 * Sirve para medir lo que la ley de control necesita y todavia no se
 * midio: el v_min CINETICO de cada rueda y la velocidad real de cada
 * rueda a un duty dado. Ver HARDWARE.md secciones 0.4 y 0.5.
 *
 * Con g_calib activo se escribe el duty CRUDO a la rueda, salteando la
 * compensacion de zona muerta y el pulso de arranque: aca se mide el
 * motor, no la ley de control. Tambien desactiva el watchdog, como el
 * modo manual.
 * ------------------------------------------------------------------ */
static bool g_calib = false;
static int g_calib_duty[2] = {0, 0};

/* Rampa descendente para el v_min cinetico: arranca la rueda a un duty
 * que la mueve seguro y baja de a poco. El operador marca con ENTER el
 * momento en que la rueda se detiene. */
#define RAMP_STEP_MS 100 /* periodo de bajada */
#define RAMP_STEP 2      /* cuentas por paso -> 20 cuentas/s */
static bool g_ramp_active = false;
static int g_ramp_wheel = 0;
static int g_ramp_duty = 0;
static uint32_t g_ramp_last_ms = 0;

/* Ventana cronometrada: corre una rueda a duty fijo durante N ms y
 * frena sola, para contar vueltas con una marca de cinta. */
static bool g_window_active = false;
static uint32_t g_window_end_ms = 0;

/* Ultrasonico */
static volatile uint32_t g_echo_rise_us = 0;
static volatile uint32_t g_echo_width_us = 0;
static volatile bool g_echo_ready = false;
static uint32_t g_ping_sent_ms = 0;
static bool g_ping_pending = false;
static int g_distance_cm = -1;

/* Buzzer */
static int g_buzz_pattern = 0;
static uint32_t g_buzz_phase_ms = 0;
static bool g_buzz_on = false;

/* Parser de linea */
#define CMD_LINE_MAX 32
static char g_line[CMD_LINE_MAX];
static int g_line_len = 0;

/* ==================================================================
 * 5. Capa de PWM
 *
 * El core 3.x de Arduino-ESP32 cambio la API de LEDC: ledcSetup() y
 * ledcAttachPin() se reemplazaron por ledcAttach(), y ledcWrite() pasa a
 * recibir el pin en vez del canal. Este bloque compila con ambos.
 * ================================================================== */
static void pwm_init(uint8_t pin, uint8_t channel, uint32_t freq)
{
#if defined(ESP_ARDUINO_VERSION_MAJOR) && (ESP_ARDUINO_VERSION_MAJOR >= 3)
    (void)channel;
    ledcAttach(pin, freq, PWM_RES_BITS);
#else
    ledcSetup(channel, freq, PWM_RES_BITS);
    ledcAttachPin(pin, channel);
#endif
}

static void pwm_write(uint8_t pin, uint8_t channel, uint32_t duty)
{
#if defined(ESP_ARDUINO_VERSION_MAJOR) && (ESP_ARDUINO_VERSION_MAJOR >= 3)
    (void)channel;
    ledcWrite(pin, duty);
#else
    (void)pin;
    ledcWrite(channel, duty);
#endif
}

static void pwm_set_freq(uint8_t pin, uint8_t channel, uint32_t freq)
{
#if defined(ESP_ARDUINO_VERSION_MAJOR) && (ESP_ARDUINO_VERSION_MAJOR >= 3)
    (void)channel;
    ledcChangeFrequency(pin, freq, PWM_RES_BITS);
#else
    (void)pin;
    ledcSetup(channel, freq, PWM_RES_BITS);
#endif
}

static void tone_write(uint8_t pin, uint8_t channel, uint32_t freq)
{
#if defined(ESP_ARDUINO_VERSION_MAJOR) && (ESP_ARDUINO_VERSION_MAJOR >= 3)
    (void)channel;
    ledcWriteTone(pin, freq);
#else
    (void)pin;
    ledcWriteTone(channel, freq);
#endif
}

/* ==================================================================
 * 6. Motores
 *
 * Tabla de verdad del L298 (por puente):
 *   EN=H, IN_A=H, IN_B=L  -> giro en un sentido
 *   EN=H, IN_A=L, IN_B=H  -> giro en el otro sentido
 *   EN=H, IN_A=IN_B       -> freno activo
 *   EN=L                  -> rueda libre (coast)
 * ================================================================== */

static void wheel_pins(int wheel, uint8_t *pin_a, uint8_t *pin_b,
                       uint8_t *pin_en, uint8_t *channel)
{
    if (wheel == WHEEL_LEFT) {
        *pin_a = PIN_LEFT_A;
        *pin_b = PIN_LEFT_B;
        *pin_en = PIN_LEFT_PWM;
        *channel = PWM_CH_LEFT;
    } else {
        *pin_a = PIN_RIGHT_A;
        *pin_b = PIN_RIGHT_B;
        *pin_en = PIN_RIGHT_PWM;
        *channel = PWM_CH_RIGHT;
    }
}

/* duty en [-PWM_MAX, PWM_MAX]. Signo = sentido, 0 = rueda libre. */
static void wheel_raw(int wheel, int duty)
{
    uint8_t pin_a, pin_b, pin_en, channel;

    wheel_pins(wheel, &pin_a, &pin_b, &pin_en, &channel);

    if (duty > PWM_MAX) {
        duty = PWM_MAX;
    }
    if (duty < -PWM_MAX) {
        duty = -PWM_MAX;
    }

    if (duty > 0) {
        digitalWrite(pin_a, HIGH);
        digitalWrite(pin_b, LOW);
        pwm_write(pin_en, channel, (uint32_t)duty);
    } else if (duty < 0) {
        digitalWrite(pin_a, LOW);
        digitalWrite(pin_b, HIGH);
        pwm_write(pin_en, channel, (uint32_t)(-duty));
    } else {
        digitalWrite(pin_a, LOW);
        digitalWrite(pin_b, LOW);
        pwm_write(pin_en, channel, 0);
    }
}

static void wheel_brake(int wheel)
{
    uint8_t pin_a, pin_b, pin_en, channel;

    wheel_pins(wheel, &pin_a, &pin_b, &pin_en, &channel);

    digitalWrite(pin_a, HIGH);
    digitalWrite(pin_b, HIGH);
    pwm_write(pin_en, channel, PWM_MAX);
}

static void wheels_coast(void)
{
    wheel_raw(WHEEL_LEFT, 0);
    wheel_raw(WHEEL_RIGHT, 0);
    g_last_duty[WHEEL_LEFT] = 0;
    g_last_duty[WHEEL_RIGHT] = 0;
}

static void wheels_brake(void)
{
    wheel_brake(WHEEL_LEFT);
    wheel_brake(WHEEL_RIGHT);
    g_last_duty[WHEEL_LEFT] = 0;
    g_last_duty[WHEEL_RIGHT] = 0;
}

/*
 * Compensacion de zona muerta - PLAN.md seccion 7.
 *
 *   u = |cmd| / 100                       magnitud normalizada en (0, 1]
 *   pwm = v_min_rueda + (v_max - v_min_rueda) * u
 *
 * Vive en el ESP32 y no en el Pi porque los v_min estan en cuentas de
 * PWM, que es justamente lo que el protocolo abstrae: el Pi manda
 * intencion normalizada, el ESP32 la traduce a su hardware.
 */
static int deadzone_map(int wheel, int cmd)
{
    int magnitude, pwm_min, pwm_top, span, duty;

    magnitude = cmd < 0 ? -cmd : cmd;
    if (magnitude == 0) {
        return 0;
    }
    if (magnitude > 100) {
        magnitude = 100;
    }

    pwm_top = (wheel == WHEEL_LEFT) ? PWM_TOP_LEFT : PWM_TOP_RIGHT;

    if (!g_deadzone_on) {
        /* Sin compensar: misma recta para las dos ruedas, desde cero.
         * Es el caso "malo" que sirve de contraste en la prueba. */
        duty = (pwm_top * magnitude) / 100;
        return cmd < 0 ? -duty : duty;
    }

    pwm_min = (wheel == WHEEL_LEFT) ? PWM_MIN_LEFT : PWM_MIN_RIGHT;
    span = pwm_top - pwm_min;
    duty = pwm_min + (span * magnitude) / 100;

    return cmd < 0 ? -duty : duty;
}

/* Aplica el comando vigente de una rueda, con pulso de arranque. */
static void wheel_apply(int wheel, int cmd)
{
    int duty, breakaway;
    uint32_t now;

    duty = deadzone_map(wheel, cmd);
    now = millis();

    if (duty != 0 && g_last_duty[wheel] == 0) {
        g_move_start_ms[wheel] = now; /* arranca desde parado */
    }

    if (duty != 0 && (now - g_move_start_ms[wheel]) < BREAKAWAY_MS) {
        breakaway = (wheel == WHEEL_LEFT) ? PWM_BREAKAWAY_LEFT
                                          : PWM_BREAKAWAY_RIGHT;
        if (duty > 0 && duty < breakaway) {
            duty = breakaway;
        } else if (duty < 0 && -duty < breakaway) {
            duty = -breakaway;
        }
    }

    wheel_raw(wheel, duty);
    g_last_duty[wheel] = duty;
}

/*
 * Mezcla diferencial: (v_lin, v_ang) -> (izquierda, derecha).
 *
 * v_ang positivo = la rueda izquierda empuja mas que la derecha, o sea
 * el robot gira hacia la derecha. Con v_lin = 0 rota en el lugar.
 *
 * Si algun lado se pasa de 100 se escala el par completo en vez de
 * recortar cada rueda por separado: recortar cambiaria la relacion
 * entre ruedas y por lo tanto la curvatura pedida.
 */
static void mix(int v_lin, int v_ang, int *left, int *right)
{
    int l, r, peak, mag;

    l = v_lin + v_ang;
    r = v_lin - v_ang;

    peak = (l < 0 ? -l : l);
    mag = (r < 0 ? -r : r);
    if (mag > peak) {
        peak = mag;
    }

    if (peak > 100) {
        l = (l * 100) / peak;
        r = (r * 100) / peak;
    }

    *left = l;
    *right = r;
}

/* ==================================================================
 * 7. Ultrasonico HC-SR04 - no bloqueante
 *
 * Un pulseIn() con timeout de 30 ms bloquearia el lazo de control, que
 * corre a 100 Hz. En vez de eso se dispara el TRIG y se mide el ancho
 * del ECHO por interrupcion; el resultado se recoge en el lazo.
 * ================================================================== */
static void IRAM_ATTR echo_isr(void)
{
    if (digitalRead(PIN_ECHO)) {
        g_echo_rise_us = micros();
    } else {
        g_echo_width_us = micros() - g_echo_rise_us;
        g_echo_ready = true;
    }
}

static void ping_send(void)
{
    g_echo_ready = false;
    digitalWrite(PIN_TRIG, LOW);
    delayMicroseconds(4);
    digitalWrite(PIN_TRIG, HIGH);
    delayMicroseconds(10);
    digitalWrite(PIN_TRIG, LOW);

    g_ping_sent_ms = millis();
    g_ping_pending = true;
}

static void ping_poll(void)
{
    uint32_t width;

    if (!g_ping_pending) {
        return;
    }

    if (g_echo_ready) {
        noInterrupts();
        width = g_echo_width_us;
        g_echo_ready = false;
        interrupts();

        /* 343 m/s ida y vuelta -> 58 us por cm */
        if (width > 0 && width < ECHO_TIMEOUT_US) {
            g_distance_cm = (int)(width / 58);
        } else {
            g_distance_cm = -1;
        }
        g_ping_pending = false;
        return;
    }

    /* Sin eco: fuera de rango, o el sensor no esta conectado. */
    if ((millis() - g_ping_sent_ms) > (ECHO_TIMEOUT_US / 1000 + 5)) {
        g_distance_cm = -1;
        g_ping_pending = false;
    }
}

/* ==================================================================
 * 8. Buzzer - no bloqueante
 *
 * Patron 1 = hallazgo (tono largo, una vez).
 * Patron 2 = alarma (intermitente, hasta que llegue B,0).
 *
 * Escrito para buzzer PASIVO (hay que generarle el tono). Si el buzzer
 * es ACTIVO (suena solo con nivel alto), poner BUZZER_PASSIVE en 0.
 * ================================================================== */
#define BUZZER_PASSIVE 1
#define BUZZ_FREQ_FOUND 2000
#define BUZZ_FREQ_ALARM 3000
#define BUZZ_FOUND_MS 1200
#define BUZZ_ALARM_ON_MS 150
#define BUZZ_ALARM_OFF_MS 150

static void buzz_output(bool on, uint32_t freq)
{
#if BUZZER_PASSIVE
    tone_write(PIN_BUZZER, PWM_CH_BUZZER, on ? freq : 0);
#else
    (void)freq;
    digitalWrite(PIN_BUZZER, on ? HIGH : LOW);
#endif
    g_buzz_on = on;
}

static void buzz_set(int pattern)
{
    g_buzz_pattern = pattern;
    g_buzz_phase_ms = millis();

    if (pattern == 1) {
        buzz_output(true, BUZZ_FREQ_FOUND);
    } else if (pattern == 2) {
        buzz_output(true, BUZZ_FREQ_ALARM);
    } else {
        buzz_output(false, 0);
    }
}

static void buzz_update(void)
{
    uint32_t elapsed = millis() - g_buzz_phase_ms;

    if (g_buzz_pattern == 1) {
        if (elapsed >= BUZZ_FOUND_MS) {
            buzz_set(0);
        }
    } else if (g_buzz_pattern == 2) {
        if (g_buzz_on && elapsed >= BUZZ_ALARM_ON_MS) {
            buzz_output(false, 0);
            g_buzz_phase_ms = millis();
        } else if (!g_buzz_on && elapsed >= BUZZ_ALARM_OFF_MS) {
            buzz_output(true, BUZZ_FREQ_ALARM);
            g_buzz_phase_ms = millis();
        }
    }
}

/* ==================================================================
 * 9. Modo manual (banco de pruebas, sin el Pi)
 * ================================================================== */
/* Definida en la seccion 10 (calibracion); 'x' y 'p' la necesitan. */
static void calib_stop(void);

static void print_help(void)
{
    Serial.println();
    Serial.println("# --- modo manual (watchdog DESACTIVADO) ---");
    Serial.println("#   w / s   adelante / atras");
    Serial.println("#   a / d   girar izq / der en el lugar");
    Serial.println("#   x       parar (rueda libre)");
    Serial.println("#   b       frenar (freno activo)");
    Serial.println("#   1 / 2   solo rueda izquierda / derecha");
    Serial.println("#   + / -   velocidad +/- 10 %");
    Serial.println("#   z       zona muerta on/off (para comparar)");
    Serial.println("#   f       ciclar PWM: 1000/500/200/100 Hz");
    Serial.println("#   t       telemetria on/off (para poder leer)");
    Serial.println("#   e       mostrar parametros");
    Serial.println("#   p       volver a modo protocolo (watchdog ON)");
    Serial.println("#   ?       esta ayuda");
    Serial.println("# Cualquier comando M,... tambien vuelve a protocolo.");
    Serial.println();
    Serial.println("# --- calibracion (Dia 5), duty CRUDO sin compensar ---");
    Serial.println("#   K,<r>[,<duty0>]     rampa abajo -> v_min cinetico");
    Serial.println("#                       ENTER cuando la rueda se detenga");
    Serial.println("#   V,<r>,<duty>,<ms>   ventana cronometrada -> contar vueltas");
    Serial.println("#   C,<r>,<duty>        duty crudo fijo");
    Serial.println("#   r: 0=izq 1=der 2=ambas   |  'x' aborta");
    Serial.println();
}

static void print_params(void)
{
    Serial.println();
    Serial.printf("# modo         : %s\n",
                  g_manual ? "MANUAL (sin watchdog)" : "protocolo");
    Serial.printf("# PWM          : %lu Hz, %d bits (0..%d)\n",
                  (unsigned long)g_pwm_freq, PWM_RES_BITS, PWM_MAX);
    Serial.printf("# v_max izq/der: %d / %d\n", PWM_TOP_LEFT, PWM_TOP_RIGHT);
    Serial.printf("# v_min izq/der: %d / %d  (zona muerta %s)\n",
                  PWM_MIN_LEFT, PWM_MIN_RIGHT, g_deadzone_on ? "ON" : "OFF");
    Serial.printf("# breakaway    : %d / %d durante %d ms\n",
                  PWM_BREAKAWAY_LEFT, PWM_BREAKAWAY_RIGHT, BREAKAWAY_MS);
    Serial.printf("# vel. manual  : %d %%\n", g_manual_speed);
    Serial.printf("# distancia    : %d cm\n", g_distance_cm);
    Serial.println();
}

static void manual_enter(void)
{
    if (!g_manual) {
        g_manual = true;
        g_wd_tripped = false;
        Serial.println("# MODO MANUAL - watchdog desactivado, ruedas al aire");
    }
}

static void manual_command(char c)
{
    int v = g_manual_speed;

    switch (c) {
    case 'w':
        manual_enter();
        g_cmd_left = v;
        g_cmd_right = v;
        break;
    case 's':
        manual_enter();
        g_cmd_left = -v;
        g_cmd_right = -v;
        break;
    case 'a':
        manual_enter();
        g_cmd_left = -v;
        g_cmd_right = v;
        break;
    case 'd':
        manual_enter();
        g_cmd_left = v;
        g_cmd_right = -v;
        break;
    case '1':
        manual_enter();
        g_cmd_left = v;
        g_cmd_right = 0;
        break;
    case '2':
        manual_enter();
        g_cmd_left = 0;
        g_cmd_right = v;
        break;
    case 'x':
        g_cmd_left = 0;
        g_cmd_right = 0;
        calib_stop(); /* aborta rampa o ventana si habia una en curso */
        g_calib = false;
        Serial.println("# parar");
        break;
    case 'b':
        g_cmd_left = 0;
        g_cmd_right = 0;
        wheels_brake();
        Serial.println("# freno activo");
        break;
    case '+':
        g_manual_speed += 10;
        if (g_manual_speed > 100) {
            g_manual_speed = 100;
        }
        Serial.printf("# velocidad = %d %%\n", g_manual_speed);
        break;
    case '-':
        g_manual_speed -= 10;
        if (g_manual_speed < 0) {
            g_manual_speed = 0;
        }
        Serial.printf("# velocidad = %d %%\n", g_manual_speed);
        break;
    case 'z':
        g_deadzone_on = !g_deadzone_on;
        Serial.printf("# zona muerta %s\n", g_deadzone_on ? "ON" : "OFF");
        break;
    case 'f':
        if (g_pwm_freq == 1000) {
            g_pwm_freq = 500;
        } else if (g_pwm_freq == 500) {
            g_pwm_freq = 200;
        } else if (g_pwm_freq == 200) {
            g_pwm_freq = 100;
        } else {
            g_pwm_freq = 1000;
        }
        pwm_set_freq(PIN_LEFT_PWM, PWM_CH_LEFT, g_pwm_freq);
        pwm_set_freq(PIN_RIGHT_PWM, PWM_CH_RIGHT, g_pwm_freq);
        Serial.printf("# PWM = %lu Hz\n", (unsigned long)g_pwm_freq);
        break;
    case 't':
        g_telemetry_on = !g_telemetry_on;
        Serial.printf("# telemetria %s\n", g_telemetry_on ? "ON" : "OFF");
        break;
    case 'e':
        print_params();
        break;
    case 'p':
        g_manual = false;
        g_cmd_left = 0;
        g_cmd_right = 0;
        calib_stop();
        g_calib = false;
        g_last_cmd_ms = millis();
        Serial.println("# modo protocolo - watchdog ACTIVO");
        break;
    case '?':
        print_help();
        break;
    default:
        break;
    }
}

/* ==================================================================
 * 10. Modo calibracion (Dia 5)
 *
 * Mide lo que la ley de control necesita y todavia no se midio. Dos
 * rutinas, las dos sobre duty CRUDO (sin zona muerta, sin breakaway):
 * aca se caracteriza el motor, no la ley de control.
 *
 *   K,<rueda>[,<duty0>]        rampa descendente -> v_min cinetico
 *   V,<rueda>,<duty>,<ms>      ventana cronometrada -> velocidad
 *   C,<rueda>,<duty>           duty crudo fijo (0 = soltar)
 *
 *   rueda: 0 = izquierda, 1 = derecha, 2 = ambas
 * ================================================================== */

static void calib_enter(void)
{
    manual_enter(); /* apaga el watchdog y avisa */
    g_calib = true;
    g_cmd_left = 0;
    g_cmd_right = 0;

    /* Calibrar es leer numeros de la consola; la telemetria a 20 Hz los
     * tapa. Se apaga sola y se vuelve a prender con 't'. */
    g_telemetry_on = false;
}

static void calib_stop(void)
{
    g_ramp_active = false;
    g_window_active = false;
    g_calib_duty[WHEEL_LEFT] = 0;
    g_calib_duty[WHEEL_RIGHT] = 0;
    wheels_coast();
}

static const char *wheel_name(int wheel)
{
    return (wheel == WHEEL_LEFT) ? "IZQ" : "DER";
}

/* C,<rueda>,<duty> - duty crudo fijo. */
static void calib_set(int wheel_sel, int duty)
{
    calib_enter();
    g_ramp_active = false;
    g_window_active = false;

    if (duty > PWM_MAX) {
        duty = PWM_MAX;
    }
    if (duty < -PWM_MAX) {
        duty = -PWM_MAX;
    }

    if (wheel_sel == 0 || wheel_sel == 2) {
        g_calib_duty[WHEEL_LEFT] = duty;
    }
    if (wheel_sel == 1 || wheel_sel == 2) {
        g_calib_duty[WHEEL_RIGHT] = duty;
    }

    Serial.printf("# C,duty crudo izq=%d der=%d\n", g_calib_duty[WHEEL_LEFT],
                  g_calib_duty[WHEEL_RIGHT]);
}

/*
 * K,<rueda>[,<duty0>] - rampa descendente para el v_min CINETICO.
 *
 * Los 32/64 del bring-up son el umbral ESTATICO, desde parado. El que
 * necesita la ley de control es el minimo para SEGUIR girando, que es
 * menor (HARDWARE.md 0.4 palanca B). Metodo: arrancar la rueda a un duty
 * que la mueve seguro y bajar de a poco hasta que se pare.
 *
 * La rueda arranca al duty inicial y baja RAMP_STEP cuentas cada
 * RAMP_STEP_MS. Cuando se detiene, ENTER (linea vacia) congela y reporta
 * el duty de ese instante.
 */
static void ramp_start(int wheel, int duty0)
{
    calib_enter();
    g_window_active = false;

    if (duty0 <= 0 || duty0 > PWM_MAX) {
        /* 300 arranca las dos ruedas desde parado: la izquierda no lo
         * hace a 211 y la derecha si (medido 2026-08-27), y el umbral
         * estatico de la izquierda es 256. Se usa el mismo valor para
         * las dos para que la rampa sea comparable. */
        duty0 = 300;
    }

    g_ramp_wheel = wheel;
    g_ramp_duty = duty0;
    g_ramp_last_ms = millis();
    g_ramp_active = true;

    g_calib_duty[WHEEL_LEFT] = 0;
    g_calib_duty[WHEEL_RIGHT] = 0;
    g_calib_duty[wheel] = duty0;

    Serial.printf("# K,rampa %s desde %d, -%d cada %d ms\n",
                  wheel_name(wheel), duty0, RAMP_STEP, RAMP_STEP_MS);
    Serial.println("# ENTER en cuanto la rueda se DETENGA (o 'x' para abortar)");
}

static void ramp_update(void)
{
    if (!g_ramp_active) {
        return;
    }
    if ((millis() - g_ramp_last_ms) < RAMP_STEP_MS) {
        return;
    }

    g_ramp_last_ms = millis();
    g_ramp_duty -= RAMP_STEP;

    if (g_ramp_duty <= 0) {
        g_ramp_duty = 0;
        g_ramp_active = false;
        g_calib_duty[g_ramp_wheel] = 0;
        wheels_coast();
        Serial.println("# K,llego a 0 sin marcar - la rueda nunca se paro?");
        return;
    }

    g_calib_duty[g_ramp_wheel] = g_ramp_duty;

    /* Rastro cada ~0,5 s: si se pasa el momento exacto, el ultimo valor
     * impreso acota igual el resultado. */
    if ((g_ramp_duty % 10) == 0) {
        Serial.printf("#   %d\n", g_ramp_duty);
    }
}

/* ENTER durante la rampa: congela y reporta. */
static void ramp_mark(void)
{
    int reaction;

    g_ramp_active = false;
    g_calib_duty[g_ramp_wheel] = 0;
    wheels_coast();

    /* A RAMP_STEP cuentas cada RAMP_STEP_MS, ~300 ms de reaccion humana
     * son unas pocas cuentas de mas: la rueda se paro un poco ARRIBA del
     * valor marcado. Se reporta el rango, no un numero solo. */
    reaction = (RAMP_STEP * 300) / RAMP_STEP_MS;

    Serial.printf("# K,%s v_min cinetico = %d  (rango %d..%d por reaccion)\n",
                  wheel_name(g_ramp_wheel), g_ramp_duty, g_ramp_duty,
                  g_ramp_duty + reaction);
    Serial.printf("#   en 8 bits: %d   |  estatico medido: %d\n",
                  g_ramp_duty / 4,
                  (g_ramp_wheel == WHEEL_LEFT) ? PWM_BREAKAWAY_LEFT
                                               : PWM_BREAKAWAY_RIGHT);
    Serial.println("#   -> anotar y repetir 2-3 veces; usar el promedio");
}

/*
 * V,<rueda>,<duty>,<ms> - ventana cronometrada para medir velocidad.
 *
 * Corre la rueda a duty crudo durante ms exactos y frena sola. Con una
 * marca de cinta en la rueda se cuentan las vueltas: rpm = vueltas *
 * 60000 / ms. Sirve para el v_max por rueda (HARDWARE.md 0.5): se busca
 * el duty al que la rueda rapida da las mismas vueltas que la lenta a
 * su propio tope.
 */
static void window_start(int wheel_sel, int duty, uint32_t ms)
{
    calib_enter();
    g_ramp_active = false;

    if (duty > PWM_MAX) {
        duty = PWM_MAX;
    }
    if (duty < -PWM_MAX) {
        duty = -PWM_MAX;
    }
    if (ms == 0 || ms > 60000) {
        ms = 10000;
    }

    g_calib_duty[WHEEL_LEFT] = 0;
    g_calib_duty[WHEEL_RIGHT] = 0;
    if (wheel_sel == 0 || wheel_sel == 2) {
        g_calib_duty[WHEEL_LEFT] = duty;
    }
    if (wheel_sel == 1 || wheel_sel == 2) {
        g_calib_duty[WHEEL_RIGHT] = duty;
    }

    g_window_end_ms = millis() + ms;
    g_window_active = true;

    Serial.printf("# V,INICIO duty=%d durante %lu ms - contar vueltas\n", duty,
                  (unsigned long)ms);
}

static void window_update(void)
{
    if (!g_window_active) {
        return;
    }
    if ((int32_t)(millis() - g_window_end_ms) < 0) {
        return;
    }

    g_window_active = false;
    g_calib_duty[WHEEL_LEFT] = 0;
    g_calib_duty[WHEEL_RIGHT] = 0;
    wheels_brake();
    Serial.println("# V,FIN - vueltas x 60000 / ms = rpm del eje de salida");
}

/* ==================================================================
 * 11. Parser del protocolo
 * ================================================================== */
static void process_line(void)
{
    int v_lin, v_ang, pattern, wheel, duty;
    unsigned int ms;

    if (g_line_len == 0) {
        /* ENTER solo: durante una rampa de calibracion es la marca. */
        if (g_ramp_active) {
            ramp_mark();
        }
        return;
    }

    if (g_line_len == 1) {
        manual_command(g_line[0]); /* tecla suelta = modo manual */
        return;
    }

    /* --- comandos de calibracion (banco) --- */
    if (g_line[0] == 'C') {
        if (sscanf(g_line, "C,%d,%d", &wheel, &duty) == 2 && wheel >= 0 &&
            wheel <= 2) {
            calib_set(wheel, duty);
        } else {
            Serial.println("# E,C,<rueda 0|1|2>,<duty -1023..1023>");
        }
        return;
    }

    if (g_line[0] == 'K') {
        duty = 0; /* opcional: si no viene, ramp_start elige */
        if (sscanf(g_line, "K,%d,%d", &wheel, &duty) >= 1 && wheel >= 0 &&
            wheel <= 1) {
            ramp_start(wheel, duty);
        } else {
            Serial.println("# E,K,<rueda 0|1>[,<duty inicial>]");
        }
        return;
    }

    if (g_line[0] == 'V') {
        if (sscanf(g_line, "V,%d,%d,%u", &wheel, &duty, &ms) == 3 &&
            wheel >= 0 && wheel <= 2) {
            window_start(wheel, duty, (uint32_t)ms);
        } else {
            Serial.println("# E,V,<rueda 0|1|2>,<duty>,<ms>");
        }
        return;
    }

    if (g_line[0] == 'M') {
        if (sscanf(g_line, "M,%d,%d", &v_lin, &v_ang) == 2) {
            if (v_lin > 100) {
                v_lin = 100;
            }
            if (v_lin < -100) {
                v_lin = -100;
            }
            if (v_ang > 100) {
                v_ang = 100;
            }
            if (v_ang < -100) {
                v_ang = -100;
            }

            mix(v_lin, v_ang, &g_cmd_left, &g_cmd_right);
            g_last_cmd_ms = millis();
            g_wd_tripped = false;

            if (g_manual) {
                g_manual = false;
                if (g_calib) {
                    calib_stop();
                    g_calib = false;
                }
                Serial.println("# modo protocolo - watchdog ACTIVO");
            }
        } else {
            Serial.println("# E,M mal formado");
        }
        return;
    }

    if (g_line[0] == 'B') {
        if (sscanf(g_line, "B,%d", &pattern) == 1 && pattern >= 0 &&
            pattern <= 2) {
            buzz_set(pattern);
        } else {
            Serial.println("# E,B mal formado");
        }
        return;
    }

    Serial.println("# E,comando desconocido");
}

/*
 * El monitor serie manda CRLF al apretar Enter. Tratar '\r' y '\n' como
 * terminadores independientes generaba DOS lineas por Enter: la del
 * comando y una vacia. Casi siempre era inofensivo, pero la linea vacia
 * es la marca de la rampa de calibracion, asi que 'K,0' arrancaba la
 * rampa y se auto-marcaba en el mismo Enter.
 *
 * Solucion: un '\n' que viene inmediatamente despues de un '\r' es parte
 * del mismo Enter y se descarta. Cualquier otro caracter rompe la pareja.
 * Asi funcionan los tres finales de linea (CR, LF y CRLF) y un Enter
 * solo sigue valiendo como marca.
 */
static void serial_poll(void)
{
    static bool expect_lf = false;
    char c;

    while (Serial.available() > 0) {
        c = (char)Serial.read();

        if (c == '\r') {
            g_line[g_line_len] = '\0';
            process_line();
            g_line_len = 0;
            expect_lf = true;
        } else if (c == '\n') {
            if (expect_lf) {
                expect_lf = false; /* segunda mitad del CRLF: ignorar */
            } else {
                g_line[g_line_len] = '\0';
                process_line();
                g_line_len = 0;
            }
        } else {
            expect_lf = false;
            if (g_line_len < (CMD_LINE_MAX - 1)) {
                g_line[g_line_len++] = c;
            } else {
                g_line_len = 0; /* linea larga = basura, descartar */
            }
        }
    }
}

/* ==================================================================
 * 12. Watchdog
 * ================================================================== */
static void watchdog_update(void)
{
    uint32_t now = millis();

    if (g_manual) {
        return;
    }

    if ((now - g_last_cmd_ms) <= CMD_TIMEOUT_MS) {
        return;
    }

    g_cmd_left = 0;
    g_cmd_right = 0;

    if (!g_wd_tripped) {
        g_wd_tripped = true;
        g_wd_trip_ms = now;
        wheels_brake();
        Serial.println("# W,watchdog - sin comando M por 500 ms, frenando");
    } else if ((now - g_wd_trip_ms) > WD_BRAKE_MS) {
        /* Soltar el freno: dejar el puente en corto indefinidamente
         * calienta el L298 sin ningun beneficio con el robot ya parado. */
        wheels_coast();
    }
}

/* ==================================================================
 * 13. Telemetria
 * ================================================================== */
static void telemetry_send(void)
{
    /* Encoders: extension opcional (PLAN.md D5). Mientras no esten
     * cableados se emiten en cero, no se omiten, para que el parser del
     * Pi sea siempre el mismo. */
    Serial.printf("D,%d,0,0\n", g_distance_cm);
}

/* ================================================================== */

void setup(void)
{
    Serial.begin(115200);

    /* Primero los pines de direccion en estado seguro: al salir del
     * reset los GPIO quedan flotando y el L298 no tiene niveles
     * definidos en sus entradas. */
    pinMode(PIN_IN1, OUTPUT);
    pinMode(PIN_IN2, OUTPUT);
    pinMode(PIN_IN3, OUTPUT);
    pinMode(PIN_IN4, OUTPUT);
    digitalWrite(PIN_IN1, LOW);
    digitalWrite(PIN_IN2, LOW);
    digitalWrite(PIN_IN3, LOW);
    digitalWrite(PIN_IN4, LOW);

    /* El pin de enable y el canal LEDC tienen que viajar juntos: en el
     * core 2.x ledcWrite() recibe el canal, no el pin (HARDWARE.md 6.3). */
    pwm_init(PIN_LEFT_PWM, PWM_CH_LEFT, g_pwm_freq);
    pwm_init(PIN_RIGHT_PWM, PWM_CH_RIGHT, g_pwm_freq);
    wheels_coast();

    pinMode(PIN_TRIG, OUTPUT);
    digitalWrite(PIN_TRIG, LOW);
    /* Pulldown interno: sin el sensor conectado el pin quedaria flotando y
     * la ISR dispararia con cualquier ruido. Con el divisor puesto el
     * pulldown (~45k) queda en paralelo con R2 (2k) y casi no lo corre:
     * la entrada pasa de 3,33 a 3,28 V. */
    pinMode(PIN_ECHO, INPUT_PULLDOWN);
    attachInterrupt(digitalPinToInterrupt(PIN_ECHO), echo_isr, CHANGE);

#if BUZZER_PASSIVE
    pwm_init(PIN_BUZZER, PWM_CH_BUZZER, 2000);
#else
    pinMode(PIN_BUZZER, OUTPUT);
#endif
    buzz_output(false, 0);

    delay(300); /* que el monitor serie alcance a conectarse */

    Serial.println();
    Serial.println("# ==========================================");
    Serial.println("# TPF Robotica IA - firmware de control");
    Serial.println("# ==========================================");
    Serial.println("# Protocolo: M,<v_lin>,<v_ang> / B,<patron>");
    Serial.println("# Telemetria: D,<dist_cm>,<enc_izq>,<enc_der> a 20 Hz");
    Serial.println("# Teclas sueltas = modo manual. '?' para la ayuda.");
    print_params();

    g_last_cmd_ms = millis();
    g_wd_tripped = true; /* arranca parado hasta el primer comando */
    g_wd_trip_ms = g_last_cmd_ms;
}

void loop(void)
{
    static uint32_t t_control = 0;
    static uint32_t t_telemetry = 0;
    static uint32_t t_ping = 0;
    uint32_t now = millis();

    serial_poll();
    ping_poll();
    buzz_update();
    ramp_update();
    window_update();

    if ((now - t_ping) >= PING_PERIOD_MS) {
        t_ping = now;
        ping_send();
    }

    if ((now - t_control) >= CONTROL_PERIOD_MS) {
        t_control = now;
        watchdog_update();

        if (g_calib) {
            /* Calibracion: duty crudo, sin zona muerta ni breakaway.
             * Aca se mide el motor, no la ley de control. */
            wheel_raw(WHEEL_LEFT, g_calib_duty[WHEEL_LEFT]);
            wheel_raw(WHEEL_RIGHT, g_calib_duty[WHEEL_RIGHT]);
            g_last_duty[WHEEL_LEFT] = g_calib_duty[WHEEL_LEFT];
            g_last_duty[WHEEL_RIGHT] = g_calib_duty[WHEEL_RIGHT];
        } else if (!g_wd_tripped || g_manual) {
            /* Mientras el watchdog esta frenando no se pisa el freno con
             * un duty de cero, que seria rueda libre. */
            wheel_apply(WHEEL_LEFT, g_cmd_left);
            wheel_apply(WHEEL_RIGHT, g_cmd_right);
        }
    }

    if ((now - t_telemetry) >= TELEMETRY_PERIOD_MS) {
        t_telemetry = now;
        if (g_telemetry_on) {
            telemetry_send();
        }
    }
}
