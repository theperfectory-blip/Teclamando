"""Mando como ratón, al estilo del navegador de la PS3.

Sin dependencias: usa XInput y user32 de Windows con ctypes. Mandos que no son de Xbox
(PlayStation, genéricos USB) se leen con mando_generico.py; configurar_mando.py aprende sus botones. El ayudante
vigilar_foco.ps1 (UI Automation) avisa cuándo hay un campo de texto activo; entonces se abre
el teclado propio (teclado_ps3.py, al estilo de la PS3, con tildes, ñ y texto predictivo).
Ejecutar con pythonw (sin ventana) mediante iniciar_mando_raton.vbs.

MODO RATÓN (normal)                                    [PS3]
  Stick izquierdo   cursor (más inclinado = más rápido)
  LT (mantener)     modo precisión: cursor a un tercio de velocidad
  A                 clic izquierdo · dos veces = doble clic    [X]
                    mantener + mover stick = arrastrar / seleccionar texto
                    mantener quieta 0,6 s = abrir enlace en pestaña nueva
  RT                clic derecho
  X                 clic derecho (al soltar)                   [cuadrado]
  X + cruceta       página arriba / abajo, inicio / final      [cuadrado + cruceta]
  B                 atrás                                      [círculo]
  B (mantener 1 s)  cerrar la pestaña                          [círculo mantenido]
  Y                 menú del navegador                         [triángulo]
  LB / RB           página anterior / siguiente; con la guía abierta, su página    [L1 / R1]
  Stick derecho     scroll
  R3 + stick der.   zoom (arriba acerca, abajo aleja); R3 solo = zoom normal
  Cruceta           flechas (en YouTube: adelantar/retroceder, volumen)
  Start (solo)      Enter: ejecutar / enviar / avanzar          [START]
  Back (solo)       favoritos                                  [SELECT]
  L3                abrir el teclado en pantalla
  Al hacer clic (A) en un campo de texto se abre el teclado solo.

  Combinaciones a dos manos (el modificador siempre en la mano contraria):
  Mano izquierda + Start (pulgar derecho):
    Start + Arriba/Abajo       velocidad del cursor + / -  (niveles 1 a 10)
    Start + Derecha/Izquierda  velocidad del scroll + / -
    Start + LB                 pestaña anterior
    Start + LT                 bajar volumen
    Start + L3                 ver todas las ventanas
  Mano derecha + Back (pulgar izquierdo):
    Back + RB                  pestaña siguiente
    Back + RT                  subir volumen
    Back + A                   reproducir / pausar
    Back + Y                   pantalla completa en YouTube (tecla F)
    Back + B                   Esc
    Back + R3                  abrir / cerrar la guía de botones (guia_mando.py)
  Back + Start               encender / pausar el control (para jugar)
  Vibra al cambiar; en los límites (nivel 1 o 10) vibra largo.

MODO TECLADO (mientras el teclado propio está abierto, teclado_ps3.py)
  Cruceta o stick izq.  moverse por las teclas (arriba del todo: palabras sugeridas)
  A                     pulsar la tecla; mantener en una vocal = vocal con tilde   [X]
  X                     borrar                                 [cuadrado]
  Y                     espacio                                [triángulo]
  Stick derecho         mover el teclado por la pantalla
  LB / RB               mover el cursor del texto ← / →                [L1 / R1]
  LT                    letras <-> números (teclado numérico) y símbolos   [L2]
  RT                    mayúsculas: 1 vez = una letra (⇧ 1), 2 = bloqueadas (BLOQ), 3 = normal
                        (igual que la tecla ⇧ del teclado)             [R2]
  Start                 Enter y cerrar el teclado              [START]
  B o L3                cerrar el teclado                      [círculo]
  El teclado se pega justo debajo del campo donde escribes (encima si abajo no cabe); en el
  menú Inicio, al lado del menú. Arriba de todo muestra la frase que vas escribiendo.
  Suena al moverse (tic) y al pulsar (clic), como el de la PS3.

Extra opcional: si modo_juego.py está en la carpeta, añade un modo juego (ver ese archivo).
"""
import collections
import ctypes
import json
import os
import subprocess
import sys
import threading
import time
from ctypes import wintypes

import rutas

try:
    import modo_juego          # extra opcional (no viene en la versión pública)
except ImportError:
    modo_juego = None

# ---------- Ajustes ----------
NIVELES_CURSOR = [3, 4, 6, 8, 10, 13, 16, 20, 25, 32]   # píxeles por ciclo al tope
NIVELES_SCROLL = [8, 12, 18, 25, 35, 45, 60, 80, 100, 130]
CURVA = 2.2               # >1 = más precisión con poca inclinación
FACTOR_PRECISION = 1 / 3  # con LT mantenido
ZONA_MUERTA_IZQ = 7849
ZONA_MUERTA_DER = 8689
UMBRAL_GATILLO = 60
HZ = 125
REPETIR_ESPERA = 0.40     # s antes de que un botón mantenido se repita
REPETIR_CADA = 0.08
TECLADO_ESPERA = 0.23     # repetición al moverse por el teclado (50 % más rápida, pedido 2026-10-27)
TECLADO_CADA = 0.087
TECLADO_ARRASTRE = 1600   # px/s con el stick derecho a fondo (mover el teclado)
CONFIGURAR_MANTENER = 10.0   # s con Back + R3 apretados = configurar el mando (mini ventana)
A_MANTENER = 0.6          # s con A quieta = abrir en pestaña nueva
B_MANTENER = 1.0          # s con B = cerrar pestaña
ESPERA_FOCO = 0.45        # s tras el clic: si el campo ya tenía el foco, abrir el teclado
DOBLE_CLIC = 0.8          # s: dos A seguidas en el mismo sitio = doble clic (más holgado que el de Windows)
VENTANA_FOCO = 1.5       # s tras el clic vigilando si un campo recibe el foco (buscadores con animación)
REGISTRO_FOCO = rutas.datos("foco_registro.txt")
ARCHIVO_AJUSTES = rutas.datos("ajustes.json")
AYUDANTE = rutas.programa("vigilar_foco.ps1")
RENOVAR_AYUDANTE = 20 * 60   # s: cada cuánto se relanza el ayudante de foco (si no hay nada pendiente)

# ---------- Windows ----------
class XINPUT_GAMEPAD(ctypes.Structure):
    _fields_ = [("wButtons", wintypes.WORD), ("bLeftTrigger", ctypes.c_ubyte),
                ("bRightTrigger", ctypes.c_ubyte), ("sThumbLX", ctypes.c_short),
                ("sThumbLY", ctypes.c_short), ("sThumbRX", ctypes.c_short),
                ("sThumbRY", ctypes.c_short)]

class XINPUT_STATE(ctypes.Structure):
    _fields_ = [("dwPacketNumber", wintypes.DWORD), ("Gamepad", XINPUT_GAMEPAD)]

class XINPUT_VIBRATION(ctypes.Structure):
    _fields_ = [("wLeftMotorSpeed", wintypes.WORD), ("wRightMotorSpeed", wintypes.WORD)]

xinput = None
for _dll in ("xinput1_4", "xinput1_3", "xinput9_1_0"):
    try:
        xinput = ctypes.WinDLL(_dll)
        break
    except OSError:
        continue
PUERTO = 0      # puerto XInput del mando en uso (0-3); None = mando genérico (sin vibración)

user32 = ctypes.WinDLL("user32")
kernel32 = ctypes.WinDLL("kernel32")
# Coordenadas reales de pantalla (UI Automation las da así; pantalla al 125 %)
try:
    user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
except (AttributeError, OSError):
    pass

DPAD_UP, DPAD_DOWN, DPAD_LEFT, DPAD_RIGHT = 0x0001, 0x0002, 0x0004, 0x0008
START, BACK, L3, R3 = 0x0010, 0x0020, 0x0040, 0x0080
LB, RB, BTN_A, BTN_B, BTN_X, BTN_Y = 0x0100, 0x0200, 0x1000, 0x2000, 0x4000, 0x8000
RT, LT = 0x10000, 0x20000  # bits propios para tratar los gatillos como botones
CRUCETA = DPAD_UP | DPAD_DOWN | DPAD_LEFT | DPAD_RIGHT

MOVE, LDOWN, LUP, RDOWN, RUP, MDOWN, MUP = 0x1, 0x2, 0x4, 0x8, 0x10, 0x20, 0x40
WHEEL, HWHEEL = 0x0800, 0x1000
KEYUP, EXTENDED = 0x2, 0x1

VK_BACK, VK_TAB, VK_RETURN, VK_SHIFT, VK_CONTROL, VK_MENU = 0x08, 0x09, 0x0D, 0x10, 0x11, 0x12
VK_ESCAPE, VK_SPACE, VK_PRIOR, VK_NEXT, VK_END, VK_HOME = 0x1B, 0x20, 0x21, 0x22, 0x23, 0x24
VK_LEFT, VK_UP, VK_RIGHT, VK_DOWN = 0x25, 0x26, 0x27, 0x28
VK_0, VK_F, VK_L, VK_O, VK_W, VK_LWIN = 0x30, 0x46, 0x4C, 0x4F, 0x57, 0x5B
VK_A, VK_D, VK_E, VK_Q, VK_R, VK_S, VK_Y = 0x41, 0x44, 0x45, 0x51, 0x52, 0x53, 0x59
VK_BROWSER_BACK, VK_BROWSER_FORWARD = 0xA6, 0xA7
VK_VOL_DOWN, VK_VOL_UP, VK_PLAY_PAUSE = 0xAE, 0xAF, 0xB3
EXTENDIDAS = {VK_LEFT, VK_UP, VK_RIGHT, VK_DOWN, VK_PRIOR, VK_NEXT, VK_END, VK_HOME, VK_LWIN}


def raton(flags, dx=0, dy=0, datos=0):
    user32.mouse_event(flags, dx, dy, ctypes.c_ulong(datos & 0xFFFFFFFF), 0)


def mover_a(x, y):
    user32.SetCursorPos(int(x), int(y))
    raton(MOVE)  # para que la ventana de debajo se entere (resalta la tecla)


def posicion_cursor():
    p = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(p))
    return p.x, p.y


def tecla(vk, arriba=False):
    f = (KEYUP if arriba else 0) | (EXTENDED if vk in EXTENDIDAS else 0)
    user32.keybd_event(vk, 0, f, 0)


def combo(*vks):
    for vk in vks:
        tecla(vk)
    for vk in reversed(vks):
        tecla(vk, True)


def vibrar(ms=120, fuerza=30000):
    if xinput is None or PUERTO is None:
        if vibracion_ps.vibrar(fuerza):         # mando de PlayStation: vibra por HID
            time.sleep(ms / 1000)
            vibracion_ps.vibrar(0)
        return
    v = XINPUT_VIBRATION(fuerza, fuerza)
    xinput.XInputSetState(PUERTO, ctypes.byref(v))
    time.sleep(ms / 1000)
    v = XINPUT_VIBRATION(0, 0)
    xinput.XInputSetState(PUERTO, ctypes.byref(v))


def stick(x, y, zona, curva=CURVA):
    """Devuelve (nx, ny) en [-1, 1] con zona muerta radial y curva."""
    mag = (x * x + y * y) ** 0.5
    if mag <= zona:
        return 0.0, 0.0
    m = min((mag - zona) / (32767 - zona), 1.0) ** curva
    return x / mag * m, y / mag * m


from teclado_ps3 import Teclado  # noqa: E402  (teclado propio)
from mando_generico import MandoGenerico  # noqa: E402  (mandos que no son de Xbox)
from vibracion_ps import VibracionPS  # noqa: E402  (vibración de DualShock 4 / DualSense)

vibracion_ps = VibracionPS()


class Ayudante:
    """Lanza vigilar_foco.ps1 y guarda si el foco está en un campo de texto."""

    def __init__(self, arrancar=True):
        self.foco_texto = False
        self.campo = None         # (x, y, ancho, alto) del campo de texto con foco
        self.otro = ""            # descripción de lo enfocado cuando no es un campo de texto
        self.cambio_t = 0.0       # instante del último cambio de foco
        self.historia = collections.deque(maxlen=12)   # (instante, línea) de los últimos cambios
        self.proceso = None
        self.inicio_t = 0.0       # cuándo se lanzó el ayudante actual
        if arrancar:
            self.arrancar()

    def arrancar(self):
        self.inicio_t = time.monotonic()
        try:
            self.proceso = subprocess.Popen(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", AYUDANTE,
                 "-Padre", str(os.getpid())],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, stdin=subprocess.PIPE,
                creationflags=0x08000000, text=True, encoding="utf-8", errors="replace")
        except OSError:
            self.proceso = None
            return
        threading.Thread(target=self.leer, daemon=True).start()

    def vivo(self):
        return self.proceso is not None and self.proceso.poll() is None

    def renovar(self):
        """Cerrar el ayudante y lanzar uno nuevo. UI Automation se queda pegada en un proceso que
        lleva horas (sobre todo tras suspender el PC): seguía diciendo "la página" con el foco en un
        buscador, y el teclado dejó de abrirse solo (2026-11-04)."""
        if self.vivo():
            try:
                self.proceso.terminate()
            except OSError:
                pass
        self.foco_texto = False
        self.campo = None
        self.arrancar()

    def punto(self, x, y):
        """Avisa de un clic: si el foco no quedó en un campo de texto pero debajo del clic hay uno
        (programas como Claude o Discord, que dejan el foco en el contenedor), el ayudante lo dice."""
        if self.vivo():
            try:
                self.proceso.stdin.write("PUNTO %d %d\n" % (x, y))
                self.proceso.stdin.flush()
            except (OSError, ValueError):
                pass

    def leer(self):
        for linea in self.proceso.stdout:
            linea = linea.strip()
            if linea.startswith("FOCO EDIT"):
                try:
                    x, y, w, h = (int(v) for v in linea.split()[2:6])
                    self.campo = (x, y, w, h)
                except ValueError:
                    self.campo = None
                self.foco_texto = True
            elif linea.startswith("FOCO OTRO"):
                self.foco_texto = False
                self.campo = None
                self.otro = linea[10:]
            else:
                continue
            self.cambio_t = time.monotonic()
            self.historia.append((self.cambio_t, linea))


def registrar_foco(descripcion):
    """Anota qué había con foco tras un clic que no abrió el teclado (últimas 40 líneas), para
    saber por qué no se reconoció un campo de una página."""
    try:
        with open(REGISTRO_FOCO, encoding="utf-8") as f:
            lineas = f.read().splitlines()[-39:]
    except OSError:
        lineas = []
    lineas.append(time.strftime("%Y-%m-%d %H:%M:%S ") + descripcion)
    try:
        with open(REGISTRO_FOCO, "w", encoding="utf-8") as f:
            f.write("\n".join(lineas) + "\n")
    except OSError:
        pass


# ---------- Ajustes guardados ----------
def cargar_ajustes():
    ajustes = {"cursor": 3, "scroll": 4}  # índices (0-9)
    try:
        with open(ARCHIVO_AJUSTES, encoding="utf-8") as f:
            ajustes.update(json.load(f))
    except (OSError, ValueError):
        pass
    for k in ajustes:
        ajustes[k] = max(0, min(9, int(ajustes[k])))
    return ajustes


def guardar_ajustes(ajustes):
    try:
        with open(ARCHIVO_AJUSTES, "w", encoding="utf-8") as f:
            json.dump(ajustes, f)
    except OSError:
        pass


def cambiar_nivel(ajustes, clave, paso):
    nuevo = max(0, min(9, ajustes[clave] + paso))
    if nuevo == ajustes[clave]:
        vibrar(350)  # ya estaba en el límite
        return
    ajustes[clave] = nuevo
    guardar_ajustes(ajustes)
    vibrar(60, 20000 + nuevo * 4000)  # más fuerte cuanto más rápido


# ---------- Programa ----------
class SinJuego:
    """Sin modo_juego.py: nunca hay modo juego."""
    en_juego = False

    def iniciar_juego(self):
        pass

    def juego_al_frente(self):
        return False

    def soltar_juego(self):
        pass


if modo_juego:
    modo_juego.m = sys.modules[__name__]


class Mando(modo_juego.ModoJuego if modo_juego else SinJuego):
    def __init__(self, en_espera=False):
        self.ajustes = cargar_ajustes()
        self.ayudante = Ayudante(arrancar=not en_espera)
        self.guia = None          # proceso de la guía de botones (guia_mando.py)
        self.indicador = None     # icono del mando + recordatorio Back + R3 (indicador_mando.py)
        self.previo = 0
        self.consumidos = 0       # botones ya usados en una combinación: se ignoran hasta soltarlos
        self.activo = not en_espera   # en espera: solo escucha Back + Start
        self.acum = [0.0, 0.0, 0.0, 0.0]
        self.acum_tec = [0.0, 0.0]   # restos de píxeles al mover el teclado con el stick derecho
        self.rep = {}
        self.back_solo = False
        self.start_solo = False
        # modo ratón
        self.a_t = None           # A apretada: instante (clic pendiente)
        self.a_arrastre = False
        self.x_pendiente = False  # X apretada sin cruceta (clic derecho al soltar)
        self.b_t = None
        self.r3_zoom = False
        self.foco_clic = None     # instante del último clic: vigilar si un campo recibe el foco
        self.clic_pos = (0, 0)
        self.clic_t = 0.0         # instante del último clic con A (para el doble clic)
        self.teclado_cerrado_t = 0.0
        self.zoom_acum = 0.0
        # modo teclado (teclado propio, en su hilo)
        self.en_teclado = False
        self.teclado = Teclado(vibrar=lambda: vibrar(40, 20000))
        self.iniciar_juego()          # modo juego (solo con modo_juego.py)
        self.generico = MandoGenerico()
        self.configurando = False   # la mini ventana está enseñándole los botones a un mando nuevo
        self.config_desde = 0.0
        self.apagando = None        # instante en que se le pidió a la mini ventana la animación de apagado
        self.mando_id = None        # qué mando hay conectado (para avisar cuando llega uno nuevo)
        self.ofrecidos = set()      # modelos a los que ya se ofreció configurarlos en esta sesión
        self.retener_t = None       # Back + R3 apretados desde este instante

    # ----- utilidades -----
    def clic_en_campo(self, campo, margen=8):
        if not campo:
            return False
        x, y = self.clic_pos
        cx, cy, w, h = campo
        return cx - margen <= x <= cx + w + margen and cy - margen <= y <= cy + h + margen

    def repetir(self, clave, apretado, ahora, espera=REPETIR_ESPERA, cada=REPETIR_CADA):
        if not apretado:
            self.rep.pop(clave, None)
            return False
        t = self.rep.get(clave)
        if t is None:
            self.rep[clave] = ahora + espera
            return True
        if ahora >= t:
            self.rep[clave] = ahora + cada
            return True
        return False

    def soltar_todo(self):
        if self.a_arrastre:
            raton(LUP)
        if self.previo & RT:
            raton(RUP)
        self.a_t = None
        self.a_arrastre = self.x_pendiente = False
        self.b_t = None
        self.r3_zoom = False
        self.foco_clic = None
        self.rep.clear()

    def mover_cursor(self, g, factor=1.0):
        velocidad = NIVELES_CURSOR[self.ajustes["cursor"]] * factor
        nx, ny = stick(g.sThumbLX, g.sThumbLY, ZONA_MUERTA_IZQ)
        self.acum[0] += nx * velocidad
        self.acum[1] -= ny * velocidad
        dx, dy = int(self.acum[0]), int(self.acum[1])
        if dx or dy:
            self.acum[0] -= dx
            self.acum[1] -= dy
        return dx, dy

    def scroll(self, g):
        vs = NIVELES_SCROLL[self.ajustes["scroll"]]
        sx, sy = stick(g.sThumbRX, g.sThumbRY, ZONA_MUERTA_DER)
        self.acum[3] += sy * vs
        self.acum[2] += sx * vs
        wy, wx = int(self.acum[3]), int(self.acum[2])
        if wy:
            raton(WHEEL, datos=wy)
            self.acum[3] -= wy
        if wx:
            raton(HWHEEL, datos=wx)
            self.acum[2] -= wx

    # ----- modo teclado -----
    def entrar_teclado(self):
        self.soltar_todo()
        self.en_teclado = True

    def salir_teclado(self):
        self.en_teclado = False
        self.rep.clear()
        self.back_solo = self.start_solo = False
        self.foco_clic = None                  # tras cerrar/enviar no se reabre solo
        self.teclado_cerrado_t = time.monotonic()

    def paso_teclado(self, g, botones, nuevos, soltados, ahora):
        t = self.teclado
        # Dirección: cruceta o stick izquierdo
        nx, ny = stick(g.sThumbLX, g.sThumbLY, 16000, curva=1.0)
        direccion = None
        if botones & DPAD_UP or (abs(ny) > abs(nx) and ny > 0):
            direccion = "arr"
        elif botones & DPAD_DOWN or (abs(ny) > abs(nx) and ny < 0):
            direccion = "aba"
        elif botones & DPAD_LEFT or nx < 0:
            direccion = "izq"
        elif botones & DPAD_RIGHT or nx > 0:
            direccion = "der"
        for d in ("arr", "aba", "izq", "der"):
            if self.repetir("nav" + d, direccion == d, ahora, TECLADO_ESPERA, TECLADO_CADA):
                t.comando("mover", d)
        if nuevos & BTN_A:
            t.comando("a_abajo")
        if soltados & BTN_A:
            t.comando("a_arriba")
        if self.repetir("borrar", bool(botones & BTN_X), ahora):
            t.comando("borrar")
        if nuevos & BTN_Y:
            t.comando("espacio")
        # Cursor del texto: LB ← · RB →
        if self.repetir("t_izq", bool(botones & LB), ahora):
            t.comando("cursor", "izq")
        if self.repetir("t_der", bool(botones & RB), ahora):
            t.comando("cursor", "der")
        # Stick derecho: mover el teclado por la pantalla en tiempo real (más inclinado = más rápido).
        # Las palabras sugeridas se eligen subiendo con la cruceta / stick izquierdo.
        rx, ry = stick(g.sThumbRX, g.sThumbRY, 8000, curva=1.6)
        self.acum_tec[0] += rx * TECLADO_ARRASTRE / HZ
        self.acum_tec[1] -= ry * TECLADO_ARRASTRE / HZ
        dx, dy = int(self.acum_tec[0]), int(self.acum_tec[1])
        if dx or dy:
            self.acum_tec[0] -= dx
            self.acum_tec[1] -= dy
            t.comando("arrastrar", dx, dy)
        if nuevos & LT:
            t.comando("capa")
        if nuevos & RT:
            t.comando("mayus")             # 1 = una mayúscula, 2 = bloqueadas, 3 = normal
        if nuevos & START:
            t.comando("enviar")
        if nuevos & (BTN_B | L3):
            t.comando("cerrar")

    # ----- modo ratón -----
    def paso_raton(self, g, botones, nuevos, soltados, ahora):
        con_back = bool(botones & BACK)

        # ---- Combinaciones ----
        # Regla de comodidad: el modificador va en la mano contraria a la acción.
        #   Back  (pulgar izquierdo) + botones de la mano derecha (A, B, Y, RB, RT, R3)
        #   Start (pulgar derecho)   + botones de la mano izquierda (cruceta, LB, LT, L3)
        con_start = bool(botones & START)
        if nuevos & BACK & ~self.consumidos:
            self.back_solo = True
        if nuevos & START & ~self.consumidos:
            self.start_solo = True
        if con_back:
            combinados = nuevos & ~BACK
            if combinados:
                self.back_solo = False
                self.consumidos |= combinados
            if nuevos & RB:
                combo(VK_CONTROL, VK_TAB)             # pestaña siguiente
            if nuevos & BTN_A:
                combo(VK_PLAY_PAUSE)
            if nuevos & BTN_Y:
                combo(VK_F)                           # pantalla completa
            if nuevos & BTN_B:
                combo(VK_ESCAPE)
        if con_start:
            combinados = nuevos & ~START
            if combinados:
                self.start_solo = False
                self.consumidos |= combinados
            if nuevos & DPAD_UP:
                cambiar_nivel(self.ajustes, "cursor", +1)
            if nuevos & DPAD_DOWN:
                cambiar_nivel(self.ajustes, "cursor", -1)
            if nuevos & DPAD_RIGHT:
                cambiar_nivel(self.ajustes, "scroll", +1)
            if nuevos & DPAD_LEFT:
                cambiar_nivel(self.ajustes, "scroll", -1)
            if nuevos & LB:
                combo(VK_CONTROL, VK_SHIFT, VK_TAB)   # pestaña anterior
            if nuevos & L3:
                combo(VK_LWIN, VK_TAB)                # ver todas las ventanas
        # Volumen con repetición: Start + LT (baja), Back + RT (sube)
        if self.repetir("vol-", con_start and bool(botones & LT), ahora):
            combo(VK_VOL_DOWN)
        if self.repetir("vol+", con_back and bool(botones & RT), ahora):
            combo(VK_VOL_UP)
        # Solos (sin combinación) actúan al soltar
        if soltados & BACK:
            if self.back_solo:
                combo(VK_CONTROL, VK_SHIFT, VK_O)  # favoritos
            self.back_solo = False
        if soltados & START:
            if self.start_solo:
                combo(VK_RETURN)                   # Enter: avanzar / ejecutar (el teclado solo se abre con L3)
            self.start_solo = False                # si no, al soltar el Start que envió desde el teclado, otro Enter
        if con_back:
            self.back_solo = self.back_solo and not (botones & ~BACK & ~self.consumidos)
        if con_start:
            self.start_solo = self.start_solo and not (botones & ~START & ~self.consumidos)

        libres = botones & ~self.consumidos
        n_libres = nuevos & ~self.consumidos
        s_libres = soltados & ~self.consumidos

        # ---- Cursor ----
        dx, dy = self.mover_cursor(g, FACTOR_PRECISION if libres & LT else 1.0)
        # A mantenida y el stick se mueve: empieza el arrastre donde se apretó
        if self.a_t is not None and (dx or dy):
            raton(LDOWN)
            self.a_arrastre = True
            self.a_t = None
        if dx or dy:
            raton(MOVE, dx, dy)

        # ---- A: clic / arrastre / pestaña nueva ----
        if n_libres & BTN_A:
            self.a_t = ahora
        if self.a_t is not None and ahora - self.a_t >= A_MANTENER:
            raton(MDOWN)
            raton(MUP)
            vibrar(50)
            self.a_t = None
            self.consumidos |= BTN_A
        if s_libres & BTN_A:
            if self.a_arrastre:
                raton(LUP)
            elif self.a_t is not None:
                raton(LDOWN)
                raton(LUP)
                pos = posicion_cursor()
                entre = ahora - self.clic_t
                if entre <= DOBLE_CLIC and abs(pos[0] - self.clic_pos[0]) <= 6 and abs(pos[1] - self.clic_pos[1]) <= 6:
                    # A dos veces = doble clic (abrir archivo/carpeta). Si fue más lento que el doble
                    # clic de Windows, otro clic ya mismo para que no lo tome como "cambiar nombre".
                    # Y no abrir el teclado (el cuadro de renombrar sale justo bajo el clic).
                    if entre * 1000 > user32.GetDoubleClickTime():
                        raton(LDOWN)
                        raton(LUP)
                    self.foco_clic = None
                    self.clic_t = 0.0
                else:
                    self.foco_clic = self.clic_t = ahora
                    self.clic_pos = pos
                    self.ayudante.punto(*pos)
            self.a_t = None
            self.a_arrastre = False

        # Tras un clic: si en el próximo segundo y medio un campo de texto recibe el foco, abrir el
        # teclado (como en la PS3). Muchos buscadores aparecen con una animación y reciben el foco tarde.
        if self.foco_clic is not None:
            dt = ahora - self.foco_clic
            cambio_nuevo = self.ayudante.cambio_t > self.foco_clic
            if self.ayudante.foco_texto and (cambio_nuevo or dt >= ESPERA_FOCO):
                self.foco_clic = None
                # Solo si el clic cayó DENTRO del campo: no al abrir el menú Inicio (pone el foco en su
                # buscador), ni al pulsar el micrófono al lado del cuadro de Claude (pedido 2026-10-27).
                # Para un campo que aparece lejos del clic (lupa de un buscador): L3.
                if ahora - self.teclado_cerrado_t > 2.0 and self.clic_en_campo(self.ayudante.campo):
                    self.teclado.abrir(self.ayudante.campo)
            elif dt >= VENTANA_FOCO:
                clic, self.foco_clic = self.foco_clic, None
                pasos = ["+%.2fs %s" % (t - clic, l[5:]) for t, l in list(self.ayudante.historia) if t > clic]
                if pasos:
                    registrar_foco(" | ".join(pasos))
                elif self.ayudante.otro:
                    registrar_foco("(sin cambios) " + self.ayudante.otro)

        # ---- RT: clic derecho sostenido ----
        if n_libres & RT:
            raton(RDOWN)
        elif soltados & RT and not (self.consumidos & RT):
            raton(RUP)

        # ---- X: clic derecho al soltar, o X + cruceta = saltos de página ----
        if n_libres & BTN_X:
            self.x_pendiente = True
        if libres & BTN_X:
            for b, vk in ((DPAD_UP, VK_PRIOR), (DPAD_DOWN, VK_NEXT),
                          (DPAD_LEFT, VK_HOME), (DPAD_RIGHT, VK_END)):
                if self.repetir("x%d" % b, bool(libres & b), ahora):
                    combo(vk)
                    self.x_pendiente = False
            if n_libres & CRUCETA:
                self.consumidos |= nuevos & CRUCETA
        if s_libres & BTN_X:
            if self.x_pendiente:
                raton(RDOWN)
                raton(RUP)
            self.x_pendiente = False

        # ---- B: atrás, o mantener = cerrar pestaña ----
        if n_libres & BTN_B:
            self.b_t = ahora
        if self.b_t is not None and ahora - self.b_t >= B_MANTENER:
            combo(VK_CONTROL, VK_W)
            vibrar(150)
            self.b_t = None
            self.consumidos |= BTN_B
        if s_libres & BTN_B and self.b_t is not None:
            combo(VK_BROWSER_BACK)
            self.b_t = None

        # ---- R3: zoom con el stick derecho ----
        if n_libres & R3:
            self.r3_zoom = False
            self.zoom_acum = 0.0
        if libres & R3:
            _, sy = stick(g.sThumbRX, g.sThumbRY, ZONA_MUERTA_DER)
            self.zoom_acum += sy * 0.08
            if abs(self.zoom_acum) >= 1:
                paso = 120 if self.zoom_acum > 0 else -120
                tecla(VK_CONTROL)
                raton(WHEEL, datos=paso)
                tecla(VK_CONTROL, True)
                self.zoom_acum -= 1 if self.zoom_acum > 0 else -1
                self.r3_zoom = True
        else:
            self.scroll(g)
        if s_libres & R3 and not self.r3_zoom:
            combo(VK_CONTROL, VK_0)

        # ---- Resto de botones ----
        if n_libres & BTN_Y:
            combo(VK_MENU, VK_F)  # menú del navegador
        if n_libres & LB:
            if self.guia_abierta():
                self.pagina_guia(-1)       # con la guía abierta, LB / RB cambian su página
            else:
                combo(VK_BROWSER_BACK)
        if n_libres & RB:
            if self.guia_abierta():
                self.pagina_guia(+1)
            else:
                combo(VK_BROWSER_FORWARD)
        if n_libres & L3:
            self.teclado.abrir(self.ayudante.campo if self.ayudante.foco_texto else None)
        if not libres & BTN_X:
            for b, vk in ((DPAD_UP, VK_UP), (DPAD_DOWN, VK_DOWN),
                          (DPAD_LEFT, VK_LEFT), (DPAD_RIGHT, VK_RIGHT)):
                if self.repetir("d%d" % b, bool(libres & b), ahora):
                    combo(vk)

    # ----- guía de botones -----
    def guia_abierta(self):
        return self.guia is not None and self.guia.poll() is None

    def pagina_guia(self, paso):
        """LB / RB con la guía abierta: cambiar de página (como las pestañas de la PS3)."""
        try:
            self.guia.stdin.write("PESTANA %d\n" % paso)
            self.guia.stdin.flush()
        except (OSError, ValueError, AttributeError):
            pass

    def cerrar_guia(self):
        if self.guia_abierta():
            self.guia.terminate()
        self.guia = None

    def alternar_guia(self):
        if self.guia_abierta():
            self.cerrar_guia()
            return
        try:
            self.guia = subprocess.Popen(
                rutas.orden("--guia", "guia_mando.py") + ["--padre", str(os.getpid())]
                + (["--juego"] if self.en_juego else []),
                stdin=subprocess.PIPE, text=True, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, creationflags=0x08000000)
        except OSError:
            self.guia = None

    def indicador_vivo(self):
        return self.indicador is not None and self.indicador.poll() is None

    def a_indicador(self, orden):
        """Una orden para la mini ventana (CONECTADO, CONFIGURAR n, APAGAR)."""
        if not self.indicador_vivo():
            return False
        try:
            self.indicador.stdin.write(orden + chr(10))
            self.indicador.stdin.flush()
            return True
        except (OSError, ValueError, AttributeError):
            return False

    def _leer_indicador(self, proceso):
        """Hilo: lo que dice la mini ventana (CONFIG 1 / CONFIG 0)."""
        try:
            for linea in proceso.stdout:
                if proceso is not self.indicador:
                    continue
                if linea.strip() == "CONFIG 0":
                    self.configurando = False
                elif linea.strip() == "CONFIG 1":
                    self.configurando = True
        except (OSError, ValueError):
            pass

    def mostrar_indicador(self, ver):
        vivo = self.indicador_vivo()
        if ver and vivo and self.apagando is not None:
            self.indicador.terminate()      # volvieron a encender a mitad de la animación de apagado
            vivo = False
        if ver and not vivo:
            self.apagando = None
            try:
                self.indicador = subprocess.Popen(
                    rutas.orden("--indicador", "indicador_mando.py") + ["--padre", str(os.getpid())],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
                    stderr=subprocess.DEVNULL, creationflags=0x08000000)
                threading.Thread(target=self._leer_indicador, args=(self.indicador,), daemon=True).start()
            except OSError:
                self.indicador = None
        elif not ver and vivo:
            # pausa: el anillo gira tres veces (como al apagar una Xbox 360) y la mini ventana se cierra sola
            self.configurando = False
            if self.apagando is None and self.a_indicador("APAGAR"):
                self.apagando = time.monotonic()
            elif self.apagando is None:
                self.indicador.terminate()
                self.indicador = None

    def revisar_indicador(self, ahora):
        """Cierra de verdad la mini ventana si la animación de apagado se alargó, y suelta el modo
        "configurando" si la mini ventana murió o se colgó."""
        if self.apagando is not None and (ahora - self.apagando > 4 or not self.indicador_vivo()):
            if self.indicador_vivo():
                self.indicador.terminate()
            self.indicador = None
            self.apagando = None
        if self.configurando and (not self.indicador_vivo() or ahora - self.config_desde > 300):
            self.configurando = False

    def mando_nuevo(self):
        """Cada vez que llega un mando: animación del anillo y, si es un genérico que no conocemos,
        ofrecer enseñarle los botones (se ofrece una vez por modelo y sesión)."""
        if PUERTO is not None:
            ident = ("x", PUERTO)
        else:
            ident = ("j", self.generico.modelo, self.generico.indice)
        if ident == self.mando_id:
            return
        self.mando_id = ident
        if not self.activo or self.apagando is not None:
            return
        if ident[0] == "j" and not self.generico.conocido and ident[1] not in self.ofrecidos:
            self.ofrecidos.add(ident[1])
            self.empezar_config(self.generico.indice, "auto")
        else:
            self.a_indicador("CONECTADO")

    def empezar_config(self, indice, modo):
        if indice is not None and self.a_indicador("CONFIGURAR %d %s" % (indice, modo)):
            self.configurando = True
            self.config_desde = time.monotonic()
            vibrar(60, 20000)

    # ----- bucle -----
    def leer_mando(self, estado):
        """Rellena `estado.Gamepad` con el mando conectado: primero uno XInput (Xbox, cualquier
        puerto), si no, cualquier otro mando (mando_generico.py). False si no hay ninguno."""
        global PUERTO
        if xinput is not None:
            puertos = [PUERTO] if PUERTO is not None else []
            puertos += [p for p in range(4) if p not in puertos]
            for p in puertos:
                if xinput.XInputGetState(p, ctypes.byref(estado)) == 0:
                    PUERTO = p
                    return True
        PUERTO = None
        if self.generico.indice is None:
            self.generico.buscar()
        return self.generico.leer(estado.Gamepad)

    def bucle(self):
        self.mostrar_indicador(self.activo)
        estado = XINPUT_STATE()
        periodo = 1.0 / HZ
        proxima_revision = 0.0
        ciclo_previo = time.monotonic()
        proximo_juego = 0.0
        juego_al_frente = False
        while True:
            ahora = time.monotonic()
            suspendido = ahora - ciclo_previo > 30    # el PC estuvo suspendido (el bucle no corrió)
            ciclo_previo = ahora
            if ahora >= proxima_revision:
                proxima_revision = ahora + 5
                if self.activo and not self.ayudante.vivo():
                    self.ayudante.arrancar()
                elif self.activo and (suspendido or ahora - self.ayudante.inicio_t > RENOVAR_AYUDANTE)                         and self.foco_clic is None and not self.teclado.visible:
                    self.ayudante.renovar()
                if self.activo:
                    self.mostrar_indicador(True)   # vuelve a abrirlo si se cerró
                self.generico.recargar_si_cambio()
            if ahora >= proximo_juego:
                proximo_juego = ahora + 0.5
                juego_al_frente = self.juego_al_frente()

            self.revisar_indicador(ahora)
            if not self.leer_mando(estado):
                self.mando_id = None
                self.soltar_todo()  # mando desconectado
                self.soltar_juego()
                self.previo = self.consumidos = 0
                time.sleep(1.0)
                continue

            g = estado.Gamepad
            botones = (g.wButtons | (RT if g.bRightTrigger > UMBRAL_GATILLO else 0)
                       | (LT if g.bLeftTrigger > UMBRAL_GATILLO else 0))
            self.mando_nuevo()
            if self.configurando:
                # la mini ventana le está enseñando los botones al mando: aquí no se hace nada
                self.previo = self.consumidos = botones
                self.retener_t = None
                time.sleep(periodo)
                continue
            nuevos = botones & ~self.previo
            soltados = self.previo & ~botones

            # Back + R3 mantenidos 10 s: configurar el mando (mandos que no son de Xbox)
            if self.activo and (botones & BACK) and (botones & R3):
                if self.retener_t is None:
                    self.retener_t = ahora
                elif (ahora - self.retener_t >= CONFIGURAR_MANTENER and PUERTO is None
                      and self.generico.indice is not None):
                    self.retener_t = ahora + 1e9      # una sola vez por pulsación
                    self.cerrar_guia()                 # la guía se abrió con el primer toque
                    self.empezar_config(self.generico.indice, "manual")
                    self.soltar_todo()
                    self.consumidos = botones
                    self.previo = botones
                    continue
            else:
                self.retener_t = None

            # Back + Start: pausar / reanudar (en cualquier modo)
            if (botones & BACK) and (botones & START) and (nuevos & (BACK | START)):
                self.activo = not self.activo
                self.back_solo = self.start_solo = False
                self.soltar_todo()
                self.soltar_juego()
                self.consumidos = botones
                if self.activo:
                    proxima_revision = 0.0   # arrancar el ayudante ya
                    self.mostrar_indicador(True)
                else:
                    self.cerrar_guia()
                    self.teclado.cerrar()
                    self.mostrar_indicador(False)
                vibrar(120 if self.activo else 300)
                self.previo = botones
                continue

            # Back + R3: abrir / cerrar la guía de botones (solo con el control activo)
            if self.activo and (botones & BACK) and (botones & R3) and (nuevos & (BACK | R3)):
                self.alternar_guia()
                self.back_solo = self.start_solo = False
                self.soltar_todo()
                self.soltar_juego()
                self.consumidos = botones
                vibrar(60, 20000)
                self.previo = botones
                continue

            if self.activo and juego_al_frente != self.en_juego:
                # Entrar o salir del juego: soltar todo; lo apretado no cuenta hasta soltarlo
                self.en_juego = juego_al_frente
                self.soltar_todo()
                self.soltar_juego()
                self.acum = [0.0, 0.0, 0.0, 0.0]
                self.back_solo = self.start_solo = False
                self.consumidos = botones
                if self.en_juego:
                    self.teclado.cerrar()
            if self.activo and self.en_juego:
                self.paso_juego(g, botones, nuevos, soltados, ahora)
            elif self.activo:
                hay_teclado = self.teclado.visible
                if hay_teclado != self.en_teclado:
                    # Al cambiar de modo, lo que esté apretado no cuenta hasta soltarlo
                    if hay_teclado:
                        self.entrar_teclado()
                    else:
                        self.salir_teclado()
                    self.consumidos = botones
                    self.back_solo = False
                nuevos_l = nuevos & ~self.consumidos
                if self.en_teclado:
                    soltados_l = soltados & ~self.consumidos
                    self.paso_teclado(g, botones & ~self.consumidos, nuevos_l, soltados_l, ahora)
                else:
                    self.paso_raton(g, botones, nuevos, soltados, ahora)

            self.consumidos &= botones
            self.previo = botones
            time.sleep(periodo)


def main():
    # Una sola copia a la vez
    kernel32.CreateMutexW(None, False, "Local\\MandoRatonPS3")
    if kernel32.GetLastError() == 183:
        return
    # Con el argumento "espera" arranca dormido y se enciende con Back + Start (inicio de Windows)
    Mando(en_espera="espera" in sys.argv[1:]).bucle()


if __name__ == "__main__":
    main()
