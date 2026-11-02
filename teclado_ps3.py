"""Teclado en pantalla propio, al estilo del teclado de la PS3, para usarlo con el mando.

- Escribe directo en la ventana que tiene el foco (SendInput Unicode): á é í ó ú ñ ü ¿ ¡ salen
  siempre, sin depender de la distribución de teclado de Windows.
- Texto predictivo: arriba salen palabras que empiezan como la que estás escribiendo, sin importar
  tildes ni eñes ("cancion" propone "canción", "nino" propone "niño"). Aprende las palabras que
  usas (palabras_usuario.json). Lista base: palabras_es.txt (una por línea, las más usadas primero).
- Tildes: mantener A sobre una vocal, o la tecla ´ y luego la vocal.
- Mayúsculas con RT (o la tecla ⇧): 1 vez = una letra, 2 = bloqueadas, 3 = normal.
- LT = números y símbolos: los números salen como un teclado numérico, a la derecha.
- Estilo "anillo de luz": teclas con relieve, la elegida hundida y encendida en verde, y la frase en
  una pantallita tipo LCD. El tamaño sale de la pantalla (PROPORCION de su ancho), para verlo desde el sofá.
- Se pega justo debajo (o encima, si abajo no cabe) del campo donde escribes. En el menú Inicio
  (que tapa cualquier ventana) se pone al lado del menú, más chico si hace falta.
- Arriba de las sugerencias se ve la frase entera que vas escribiendo.
- Suena como el de la PS3: un tic suave al moverte y un clic al pulsar (sonido_*.wav, se generan solos).
La ventana nunca toma el foco. Corre en su propio hilo (tkinter): mando_raton.py le manda órdenes
con comando(); también responde a clics del ratón sobre las teclas.
"""
import ctypes
import json
import math
import os
import queue
import struct
import threading
import time
import tkinter as tk
import unicodedata
import wave
import winsound
from ctypes import wintypes
from tkinter import font as tkfont

import rutas

DICCIONARIO = rutas.programa("palabras_es.txt")
RESERVA = rutas.programa("palabras_reserva.txt")   # tercera capa: 12 000 palabras por frecuencia real
LETRAS_RESERVA = 3        # la reserva solo completa sugerencias desde esta cantidad de letras
APRENDIDAS = rutas.datos("palabras_usuario.json")
MANTENER_TILDE = 0.45     # s con A sobre una vocal = vocal con tilde
MAX_SUGERENCIAS = 5
SONIDO = True
# Tamaño: el teclado ocupa esta parte del ancho de la pantalla donde está el campo (y nunca más de
# ALTO_MAX de su alto). Así se ve igual de grande en cualquier resolución (pedido 2026-10-31: se usa
# desde el sofá, a 3-4 m de la tele; la mitad fija del 30-10 quedó muy chica).
PROPORCION = 0.40
OPACIDAD = 0.88           # ventana semitransparente, estilo vidrio de la PS3 (pedido 2026-10-31)
ALTO_MAX = 0.48

# Colores del estilo "anillo de luz" (los mismos de la guía y la mini ventana)
CLAVE = "#010203"         # color que se vuelve transparente (esquinas redondeadas de la ventana)
PLACA, BORDE = "#1e2127", "#343944"
CARA, SOMBRA, CANTO = "#2f343e", "#181a1f", "#424855"       # tecla normal: cara, sombra, borde de luz
CARA_ESP, SOMBRA_ESP = "#262a31", "#15171b"                  # teclas de acción
CARA_NUM, SOMBRA_NUM = "#3a404c", "#1c1f25"                  # teclado numérico (capa de símbolos)
HUNDIDA = "#2d313a"
TEXTO, SUAVE, OSCURO = "#f1f3f6", "#c9ced8", "#15171b"
LUZ = "#3ff06b"           # la tecla elegida, el cursor y las mayúsculas encendidas
LCD, LCD_BORDE = "#0b1610", "#22302a"
PILDORA, PILDORA_SEL = "#2a2e36", "#e9ecf1"
VERDE, ROJO, AZUL, AMARILLO = "#4cc75a", "#f0524a", "#4b8ff0", "#f1c232"

user32 = ctypes.WinDLL("user32")


def aclarar(color, t=0.45):
    """El mismo color mezclado con blanco (el brillo de los domos A B X Y)."""
    r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02x%02x%02x" % tuple(round(c + (255 - c) * t) for c in (r, g, b))


# ---------- Envío de teclas (SendInput) ----------
class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class _ENTRADA(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _ENTRADA)]


UNICODE, KEYUP, EXTENDED = 0x4, 0x2, 0x1
VK_BACK, VK_RETURN, VK_LEFT, VK_RIGHT = 0x08, 0x0D, 0x25, 0x27


def _evento(vk=0, scan=0, flags=0):
    e = INPUT(type=1)
    e.u.ki = KEYBDINPUT(vk, scan, flags, 0, 0)
    return e


def _enviar(eventos):
    if eventos:
        arr = (INPUT * len(eventos))(*eventos)
        user32.SendInput(len(eventos), arr, ctypes.sizeof(INPUT))


def escribir(texto):
    """Escribe texto tal cual en la ventana con foco (cualquier carácter)."""
    datos = texto.encode("utf-16-le")
    ev = []
    for i in range(0, len(datos), 2):
        u = int.from_bytes(datos[i:i + 2], "little")
        ev += [_evento(0, u, UNICODE), _evento(0, u, UNICODE | KEYUP)]
    _enviar(ev)


def pulsar(vk, veces=1):
    f = EXTENDED if vk in (VK_LEFT, VK_RIGHT) else 0
    _enviar([e for _ in range(veces) for e in (_evento(vk, 0, f), _evento(vk, 0, f | KEYUP))])


# ---------- Sonidos (sintetizados, parecidos a los del teclado de la PS3) ----------
SONIDOS = {
    # nombre: (duración s, [(frecuencia Hz, volumen)], caída s)
    "mover": (0.022, [(2300, 0.22), (4600, 0.05)], 0.004),   # tic suave y agudo al moverse
    "tecla": (0.045, [(1200, 0.30), (2400, 0.12), (3600, 0.04)], 0.009),  # clic al pulsar
}


def _crear_sonido(ruta, dur, tonos, caida, tasa=44100):
    n = int(dur * tasa)
    datos = bytearray()
    for i in range(n):
        t = i / tasa
        env = min(1.0, t / 0.0008) * math.exp(-t / caida)   # ataque de 0,8 ms y caída rápida
        v = sum(a * math.sin(2 * math.pi * f * t) for f, a in tonos) * env
        datos += struct.pack("<h", int(max(-1, min(1, v)) * 32767))
    with wave.open(ruta, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(tasa)
        w.writeframes(bytes(datos))


def preparar_sonidos():
    archivos = {}
    for nombre, (dur, tonos, caida) in SONIDOS.items():
        ruta = rutas.programa("sonido_%s.wav" % nombre)
        if not os.path.exists(ruta):
            ruta = rutas.datos("sonido_%s.wav" % nombre)     # si faltan, se crean en tus datos
        if not os.path.exists(ruta):
            try:
                _crear_sonido(ruta, dur, tonos, caida)
            except OSError:
                continue
        archivos[nombre] = ruta
    return archivos


def sonar(archivos, nombre):
    if SONIDO and nombre in archivos:
        try:
            winsound.PlaySound(archivos[nombre], winsound.SND_FILENAME | winsound.SND_ASYNC
                               | winsound.SND_NODEFAULT)
        except RuntimeError:
            pass


# ---------- Pantalla ----------
class _RECT(ctypes.Structure):
    _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG),
                ("right", wintypes.LONG), ("bottom", wintypes.LONG)]


class _MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", _RECT), ("rcWork", _RECT),
                ("dwFlags", wintypes.DWORD)]


def area_trabajo(x, y):
    """(izq, arriba, der, abajo) de la pantalla donde está el punto, sin la barra de tareas."""
    user32.MonitorFromPoint.restype = ctypes.c_void_p
    user32.MonitorFromPoint.argtypes = [wintypes.POINT, wintypes.DWORD]
    user32.GetMonitorInfoW.argtypes = [ctypes.c_void_p, ctypes.POINTER(_MONITORINFO)]
    mon = user32.MonitorFromPoint(wintypes.POINT(int(x), int(y)), 2)   # 2 = el más cercano
    info = _MONITORINFO(cbSize=ctypes.sizeof(_MONITORINFO))
    if mon and user32.GetMonitorInfoW(mon, ctypes.byref(info)):
        r = info.rcWork
        return r.left, r.top, r.right, r.bottom
    return None


# Menú Inicio y búsqueda de Windows: van por encima de todas las ventanas "siempre encima" (Windows
# no deja que un programa normal los tape), así que el teclado tiene que ponerse al lado.
SHELL = {"startmenuexperiencehost.exe", "searchhost.exe", "searchapp.exe", "shellexperiencehost.exe"}


def rect_shell():
    """Si la ventana activa es el menú Inicio o la búsqueda de Windows: su rectángulo; si no, None."""
    kernel32 = ctypes.WinDLL("kernel32")
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    kernel32.OpenProcess.restype = ctypes.c_void_p
    proc = kernel32.OpenProcess(0x1000, False, pid.value)   # PROCESS_QUERY_LIMITED_INFORMATION
    if not proc:
        return None
    try:
        buf = ctypes.create_unicode_buffer(520)
        n = wintypes.DWORD(520)
        kernel32.QueryFullProcessImageNameW.argtypes = [ctypes.c_void_p, wintypes.DWORD,
                                                         wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
        if not kernel32.QueryFullProcessImageNameW(proc, 0, buf, ctypes.byref(n)):
            return None
    finally:
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel32.CloseHandle(proc)
    if os.path.basename(buf.value).lower() not in SHELL:
        return None
    r = _RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    return r.left, r.top, r.right, r.bottom


# ---------- Texto predictivo ----------
def plano(texto):
    """Minúsculas sin tildes ni eñe: para comparar 'cancion' con 'canción'."""
    t = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


class Predictor:
    """Tres capas: lista fija + memoria propia, y una reserva grande que solo completa.

    La memoria (palabras_usuario.json) guarda cada palabra que escribes tal cual (respeta las
    mayúsculas de nombres propios: Kojima, Claude, Fallout), cuántas veces y cuándo la usaste, y qué
    palabra vino después de cuál (Winning -> Eleven, Darío -> Amodei). Lo tuyo siempre sale antes que
    la lista fija, y lo usado hace poco antes que lo viejo. Si con 3 letras o más esas dos capas dan
    menos de 5 sugerencias, se completan con la reserva (palabras_reserva.txt, por frecuencia real).
    """
    RECIENTE = 7 * 24 * 3600   # s: lo usado esta semana pesa más

    def __init__(self):
        self.base = {}        # palabra -> posición (0 = la más usada)
        try:
            with open(DICCIONARIO, encoding="utf-8") as f:
                for i, linea in enumerate(f):
                    p = linea.strip()
                    if len(p) > 1 and p not in self.base:
                        self.base[p] = i
        except OSError:
            pass
        self.planos = {p: plano(p) for p in self.base}
        self.en_reserva = set()
        self.reserva = []     # (plana, palabra), de la más usada a la menos
        try:
            with open(RESERVA, encoding="utf-8") as f:
                for linea in f:
                    p = linea.strip()
                    if len(p) > 1 and not p.startswith("#") and p not in self.base:
                        self.reserva.append((plano(p), p))
                        self.en_reserva.add(p)
        except OSError:
            pass
        self.palabras = {}    # palabra -> [veces, último uso]
        self.siguientes = {}  # palabra -> {palabra que vino después: veces}
        try:
            with open(APRENDIDAS, encoding="utf-8") as f:
                datos = json.load(f)
            self.palabras = {k: list(v) for k, v in datos.get("palabras", {}).items() if len(k) > 1}
            self.siguientes = datos.get("siguientes", {})
        except (OSError, ValueError, AttributeError, TypeError):
            pass

    def _peso(self, p, ahora):
        veces, cuando = self.palabras.get(p, (0, 0))
        return veces + (3 if ahora - cuando < self.RECIENTE else 0)

    def sugerir(self, prefijo, anterior=""):
        ahora = time.time()
        despues = self.siguientes.get(anterior, {})
        pp = plano(prefijo)
        if not pp:
            # sin letras todavía: proponer lo que suele venir después de la palabra anterior
            return sorted(despues, key=lambda p: (-despues[p], -self._peso(p, ahora)))[:MAX_SUGERENCIAS]
        candidatas = {}
        for p in list(self.palabras) + list(self.base):
            if p.lower() == prefijo.lower() or p in candidatas or not (self.planos.get(p) or plano(p)).startswith(pp):
                continue
            candidatas[p] = (plano(p) != pp,               # misma palabra con otra tilde/eñe: primero
                             -despues.get(p, 0),           # lo que sueles escribir después de la anterior
                             p not in self.palabras,       # lo tuyo antes que la lista fija
                             -self._peso(p, ahora),
                             self.base.get(p, 10 ** 6))
        mejores = sorted(candidatas, key=candidatas.get)[:MAX_SUGERENCIAS]
        if len(mejores) < MAX_SUGERENCIAS and len(pp) >= LETRAS_RESERVA:
            for plana, p in self.reserva:
                if plana.startswith(pp) and p not in candidatas and p.lower() != prefijo.lower():
                    mejores.append(p)
                    if len(mejores) == MAX_SUGERENCIAS:
                        break
        if prefijo[:1].isupper():
            todo = len(prefijo) > 1 and prefijo.isupper()
            mejores = [p.upper() if todo else p[:1].upper() + p[1:] for p in mejores]
        return mejores

    def aprender(self, palabra, anterior=""):
        if len(palabra) < 2 or not palabra.isalpha():
            return
        # "Casa" a principio de frase es "casa"; "Kojima" se guarda tal cual
        if palabra not in self.base and (palabra.lower() in self.base or palabra.lower() in self.en_reserva):
            palabra = palabra.lower()
        dato = self.palabras.setdefault(palabra, [0, 0])
        dato[0] += 1
        dato[1] = int(time.time())
        if anterior:
            sig = self.siguientes.setdefault(anterior, {})
            sig[palabra] = sig.get(palabra, 0) + 1
        try:
            with open(APRENDIDAS, "w", encoding="utf-8") as f:
                json.dump({"palabras": self.palabras, "siguientes": self.siguientes}, f,
                          ensure_ascii=False, indent=0)
        except OSError:
            pass


# ---------- Distribución ----------
# (etiqueta, acción, ancho en columnas). Acción None = escribir la etiqueta. 12 columnas.
# Enter va donde en un teclado normal: al final de la fila de la "a" (pedido 2026-10-31).
CAPAS = {
    "letras": [
        [(c, None, 1) for c in "1234567890"] + [("⌫", "borrar", 2)],
        [(c, None, 1) for c in "qwertyuiop"] + [("´", "tilde", 1), ("@", None, 1)],
        [(c, None, 1) for c in "asdfghjklñ"] + [("Enter ↵", "enter", 2)],
        [("⇧", "mayus", 1)] + [(c, None, 1) for c in "zxcvbnm,.-/"],
        [("?123  LT", "capa", 2), ("espacio", "espacio", 8), ("?", None, 1), ("!", None, 1)],
    ],
    # símbolos a la izquierda y los números como teclado numérico a la derecha (columnas 8 a 11)
    "simbolos": [
        [(c, None, 1) for c in "!¡?¿()[]789"] + [("⌫", "borrar", 1)],
        [(c, None, 1) for c in "\"'#$%&=~456-"],
        [(c, None, 1) for c in "{}<>_^°€123+"],
        [(c, None, 1) for c in r":;@/\*|ü0.,"] + [("↵", "enter", 1)],
        [("abc  LT", "capa", 2), ("espacio", "espacio", 9), ("´", "tilde", 1)],
    ],
}
COL_NUMERICO = 8          # en la capa de símbolos, desde esta columna empieza el teclado numérico
CON_TILDE = {"a": "á", "e": "é", "i": "í", "o": "ó", "u": "ú",
             "A": "Á", "E": "É", "I": "Í", "O": "Ó", "U": "Ú"}
SUG = -1   # índice de la fila de sugerencias


class Teclado:
    def __init__(self, vibrar=None):
        self.visible = False
        self._cola = queue.Queue()
        self._vibrar = vibrar or (lambda: None)
        self.pred = Predictor()
        self._listo = threading.Event()
        threading.Thread(target=self._hilo, daemon=True).start()
        self._listo.wait(5)

    # ----- API: se puede llamar desde cualquier hilo -----
    def abrir(self, campo=None):
        """campo = (x, y, ancho, alto) del campo de texto: el teclado se pone en el lado contrario."""
        self._cola.put(("abrir", campo))

    def cerrar(self):
        self._cola.put(("cerrar",))

    def comando(self, *orden):
        """mover arr/aba/izq/der · a_abajo · a_arriba · borrar · espacio · cursor izq/der ·
        capa · mayus · arrastrar dx dy · enviar · cerrar"""
        self._cola.put(orden)

    # ----- hilo de la ventana -----
    def _hilo(self):
        antes = user32.GetForegroundWindow()
        self.raiz = r = tk.Tk()
        r.withdraw()
        r.overrideredirect(True)
        r.attributes("-topmost", True)
        r.configure(bg=CLAVE)
        r.attributes("-transparentcolor", CLAVE)
        r.attributes("-alpha", OPACIDAD)        # vidrio: se ve lo de atrás, como en la PS3
        r.update()
        # Que nunca tome el foco (Tk lo roba al crearse: se devuelve enseguida)
        self.hwnd = user32.GetParent(r.winfo_id()) or r.winfo_id()
        get = user32.GetWindowLongPtrW
        get.restype = ctypes.c_ssize_t
        user32.SetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_ssize_t]
        user32.SetWindowLongPtrW(self.hwnd, -20, get(self.hwnd, -20) | 0x08000000 | 0x80)
        if antes:
            user32.SetForegroundWindow(antes)

        self.e = r.winfo_fpixels("1i") / 96
        # tamaños de letra en píxeles (negativos para tkinter): crecen con el teclado, no con los ppp
        self.f_tecla = tkfont.Font(family="Bahnschrift", size=-22)
        self.f_peq = tkfont.Font(family="Bahnschrift", size=-15, weight="bold")
        self.f_sug = tkfont.Font(family="Bahnschrift", size=-18)
        self.f_frase = tkfont.Font(family="Consolas", size=-21)
        self.f_pie = tkfont.Font(family="Bahnschrift", size=-15)
        self.f_boton = tkfont.Font(family="Bahnschrift", size=-13, weight="bold")
        self.cv = tk.Canvas(r, bg=CLAVE, highlightthickness=0)
        self.cv.pack()
        self.cv.bind("<Button-1>", self._clic)
        self.sw, self.sh = r.winfo_screenwidth(), r.winfo_screenheight()
        self.campo = None                       # (x, y, ancho, alto) del campo donde se escribe
        self.escala = None
        self._medidas(1.0)
        self.HUECO = int(8 * self.e)            # separación entre el campo y el teclado
        self.evitar = None                      # rectángulo del menú Inicio (no se puede tapar)
        self.lado = "abajo"
        self.sonidos = preparar_sonidos()
        self._colocar("abajo")

        self.capa = "letras"
        self.fila, self.col = 2, 4              # empieza en la "g"
        self.mayus = 0                          # 0 no, 1 una letra, 2 bloqueada
        self.volver = None                      # (fila, col) a la que volver tras elegir sugerencia
        self.tilde = False
        self.frase = ""                         # lo escrito desde que se abrió (se ve arriba)
        self.pos = 0                            # dónde está el cursor del texto dentro de la frase
        self.palabra = ""
        self.anterior = ""                     # última palabra terminada (para proponer la siguiente)
        self.sugerencias = []
        self.sug = 0
        self.a_t = None                         # A mantenida sobre una vocal
        self._dibujar()
        self._listo.set()
        r.after(10, self._atender)
        r.mainloop()

    def _atender(self):
        try:
            while True:
                orden = self._cola.get_nowait()
                try:
                    getattr(self, "_c_" + orden[0])(*orden[1:])
                except Exception:
                    pass
                if self.visible or orden[0] in ("enviar", "cerrar"):
                    if orden[0] == "mover":
                        sonar(self.sonidos, "mover")
                    elif orden[0] in ("a_abajo", "borrar", "espacio", "cursor", "capa", "enviar", "mayus"):
                        sonar(self.sonidos, "tecla")
        except queue.Empty:
            pass
        # A mantenida sobre una vocal: tilde
        if self.a_t is not None and time.monotonic() - self.a_t >= MANTENER_TILDE:
            self.a_t = None
            etq = self._tecla_actual()[0]
            self._insertar(CON_TILDE.get(self._con_mayus(etq), etq))
            self._vibrar()
        self.raiz.after(10, self._atender)

    # ----- geometría -----
    # medidas de diseño (píxeles con z = 1): tecla, hueco, margen, filas de frase / sugerencias / pie
    T, G, M = 54, 6, 16
    ALTO_FRASE, ALTO_SUG, ALTO_PIE = 46, 38, 30
    ANCHO_DISENO = 2 * M + 12 * T + 11 * G
    ALTO_DISENO = M + ALTO_FRASE + 10 + ALTO_SUG + 10 + 5 * T + 4 * G + 12 + ALTO_PIE + M

    def _z_base(self):
        """Tamaño para la pantalla del campo: PROPORCION de su ancho, sin pasar ALTO_MAX de su alto."""
        izq, arr, der, aba = self._pantalla()
        return min(PROPORCION * (der - izq) / self.ANCHO_DISENO, ALTO_MAX * (aba - arr) / self.ALTO_DISENO)

    def _medidas(self, escala):
        """Tamaño de teclas y letras según la pantalla. escala 1 = normal; menos en el menú Inicio
        si no cabe al lado."""
        z = self._z_base() * escala
        if (escala, z) == (self.escala, getattr(self, "z", None)):
            return
        self.escala, self.z = escala, z
        p, d = self._px, Teclado
        self.T, self.G, self.M = p(d.T), max(2, p(d.G)), p(d.M)
        self.ALTO_FRASE, self.ALTO_SUG, self.ALTO_PIE = p(d.ALTO_FRASE), p(d.ALTO_SUG), p(d.ALTO_PIE)
        for fuente, tam in ((self.f_tecla, 22), (self.f_peq, 15), (self.f_sug, 18), (self.f_frase, 21),
                            (self.f_pie, 15), (self.f_boton, 13)):
            fuente.configure(size=-max(9, round(tam * z)))
        self.Y_SUG = self.M + self.ALTO_FRASE + p(10)
        self.Y_TECLAS = self.Y_SUG + self.ALTO_SUG + p(10)
        self.ancho = self.M * 2 + 12 * self.T + 11 * self.G
        self.alto = self.Y_TECLAS + 5 * self.T + 4 * self.G + p(12) + self.ALTO_PIE + self.M
        self.cv.configure(width=self.ancho, height=self.alto)

    def _filas(self):
        return CAPAS[self.capa]

    def _inicio_col(self, fila, i):
        return sum(t[2] for t in self._filas()[fila][:i])

    def _tecla_actual(self):
        return self._filas()[self.fila][self.col]

    def _caja(self, fila, i):
        x = self.M + self._inicio_col(fila, i) * (self.T + self.G)
        y = self.Y_TECLAS + fila * (self.T + self.G)
        ancho = self._filas()[fila][i][2]
        return x, y, x + ancho * self.T + (ancho - 1) * self.G, y + self.T

    def _px(self, n):
        """n píxeles del diseño, al tamaño actual del teclado."""
        return max(1, round(n * self.z))

    def _cajas_sug(self):
        x = self.M
        cajas = []
        for s in self.sugerencias:
            w = self.f_sug.measure(s) + self._px(28)
            cajas.append((x, self.Y_SUG, x + w, self.Y_SUG + self.ALTO_SUG))
            x += w + self.G
        return cajas

    # ----- dibujo -----
    def _redondo(self, x1, y1, x2, y2, r, color, borde=None, ancho=1):
        cv = self.cv
        r = min(r, (x2 - x1) / 2, (y2 - y1) / 2)
        pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
               x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
        cv.create_polygon(pts, smooth=True, fill=color, outline=borde or color, width=ancho)

    def _tecla(self, x1, y1, x2, y2, cara, sombra, canto=None):
        """Tecla con relieve: la sombra asoma abajo (el canto) y una línea de luz arriba."""
        r, h = self._px(8), self._px(4)
        self._redondo(x1, y1 + h, x2, y2, r, sombra)
        self._redondo(x1, y1, x2, y2 - h, r, cara)
        if canto:
            self.cv.create_line(x1 + r, y1 + 1, x2 - r, y1 + 1, fill=canto)

    def _boton(self, x, y, nombre, color=None):
        """Botón del mando en el pie: domo de color (A B X Y) o tecla con el nombre. Devuelve la x final."""
        cv, rr = self.cv, self._px(12)
        if color:
            cv.create_oval(x, y - rr + self._px(2), x + 2 * rr, y + rr + self._px(2), fill="#000000", outline="")
            cv.create_oval(x, y - rr, x + 2 * rr, y + rr, fill=color, outline="")
            cv.create_oval(x + rr * 0.45, y - rr * 0.75, x + rr * 1.05, y - rr * 0.3, fill=aclarar(color),
                           outline="")
            cv.create_text(x + rr, y, text=nombre, fill="#111111", font=self.f_boton)
            return x + 2 * rr
        w = self.f_boton.measure(nombre) + self._px(16)
        self._tecla(x, y - rr, x + w, y + rr + self._px(2), "#3a3f4b", "#23262d")
        cv.create_text(x + w / 2, y - self._px(1), text=nombre, fill=TEXTO, font=self.f_boton)
        return x + w

    def _con_mayus(self, etq):
        return etq.upper() if self.mayus and len(etq) == 1 else etq

    def _dibujar(self):
        cv, p = self.cv, self._px
        cv.delete("all")
        # la placa (las esquinas de la ventana son transparentes)
        self._redondo(0, 0, self.ancho - 1, self.alto - 1, p(18), PLACA, BORDE)
        cv.create_line(p(18), 2, self.ancho - p(18), 2, fill="#2a2e36")
        # la frase entera que vas escribiendo, en una pantallita LCD (si no cabe, se ve el final)
        x1, y1, x2, y2 = self.M, self.M, self.ancho - self.M, self.M + self.ALTO_FRASE
        self._redondo(x1, y1, x2, y2, p(8), LCD, LCD_BORDE)
        yf = (y1 + y2) / 2
        if self.frase:
            disponible = x2 - x1 - p(28)
            antes, despues = self.frase[:self.pos], self.frase[self.pos:]
            recorte = ""
            while antes and self.f_frase.measure(recorte + antes + "m") > disponible:
                antes, recorte = antes[1:], "…"
            while despues and self.f_frase.measure(recorte + antes + "m" + despues) > disponible:
                despues = despues[:-1]
            xt = x1 + p(14)
            cv.create_text(xt, yf, text=recorte + antes, anchor="w", fill=LUZ, font=self.f_frase)
            xc = xt + self.f_frase.measure(recorte + antes)
            wc = self.f_frase.measure("m")
            cv.create_rectangle(xc + 1, yf - p(11), xc + max(3, wc * 0.55), yf + p(11), fill=LUZ, outline="")
            cv.create_text(xc + wc * 0.55 + 3, yf, text=despues, anchor="w", fill=LUZ, font=self.f_frase)
        else:
            cv.create_text(x1 + p(14), yf, text="lo que escribas se ve aquí", anchor="w", fill="#5fa874",
                           font=self.f_frase)
        # sugerencias (se llega subiendo con la cruceta / stick izquierdo; A escribe la iluminada)
        for i, (s, caja) in enumerate(zip(self.sugerencias, self._cajas_sug())):
            sel = self.fila == SUG and self.sug == i
            self._redondo(*caja, self.ALTO_SUG / 2, PILDORA_SEL if sel else PILDORA)
            cv.create_text((caja[0] + caja[2]) / 2, (caja[1] + caja[3]) / 2, text=s,
                           fill=OSCURO if sel else "#dfe3ea", font=self.f_sug)
        # teclas
        for f, fila in enumerate(self._filas()):
            for i, (etq, accion, _) in enumerate(fila):
                x1, y1, x2, y2 = self._caja(f, i)
                sel = self.fila == f and self.col == i
                numerico = self.capa == "simbolos" and self._inicio_col(f, i) >= COL_NUMERICO
                encendida = (accion == "mayus" and self.mayus == 1) or (accion == "tilde" and self.tilde)
                bloq = accion == "mayus" and self.mayus == 2
                texto = self._con_mayus(etq) if accion is None else etq
                if accion == "mayus":
                    texto = {0: "⇧", 1: "⇧ 1", 2: "BLOQ"}[self.mayus]
                fuente = self.f_peq if len(texto) > 1 else self.f_tecla
                if sel:                          # hundida y encendida
                    h = p(3)
                    self._redondo(x1, y1 + h, x2, y2, p(8), HUNDIDA, LUZ, max(2, p(2)))
                    color = LUZ
                    yt = (y1 + h + y2) / 2
                elif bloq:
                    self._tecla(x1, y1, x2, y2, LUZ, "#1f7a38")
                    color, yt = OSCURO, (y1 + y2 - p(4)) / 2
                else:
                    if accion:
                        self._tecla(x1, y1, x2, y2, CARA_ESP, SOMBRA_ESP, "#353a45")
                    elif numerico:
                        self._tecla(x1, y1, x2, y2, CARA_NUM, SOMBRA_NUM, "#4b5260")
                    else:
                        self._tecla(x1, y1, x2, y2, CARA, SOMBRA, CANTO)
                    color = LUZ if encendida else (SUAVE if accion else TEXTO)
                    yt = (y1 + y2 - p(4)) / 2
                cv.create_text((x1 + x2) / 2, yt, text=texto, fill=color, font=fuente)
                if accion is None and etq in "aeiouAEIOU" and not sel:
                    cv.create_text(x2 - p(8), y1 + p(9), text="´", fill="#7c8494", font=self.f_boton)
        # pie: qué hace cada botón
        y = self.alto - self.M - self.ALTO_PIE / 2
        pie = (("A", VERDE, "escribir"), ("X", AZUL, "borrar"), ("Y", AMARILLO, "espacio"),
               ("LB RB", None, "cursor"), ("RT", None, "mayús"), ("Start", None, "enviar"),
               ("B", ROJO, "cerrar"))
        # que quepa entero: si no, la letra del pie se achica
        tam = -self.f_pie.cget("size")
        while tam > 9:
            ancho = sum((2 * p(12) if c else self.f_boton.measure(b) + p(16)) + p(6)
                        + self.f_pie.measure(t) + p(14) for b, c, t in pie)
            if self.M + ancho <= self.ancho - self.M:
                break
            tam -= 1
            self.f_pie.configure(size=-tam)
        x = self.M
        for boton, color, texto in pie:
            x = self._boton(x, y, boton, color) + p(6)
            cv.create_text(x, y, text=texto, anchor="w", fill=SUAVE, font=self.f_pie)
            x += self.f_pie.measure(texto) + p(14)

    # ----- escribir -----
    def _frase_meter(self, texto):
        self.frase = self.frase[:self.pos] + texto + self.frase[self.pos:]
        self.pos += len(texto)

    def _frase_borrar(self, n=1):
        n = min(n, self.pos)
        self.frase = self.frase[:self.pos - n] + self.frase[self.pos:]
        self.pos -= n

    def _insertar(self, texto):
        escribir(texto)
        self._frase_meter(texto)
        if texto.isalnum():
            self.palabra += texto
        else:
            self._terminar_palabra(texto)
        self._actualizar()

    def _terminar_palabra(self, separador=" "):
        if self.palabra:
            self.pred.aprender(self.palabra, self.anterior)
            # la cadena de palabras se corta con puntuación (nueva frase / otro dato)
            self.anterior = self.palabra if separador == " " else ""
        elif separador != " ":
            self.anterior = ""
        self.palabra = ""

    def _actualizar(self):
        self.sugerencias = self.pred.sugerir(self.palabra, self.anterior)
        limite = self.ancho - self.M
        while self.sugerencias and self._cajas_sug()[-1][2] > limite:
            self.sugerencias.pop()
        if self.fila == SUG and not self.sugerencias:
            self._salir_sug()
        self.sug = min(self.sug, max(0, len(self.sugerencias) - 1))
        self._dibujar()

    def _escribir_letra(self, etq):
        letra = self._con_mayus(etq)
        if self.tilde:
            letra = CON_TILDE.get(letra, letra)
            self.tilde = False
        if self.mayus == 1 and len(etq) == 1 and etq.isalpha():
            self.mayus = 0
        self._insertar(letra)

    def _usar_sugerencia(self, i):
        if i >= len(self.sugerencias):
            return
        palabra = self.sugerencias[i]
        pulsar(VK_BACK, len(self.palabra))
        escribir(palabra + " ")
        self._frase_borrar(len(self.palabra))
        self._frase_meter(palabra + " ")
        self.palabra = palabra
        self._terminar_palabra()
        if self.fila == SUG:
            self._salir_sug()
        self._actualizar()

    def _salir_sug(self):
        """Deja la fila de sugerencias: vuelve a la tecla donde estabas al ir a las palabras."""
        filas = self._filas()
        if self.volver:
            f, c = self.volver
            self.fila, self.col = f, min(c, len(filas[f]) - 1)
        else:
            self.fila, self.col = 0, min(self.col, len(filas[0]) - 1)
        self.volver = None

    def _accion(self, accion, etq):
        if accion is None:
            self._escribir_letra(etq)
        elif accion == "borrar":
            self._c_borrar()
        elif accion == "espacio":
            self._c_espacio()
        elif accion == "enter":
            self._terminar_palabra("\n")
            pulsar(VK_RETURN)
            self.frase, self.pos = "", 0      # frase enviada: empieza otra
            self._actualizar()
        elif accion == "mayus":
            self._c_mayus()
        elif accion == "tilde":
            self.tilde = not self.tilde
            self._dibujar()
        elif accion == "capa":
            self._c_capa()

    # ----- órdenes del mando -----
    def _pantalla(self):
        """Zona útil (sin barra de tareas) de la pantalla del campo, o de la principal."""
        if self.campo:
            cx, cy, cw, ch = self.campo
            zona = area_trabajo(cx + cw / 2, cy + ch / 2)
        else:
            zona = area_trabajo(self.sw / 2, self.sh / 2)
        return zona or (0, 0, self.sw, self.sh)

    def _posicion(self, lado):
        """Pegado justo debajo / encima del campo, centrado en él (o en el borde de la pantalla
        si no hay campo). Nunca se sale de la pantalla."""
        izq, arr, der, aba = self._pantalla()
        if not self.campo:
            x = (izq + der - self.ancho) // 2
            y = aba - self.alto - self.HUECO if lado == "abajo" else arr + self.HUECO
            return x, y
        cx, cy, cw, ch = self.campo
        if lado in ("izq", "der", "sobre") and self.evitar:
            # menú Inicio: al lado del menú (a la altura del buscador) o encima de él
            mx1, my1, mx2, my2 = self.evitar
            if lado == "sobre":
                x, y = int(cx + cw / 2 - self.ancho / 2), my1 - self.alto - self.HUECO
            else:
                x = mx1 - self.ancho - self.HUECO if lado == "izq" else mx2 + self.HUECO
                y = cy
            return (max(izq, min(int(x), der - self.ancho)),
                    max(arr, min(int(y), aba - self.alto)))
        x = int(cx + cw / 2 - self.ancho / 2)
        # campos muy anchos (barra de direcciones): alinear con su principio, no con el centro
        if cw > self.ancho:
            x = cx
        x = max(izq, min(x, der - self.ancho))
        y = cy + ch + self.HUECO if lado == "abajo" else cy - self.alto - self.HUECO
        return x, max(arr, min(y, aba - self.alto))

    def _cabe(self, lado):
        izq, arr, der, aba = self._pantalla()
        cx, cy, cw, ch = self.campo
        if lado == "abajo":
            return cy + ch + self.HUECO + self.alto <= aba
        return cy - self.HUECO - self.alto >= arr

    def _menu_inicio(self):
        """Si el campo es el buscador del menú Inicio / búsqueda de Windows: el rectángulo que
        ocupa el menú (ninguna ventana puede ir encima de él). Si no, None."""
        r = rect_shell()
        if not r or not self.campo:
            return None
        izq, arr, der, aba = self._pantalla()
        cx, cy, cw, ch = self.campo
        # el buscador va arriba del menú y casi de lado a lado; el menú baja hasta la barra de tareas
        m = int(56 * self.e)
        zona = [cx - m, cy - int(40 * self.e), cx + cw + m, aba]
        # la ventana del menú, si no ocupa toda la pantalla, puede ser algo más grande
        if r[2] - r[0] < 0.8 * (der - izq) and r[0] <= cx and cx + cw <= r[2]:
            zona = [min(zona[0], r[0]), min(zona[1], r[1]), max(zona[2], r[2]), max(zona[3], r[3])]
        return tuple(zona)

    def _hueco_menu(self):
        """(lado, escala) donde el teclado cabe más grande sin tocar el menú Inicio."""
        izq, arr, der, aba = self._pantalla()
        mx1, my1, mx2, my2 = self.evitar
        h2 = 2 * self.HUECO
        huecos = {"izq": (mx1 - izq - h2, aba - arr - h2),
                  "der": (der - mx2 - h2, aba - arr - h2),
                  "sobre": (der - izq - h2, my1 - arr - h2)}

        def escala(lado):
            w, h = huecos[lado]
            z = self._z_base()
            return min(1.0, w / (self.ANCHO_DISENO * z), h / (self.ALTO_DISENO * z))
        lado = max(huecos, key=escala)
        return lado, escala(lado)

    def _elegir_lado(self, campo):
        """Debajo del campo si cabe; si no, encima; si no cabe en ninguno, donde tape menos.
        En el menú Inicio: al lado del menú, achicado si hace falta."""
        self.campo = tuple(campo) if campo and campo[2] > 0 and campo[3] > 0 else None
        self.evitar = self._menu_inicio()
        if self.evitar:
            lado, escala = self._hueco_menu()
            if escala >= 0.8:              # más chico ya no se lee: mejor el tamaño normal
                self._medidas(round(escala, 2))
                return lado
            self.evitar = None
        self._medidas(1.0)
        if not self.campo:
            return "abajo"
        if self._cabe("abajo"):
            return "abajo"
        if self._cabe("arriba"):
            return "arriba"
        cy, ch = self.campo[1], self.campo[3]

        def tapa(lado):
            y = self._posicion(lado)[1]
            return max(0, min(cy + ch, y + self.alto) - max(cy, y))
        return "arriba" if tapa("arriba") < tapa("abajo") else "abajo"

    def _colocar(self, lado):
        self.lado = lado
        self.raiz.geometry("+%d+%d" % self._posicion(lado))

    def _c_abrir(self, campo=None):
        if self.visible and campo:
            if tuple(campo) != self.campo:     # otro campo: otra frase
                self.frase, self.pos = "", 0
            self._colocar(self._elegir_lado(campo))
            self._actualizar()
        if not self.visible:
            self._colocar(self._elegir_lado(campo))
            self.frase, self.pos = "", 0
            self.palabra = ""
            self.anterior = ""
            self.tilde = False
            self.capa = "letras"
            self.fila, self.col = 2, 4
            self.volver = None
            self._actualizar()
            self.raiz.deiconify()
            self.raiz.attributes("-topmost", True)
            self.visible = True

    def _c_cerrar(self):
        if self.visible:
            self._terminar_palabra()
            self.raiz.withdraw()
            self.visible = False
            self.a_t = None

    def _c_mover(self, d):
        filas = self._filas()
        if self.fila == SUG:
            if d == "izq":
                self.sug = (self.sug - 1) % len(self.sugerencias)
            elif d == "der":
                self.sug = (self.sug + 1) % len(self.sugerencias)
            elif d == "aba":
                self._salir_sug()
            else:
                self.volver = None
                self.fila = len(filas) - 1
                self.col = self._col_en(self.fila, getattr(self, "_centro", 0.5))
            self._dibujar()
            return
        if d in ("izq", "der"):
            self.col = (self.col + (1 if d == "der" else -1)) % len(filas[self.fila])
            self._centro = self._inicio_col(self.fila, self.col) + filas[self.fila][self.col][2] / 2
        else:
            if not hasattr(self, "_centro"):
                self._centro = self._inicio_col(self.fila, self.col) + 0.5
            destino = self.fila + (1 if d == "aba" else -1)
            if destino < 0 and self.sugerencias:
                self.volver = None
                self.fila = SUG
                self._dibujar()
                return
            self.fila = destino % len(filas)
            self.col = self._col_en(self.fila, self._centro)
        self._dibujar()

    def _col_en(self, fila, centro):
        x = 0
        for i, t in enumerate(self._filas()[fila]):
            if x <= centro < x + t[2]:
                return i
            x += t[2]
        return len(self._filas()[fila]) - 1

    def _c_a_abajo(self):
        if self.fila == SUG:
            self._usar_sugerencia(self.sug)
            return
        etq, accion, _ = self._tecla_actual()
        if accion is None and etq in CON_TILDE:
            self.a_t = time.monotonic()      # se decide al soltar o al pasar el tiempo
        else:
            self._accion(accion, etq)

    def _c_a_arriba(self):
        if self.a_t is not None:
            self.a_t = None
            self._escribir_letra(self._tecla_actual()[0])

    def _c_borrar(self):
        pulsar(VK_BACK)
        self._frase_borrar()
        if not self.palabra:
            self.anterior = ""
        self.palabra = self.palabra[:-1]
        self._actualizar()

    def _c_espacio(self):
        self._insertar(" ")

    def _c_cursor(self, d):
        """LB / RB: mover el cursor del texto una letra."""
        pulsar(VK_LEFT if d == "izq" else VK_RIGHT)
        self.pos = max(0, min(len(self.frase), self.pos + (-1 if d == "izq" else 1)))
        # la palabra en el cursor sale de la frase (si el cursor queda al final de una palabra)
        self.palabra = ""
        if self.pos == len(self.frase) or not self.frase[self.pos].isalnum():
            i = self.pos
            while i > 0 and self.frase[i - 1].isalnum():
                i -= 1
            self.palabra = self.frase[i:self.pos]
        self.anterior = ""
        self._actualizar()

    def _c_mayus(self):
        """RT o la tecla ⇧: 1 vez = una mayúscula; 2 = bloqueadas; 3 = normal otra vez."""
        self.mayus = (self.mayus + 1) % 3
        self._dibujar()

    def _c_capa(self):
        """LT: letras <-> números y símbolos."""
        self.capa = "simbolos" if self.capa == "letras" else "letras"
        if self.fila != SUG:
            self.col = min(self.col, len(self._filas()[self.fila]) - 1)
        if self.volver:
            self.volver = (self.volver[0], min(self.volver[1], len(self._filas()[self.volver[0]]) - 1))
        self._dibujar()

    def _c_arrastrar(self, dx, dy):
        """Stick derecho: mueve el teclado a mano por la pantalla (puede pasar a otro monitor)."""
        if not self.visible:
            return
        gx = user32.GetSystemMetrics
        vx, vy, vw, vh = gx(76), gx(77), gx(78), gx(79)       # escritorio virtual (todas las pantallas)
        x = min(max(self.raiz.winfo_x() + int(dx), vx), vx + vw - self.ancho)
        y = min(max(self.raiz.winfo_y() + int(dy), vy), vy + vh - self.alto)
        self.lado = "libre"
        self.raiz.geometry("+%d+%d" % (x, y))

    def _c_enviar(self):
        self._terminar_palabra("\n")
        pulsar(VK_RETURN)
        self._c_cerrar()

    # ----- ratón -----
    def _clic(self, ev):
        for i, (x1, y1, x2, y2) in enumerate(self._cajas_sug()):
            if x1 <= ev.x <= x2 and y1 <= ev.y <= y2:
                self._usar_sugerencia(i)
                return
        for f, fila in enumerate(self._filas()):
            for i, (etq, accion, _) in enumerate(fila):
                x1, y1, x2, y2 = self._caja(f, i)
                if x1 <= ev.x <= x2 and y1 <= ev.y <= y2:
                    self.fila, self.col = f, i
                    self.volver = None
                    sonar(self.sonidos, "tecla")
                    self._accion(accion, etq)
                    return
