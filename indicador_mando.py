"""Mini ventana mientras el mando está activo, estilo "anillo de luz": el anillo del mando con el
logo al centro (jugador 1 encendido) y Back + R3 (lo que abre la guía). Sin textos.

Lo lanza mando_raton.py al encender (Back + Start) y lo cierra al pausar.
Ventana siempre encima y sin robar el foco. Tomarla por el anillo y arrastrar = moverla (posición
guardada en indicador_pos.json); clic en Back + R3 = minimizarla a la barra de tareas ("Teclamando");
al pulsarla ahí vuelve a su sitio.

Animaciones (solo en estos momentos, nunca en el uso diario; pedido 2026-11-05):
  - al encenderse: el anillo se llena cuadrante por cuadrante (2 s) y queda el del jugador 1;
  - al pausar (orden APAGAR): el anillo gira tres veces, como al apagar una Xbox 360, y se cierra;
  - mando nuevo sin configurar (o Back + R3 mantenidos 10 s): el anillo se llena, la ventana se
    despliega hacia arriba y muestra el mando dibujado para enseñarle los botones uno por uno.
Órdenes que recibe de mando_raton.py por stdin: CONECTADO, CONFIGURAR <joystick> [auto], APAGAR.
Le dice a mando_raton.py por stdout: CONFIG 1 (empezó) / CONFIG 0 (terminó), para que el mando
no mueva el cursor mientras se configura.
"""
import ctypes
import json
import os
import queue
import sys
import threading
from ctypes import wintypes
import time
import tkinter as tk

import configurar_mando as cfg
import guia_mando as gm
import mando_generico as mg
import rutas
from guia_mando import Glifos, Guia, seguir_al_padre

try:
    ctypes.WinDLL("user32").SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
except (AttributeError, OSError):
    pass

CLAVE = "#010203"   # color que se vuelve transparente (las esquinas redondeadas)
OPACIDAD = 0.88     # ventana semitransparente, estilo vidrio de la PS3 (pedido 2026-10-31)


POSICION = rutas.datos("indicador_pos.json")
ANCHO, ALTO = 272, 112     # píxeles de diseño (a 96 ppp; se escalan con la pantalla)
NOMBRE = "Teclamando"
CARPETA = rutas.PROGRAMA


def leer_pos(r, ancho=ANCHO, alto=ALTO):
    try:
        with open(POSICION, encoding="utf-8") as f:
            x, y = (int(v) for v in json.load(f))
        # guardada en otra pantalla (otro PC, monitor desconectado): si no se ve entera, a la esquina
        g = ctypes.WinDLL("user32").GetSystemMetrics
        vx, vy, vw, vh = g(76), g(77), g(78), g(79)        # escritorio virtual (todas las pantallas)
        if vx <= x and x + ancho <= vx + vw and vy <= y and y + alto <= vy + vh:
            return x, y
    except (OSError, ValueError, TypeError):
        pass
    return r.winfo_screenwidth() - ancho - 16, r.winfo_screenheight() - alto - 64


def guardar_pos(x, y):
    try:
        with open(POSICION, "w", encoding="utf-8") as f:
            json.dump([x, y], f)
    except OSError:
        pass


class VistaPrevia:
    """Vista previa de la barra de tareas = imagen de la guía de botones.

    Tk no dibuja si la ventana está fuera de la pantalla, así que al arrancar se dibuja la guía en
    una ventana invisible (alpha 0, sin foco), se fotografía con PrintWindow y se le entrega a Windows
    cuando la pide (DwmSetIconicThumbnail, mensaje WM_DWMSENDICONICTHUMBNAIL).
    """

    def __init__(self, raiz):
        self.u, self.g = ctypes.WinDLL("user32"), ctypes.WinDLL("gdi32")
        self.dwm = ctypes.WinDLL("dwmapi")
        u, g = self.u, self.g
        vp = ctypes.c_void_p
        g.CreateCompatibleDC.restype = vp
        g.CreateCompatibleDC.argtypes = [vp]
        g.CreateDIBSection.restype = vp
        g.CreateDIBSection.argtypes = [vp, vp, ctypes.c_uint, ctypes.POINTER(vp), vp, ctypes.c_uint]
        g.SelectObject.restype = vp
        g.SelectObject.argtypes = [vp, vp]
        g.DeleteObject.argtypes = [vp]
        g.DeleteDC.argtypes = [vp]
        g.SetStretchBltMode.argtypes = [vp, ctypes.c_int]
        g.StretchBlt.argtypes = [vp] + [ctypes.c_int] * 4 + [vp] + [ctypes.c_int] * 4 + [ctypes.c_uint]
        u.PrintWindow.argtypes = [vp, vp, ctypes.c_uint]
        self.dwm.DwmSetIconicThumbnail.argtypes = [vp, vp, ctypes.c_uint]
        self.dwm.DwmSetWindowAttribute.argtypes = [vp, ctypes.c_uint, vp, ctypes.c_uint]
        self.origen = None
        self.capturar(raiz)

    def dib(self, w, h):
        class BMI(ctypes.Structure):
            _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                        ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD),
                        ("biCompression", wintypes.DWORD), ("biSizeImage", wintypes.DWORD),
                        ("biXPelsPerMeter", wintypes.LONG), ("biYPelsPerMeter", wintypes.LONG),
                        ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]
        bmi = BMI(ctypes.sizeof(BMI), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)   # 32 bits, de arriba abajo
        bits = ctypes.c_void_p()
        hbm = self.g.CreateDIBSection(None, ctypes.byref(bmi), 0, ctypes.byref(bits), None, 0)
        return hbm, bits

    def capturar(self, raiz):
        u, g = self.u, self.g
        t = tk.Toplevel(raiz)
        t.withdraw()
        t.overrideredirect(True)
        t.attributes("-alpha", 0.0)
        Guia(contenedor=t)
        t.update()
        hw = u.GetParent(t.winfo_id()) or t.winfo_id()
        get = u.GetWindowLongPtrW
        get.restype = ctypes.c_ssize_t
        u.SetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_ssize_t]
        u.SetWindowLongPtrW(hw, -20, get(hw, -20) | 0x08000000 | 0x80)   # sin foco, sin botón
        t.geometry("+0+0")
        t.deiconify()
        t.update()
        time.sleep(0.25)
        t.update()
        w, h = t.winfo_width(), t.winfo_height()
        hbm, _ = self.dib(w, h)
        dc = g.CreateCompatibleDC(None)
        g.SelectObject(dc, hbm)
        if u.PrintWindow(hw, dc, 2):            # PW_RENDERFULLCONTENT
            self.origen = (dc, hbm, w, h)
        else:
            g.DeleteDC(dc)
            g.DeleteObject(hbm)
        t.destroy()

    def activar(self, hwnd):
        """Pedirle a Windows que use nuestra imagen como vista previa de esta ventana."""
        if not self.origen:
            return
        si = ctypes.c_int(1)
        for atributo in (7, 10):    # DWMWA_FORCE_ICONIC_REPRESENTATION, DWMWA_HAS_ICONIC_BITMAP
            self.dwm.DwmSetWindowAttribute(hwnd, atributo, ctypes.byref(si), 4)
        u = self.u
        WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_void_p, ctypes.c_uint,
                                     ctypes.c_size_t, ctypes.c_ssize_t)
        u.CallWindowProcW.restype = ctypes.c_ssize_t
        u.CallWindowProcW.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint,
                                      ctypes.c_size_t, ctypes.c_ssize_t]
        u.GetWindowLongPtrW.restype = ctypes.c_ssize_t
        anterior = u.GetWindowLongPtrW(hwnd, -4)      # GWLP_WNDPROC

        def proc(h, msg, wp, lp):
            if msg == 0x0323:                         # WM_DWMSENDICONICTHUMBNAIL
                try:
                    self.entregar(h, (lp >> 16) & 0xFFFF, lp & 0xFFFF)
                    return 0
                except Exception:
                    pass
            return u.CallWindowProcW(anterior, h, msg, wp, lp)

        self.proc = WNDPROC(proc)                     # guardar la referencia (si no, se libera)
        u.SetWindowLongPtrW(hwnd, -4, ctypes.cast(self.proc, ctypes.c_void_p).value)
        self.dwm.DwmInvalidateIconicBitmaps(ctypes.c_void_p(hwnd))

    def entregar(self, hwnd, max_w, max_h):
        dc0, _, w, h = self.origen
        k = min(max_w / w, max_h / h)
        tw, th = max(1, int(w * k)), max(1, int(h * k))
        hbm, bits = self.dib(tw, th)
        dc = self.g.CreateCompatibleDC(None)
        self.g.SelectObject(dc, hbm)
        self.g.SetStretchBltMode(dc, 4)               # HALFTONE: reducción suave
        self.g.StretchBlt(dc, 0, 0, tw, th, dc0, 0, 0, w, h, 0x00CC0020)
        # alfa opaco (si no, Windows la dibuja transparente)
        n = tw * th * 4
        datos = bytearray(ctypes.string_at(bits, n))
        datos[3::4] = b"\xff" * (n // 4)
        ctypes.memmove(bits, bytes(datos), n)
        self.dwm.DwmSetIconicThumbnail(hwnd, hbm, 0)
        self.g.DeleteDC(dc)
        self.g.DeleteObject(hbm)


ORDEN = (95, 185, 275, 5)        # inicio de cada cuadrante, en el orden en que se encienden (antihorario)
PACIENCIA = 8.0                  # s sin pulsar el botón que toca: se salta
DURACION_ANILLO = 2.0            # s de la animación del anillo
DESPLIEGUE = 0.25                # s de abrir / cerrar hacia arriba
MARGEN = 14                      # px de diseño alrededor del mando dibujado
MANDO_ANCHO, MANDO_ALTO = 508, 362   # lo que ocupa dibujar_cuerpo (de -18 a 344 en vertical)


def decir(texto):
    """Una línea para mando_raton.py (por la salida estándar, que no depende de sys.stdout)."""
    try:
        k = ctypes.WinDLL("kernel32")
        k.GetStdHandle.restype = ctypes.c_void_p
        k.WriteFile.argtypes = [ctypes.c_void_p, ctypes.c_char_p, wintypes.DWORD,
                                ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
        dato = (texto + "\n").encode()
        escrito = wintypes.DWORD()
        k.WriteFile(k.GetStdHandle(-11), dato, len(dato), ctypes.byref(escrito), None)
    except (OSError, ValueError, AttributeError):
        pass


def leer_ordenes(cola):
    try:
        for linea in sys.stdin:
            cola.put(linea.strip())
    except (OSError, ValueError, TypeError, AttributeError):
        pass


def suave(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


class Mini:
    """La mini ventana: el anillo y Back + R3, y (desplegada hacia arriba) el mando para configurar."""

    def __init__(self, raiz, vista, sin_animacion=False):
        self.raiz, self.vista = raiz, vista
        self.u = ctypes.WinDLL("user32")
        r = self.r = tk.Toplevel(raiz)
        r.overrideredirect(True)
        r.attributes("-topmost", True)
        r.configure(bg=CLAVE)
        r.attributes("-transparentcolor", CLAVE)
        r.attributes("-alpha", OPACIDAD)       # vidrio: se ve lo de atrás, como en la PS3
        e = self.e = r.winfo_fpixels("1i") / 96
        self.W, self.H = round(ANCHO * e), round(ALTO * e)
        self.extra = round((MANDO_ALTO * (ANCHO - 2 * MARGEN) / MANDO_ANCHO + 2 * MARGEN) * e)
        self.Ht = self.H                       # alto actual (crece al desplegar)
        self.sube = True                       # se despliega hacia arriba (abajo si no cabe)
        self.cv = tk.Canvas(r, width=self.W, height=self.H, bg=CLAVE, highlightthickness=0, cursor="fleur")
        self.cv.pack()
        self.g = Glifos(self.cv, e, alto=42)
        k = (self.W - 2 * MARGEN * e) / MANDO_ANCHO
        self.gm = Glifos(self.cv, k)           # el mando dibujado, a escala de la ventana
        logo = tk.PhotoImage(file=os.path.join(CARPETA, "icono_ancho.png"))     # 84 x 56
        m = round(8 * e)
        self.d = self.H - 2 * m
        ri = self.d * 0.31
        for zoom, sub in ((1, 1), (5, 6), (3, 4), (2, 3), (3, 5), (1, 2)):
            if logo.width() * zoom / sub <= 2 * ri * 0.92:
                break
        if (zoom, sub) != (1, 1):
            logo = logo.zoom(zoom).subsample(sub)
        self.logo = logo
        self.ext = [80, 0, 0, 0]               # cuánto se enciende cada cuadrante (grados)
        self.color = gm.LUZ
        self.rotacion = None                   # cuadrante único encendido (animación de apagado)
        self.pos = list(leer_pos(r, self.W, self.H))
        self.anim = None                       # animación en curso (id de after)
        self.cfg = None                        # configuración rápida en curso
        self.cola = queue.Queue()
        self.arrastre = {}
        self.zona_min = (0, 0, 0, 0)
        self.minimizada = False
        self.dibujar()
        self.poner()
        cv = self.cv
        cv.bind("<ButtonPress-1>", self.apretar)
        cv.bind("<B1-Motion>", self.mover)
        cv.bind("<ButtonRelease-1>", self.soltar)
        raiz.bind("<Map>", self.restaurar)
        r.update()
        hwnd = self.u.GetParent(r.winfo_id()) or r.winfo_id()
        get = self.u.GetWindowLongPtrW
        get.restype = ctypes.c_ssize_t
        self.u.SetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_ssize_t]
        # sin robar el foco y sin botón propio en la barra (el de la barra es el de la raíz)
        self.u.SetWindowLongPtrW(hwnd, -20, get(hwnd, -20) | 0x08000000 | 0x80)
        threading.Thread(target=leer_ordenes, args=(self.cola,), daemon=True).start()
        self.sondear()
        if not sin_animacion:
            self.encender()

    # ----- dibujo -----
    def dibujar(self):
        cv, g, e, W, H, Ht = self.cv, self.g, self.e, self.W, self.H, self.Ht
        yo = Ht - H                                     # la barra siempre queda abajo
        cv.delete("all")
        g.redondo(0, 0, W - 1, Ht - 1, H / 2, gm.PLACA, gm.BORDE)
        cv.create_line(H / 2, 2, W - H / 2, 2, fill="#2a2e36")
        if yo > 2:
            self.dibujar_mando(yo)
            cv.create_line(H / 2, yo, W - H / 2, yo, fill="#2a2e36")
        m, d = round(8 * e), self.d
        cx, cy = m + d / 2, yo + H / 2
        cv.create_oval(m, yo + m, m + d, yo + m + d, fill="#121418", outline="")
        a = d * 0.10                                    # el anillo va un poco adentro del borde
        caja = (m + a, yo + m + a, m + d - a, yo + m + d - a)
        grosor = max(4, round(7 * e))
        for k, inicio in enumerate(ORDEN):               # los cuadrantes: apagados y, encima, lo encendido
            cv.create_arc(*caja, start=inicio, extent=80, style="arc", outline="#2c313b", width=grosor)
            ext = 80 if self.rotacion == k else (0 if self.rotacion is not None else self.ext[k])
            if ext > 0.5:
                cv.create_arc(*caja, start=inicio, extent=ext, style="arc", outline=self.color, width=grosor)
        ri = d * 0.31
        cv.create_oval(cx - ri, cy - ri, cx + ri, cy + ri, fill="#1b1e24", outline="#2c313b")
        cv.create_image(cx, cy, image=self.logo)
        # Back + R3 (clic aquí = minimizar)
        xb = m + d + round(16 * e)
        xf = g.fila(xb, yo + H / 2, ["Back", "+", "R3"])
        self.zona_min = (xb - round(6 * e), yo, xf + round(4 * e), Ht)
        zona = cv.create_rectangle(self.zona_min[0], yo, self.zona_min[2], Ht, fill="", outline="")
        cv.tag_bind(zona, "<Enter>", lambda ev: cv.config(cursor="hand2"))
        cv.tag_bind(zona, "<Leave>", lambda ev: cv.config(cursor="fleur"))
        cv.tag_raise(zona)

    def dibujar_mando(self, yo):
        """El mando dibujado en la parte desplegada, con el botón que toca rodeado de luz."""
        c = self.cfg
        zona = direccion = None
        hecho = False
        if c and not c["fin"] and c["ap"].paso < len(cfg.PASOS):
            if not (c["blink"] > time.monotonic() and int(time.monotonic() * 8) % 2):
                zona, direccion = cfg.RESALTE[cfg.PASOS[c["ap"].paso][0]]
            hecho = c["ap"].captura is not None
        elif c and c["fin"]:
            hecho = True
        k = self.gm.k
        margen = MARGEN * self.e
        ox = margen / k
        oy = (yo - self.extra + margen) / k + 18
        gm.dibujar_cuerpo(self.cv, self.gm.px, self.gm, ox, oy, zona, direccion, hecho, etiqueta=False)

    def poner(self):
        y = self.pos[1] - (self.Ht - self.H if self.sube else 0)
        self.cv.config(height=self.Ht)
        self.r.geometry("+%d+%d" % (self.pos[0], y))

    # ----- ratón (arrastrar = mover; Back + R3 = minimizar) -----
    def apretar(self, ev):
        z = self.zona_min
        if z[0] <= ev.x <= z[2] and ev.y >= z[1]:
            self.arrastre.clear()
            self.minimizar()
            return
        self.arrastre["d"] = (ev.x_root - self.r.winfo_x(), ev.y_root - self.r.winfo_y())

    def mover(self, ev):
        if "d" in self.arrastre:
            dx, dy = self.arrastre["d"]
            self.pos[:] = [ev.x_root - dx, ev.y_root - dy + (self.Ht - self.H if self.sube else 0)]
            self.poner()

    def soltar(self, ev):
        if self.arrastre.pop("d", None):
            guardar_pos(*self.pos)

    def minimizar(self):
        self.r.withdraw()
        self.raiz.iconify()          # botón "Teclamando" en la barra; su vista previa es la guía
        self.minimizada = True

    def restaurar(self, ev=None):
        if self.raiz.state() == "normal":     # clic en la barra de tareas
            self.raiz.withdraw()
            self.r.deiconify()
            self.poner()
            self.r.attributes("-topmost", True)
            self.minimizada = False

    # ----- animaciones -----
    def animar(self, duracion, cuadro, al_final=None):
        """Llama a cuadro(t) cada ~33 ms durante `duracion` s y luego a al_final()."""
        if self.anim:
            self.raiz.after_cancel(self.anim)
        t0 = time.monotonic()

        def paso():
            t = time.monotonic() - t0
            if t >= duracion:
                self.anim = None
                cuadro(duracion)
                self.dibujar()
                if al_final:
                    al_final()
                return
            cuadro(t)
            self.dibujar()
            self.anim = self.raiz.after(33, paso)
        paso()

    def anillo_llenar(self, t, conservar):
        """Los cuadrantes 2, 3 y 4 se van llenando uno tras otro (1,8 s) y se sostienen un instante."""
        self.color = gm.LUZ
        self.ext = [80] + [80 * suave((t - 0.6 * (k - 1)) / 0.6) for k in (1, 2, 3)]
        if t >= DURACION_ANILLO and not conservar:
            self.ext = [80, 0, 0, 0]

    def encender(self, conservar=False, al_final=None):
        self.animar(DURACION_ANILLO, lambda t: self.anillo_llenar(t, conservar), al_final)

    def apagar(self):
        """Como una Xbox 360 al apagarse: el anillo gira tres veces y se apaga."""
        def cuadro(t):
            self.color = gm.LUZ
            self.rotacion = int(t / (DURACION_ANILLO / 12)) % 4 if t < DURACION_ANILLO else None
            if t >= DURACION_ANILLO:
                self.ext = [0, 0, 0, 0]

        def fin():
            self.raiz.after(250, self.raiz.destroy)
        self.animar(DURACION_ANILLO, cuadro, fin)

    def desplegar(self, abrir, al_final=None):
        if abrir:
            y_min = self.u.GetSystemMetrics(77)
            self.sube = self.pos[1] - self.extra >= y_min        # si no cabe arriba, hacia abajo

        def cuadro(t):
            f = suave(t / DESPLIEGUE)
            self.Ht = self.H + round(self.extra * (f if abrir else 1 - f))
            self.poner()
        self.animar(DESPLIEGUE, cuadro, al_final)

    # ----- configuración rápida del mando -----
    def configurar(self, indice, auto):
        if self.cfg or mg.leer_crudo(indice) is None:
            return
        if self.minimizada:
            self.raiz.withdraw()
            self.r.deiconify()
            self.minimizada = False
        ap = cfg.Aprendiz()
        ap.iniciar(indice)
        self.cfg = {"ap": ap, "auto": auto, "fin": False, "blink": 0.0, "t_paso": time.monotonic(),
                    "paso": 0}
        decir("CONFIG 1")
        self.encender(conservar=True, al_final=lambda: self.desplegar(True, self.empezar_pasos))

    def empezar_pasos(self):
        c = self.cfg
        if not c:
            return
        c["t_paso"] = time.monotonic()
        c["ap"].reposo = mg.leer_crudo(c["ap"].indice) or c["ap"].reposo
        self.progreso()
        self.raiz.after(30, self.vigilar)

    def progreso(self):
        c = self.cfg
        f = c["ap"].paso / len(cfg.PASOS)
        self.color = gm.LUZ
        self.ext = [80 * max(0.0, min(1.0, f * 4 - k)) for k in range(4)]
        self.dibujar()

    def vigilar(self):
        c = self.cfg
        if not c or c["fin"]:
            return
        ap = c["ap"]
        info = mg.leer_crudo(ap.indice)
        if info is None:                                  # se desconectó
            self.terminar_config(False)
            return
        ahora = time.monotonic()
        if ap.avanzar(info):
            self.dibujar()                                # lo detecté: el anillo se vuelve blanco
        if ap.terminado:
            self.terminar_config(True)
            return
        if ap.paso != c["paso"]:                          # pasó al siguiente botón
            c["paso"] = ap.paso
            c["t_paso"] = ahora
            self.progreso()
        elif ap.captura is None and ahora - c["t_paso"] > PACIENCIA:
            if c["auto"] and ap.paso == 0:                # nadie quiere configurarlo: dejarlo
                self.terminar_config(False)
                return
            c["blink"] = ahora + 0.5                      # parpadea: ese botón se salta
            ap.siguiente(None)
            if ap.saltados_seguidos >= 3:
                self.terminar_config(False)               # nadie pulsa nada: se canceló
                return
        elif c["blink"] > ahora:
            self.dibujar()
        self.raiz.after(30, self.vigilar)

    def terminar_config(self, guardar):
        c = self.cfg
        c["fin"] = True
        if guardar:
            try:
                c["ap"].guardar_mapa()
            except OSError:
                guardar = False

        def listo():
            self.cfg = None
            self.ext = [80, 0, 0, 0]
            self.color = gm.LUZ
            self.dibujar()
            decir("CONFIG 0")

        def plegar():
            self.desplegar(False, listo)
        if guardar:
            self.ext = [80, 80, 80, 80]                  # anillo lleno y blanco: guardado
            self.color = "#ffffff"
            self.dibujar()
            self.raiz.after(900, plegar)
        else:
            plegar()

    # ----- órdenes de mando_raton.py -----
    def sondear(self):
        try:
            while True:
                orden = self.cola.get_nowait().split()
                if not orden:
                    continue
                if orden[0] == "APAGAR":
                    self.cfg = None
                    self.apagar()
                elif orden[0] == "CONECTADO" and not self.anim and not self.cfg:
                    self.encender()
                elif orden[0] == "CONFIGURAR" and len(orden) >= 2:
                    try:
                        self.configurar(int(orden[1]), "auto" in orden[2:])
                    except ValueError:
                        pass
        except queue.Empty:
            pass
        self.raiz.after(120, self.sondear)


def main():
    # Una sola copia: varios indicadores superpuestos se roban los clics
    # (si queda uno de un arranque anterior, se cierra solo en ~1 s: esperarlo un poco)
    k = ctypes.WinDLL("kernel32")
    k.CreateMutexW.restype = ctypes.c_void_p
    for _ in range(30):
        m = k.CreateMutexW(None, False, "Local\\TeclamandoIndicador")
        if k.GetLastError() != 183:
            break
        k.CloseHandle(ctypes.c_void_p(m))
        time.sleep(0.1)
    else:
        return
    # raiz = ventana normal, fuera de la pantalla, con la guía dibujada dentro: es la que se minimiza
    # a la barra de tareas, así su vista previa muestra la lista de comandos.
    # Identidad propia en la barra (si no, sale agrupada con el icono de Python)
    try:
        ctypes.WinDLL("shell32").SetCurrentProcessExplicitAppUserModelID(NOMBRE)
    except (AttributeError, OSError):
        pass
    u = ctypes.WinDLL("user32")
    antes = u.GetForegroundWindow()
    raiz = tk.Tk()
    raiz.title(NOMBRE)
    raiz.withdraw()
    try:
        raiz.iconbitmap(default=os.path.join(CARPETA, "icono.ico"))
    except tk.TclError:
        pass
    raiz.geometry("+-8000+-8000")
    vista = VistaPrevia(raiz)
    Mini(raiz, vista, sin_animacion="--sin-animacion" in sys.argv)
    raiz.update()
    hw_raiz = u.GetParent(raiz.winfo_id()) or raiz.winfo_id()

    def poner_icono():
        # Icono de la ventana (barra de tareas y vista previa) directo con la API de Windows:
        # iconbitmap/iconphoto no alcanzan a la ventana real y sale el de Python.
        ruta = os.path.join(CARPETA, "icono.ico")
        u.LoadImageW.restype = ctypes.c_void_p
        u.SendMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_void_p]
        for tipo, lado in ((1, 48), (0, 16)):          # ICON_BIG, ICON_SMALL
            h = u.LoadImageW(None, ruta, 1, lado, lado, 0x10)   # IMAGE_ICON, LR_LOADFROMFILE
            if h:
                u.SendMessageW(hw_raiz, 0x80, tipo, h)        # WM_SETICON

    poner_icono()
    vista.activar(hw_raiz)
    if antes:
        u.SetForegroundWindow(antes)   # Tk se queda el foco al crearse: devolverlo
    seguir_al_padre(raiz)
    raiz.mainloop()


if __name__ == "__main__":
    main()
