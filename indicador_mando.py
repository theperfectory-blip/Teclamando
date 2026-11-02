"""Mini ventana mientras el mando está activo, estilo "anillo de luz": el anillo del mando con el
logo al centro (jugador 1 encendido) y Back + R3 (lo que abre la guía). Sin textos.

Lo lanza mando_raton.py al encender (Back + Start) y lo cierra al pausar.
Ventana siempre encima y sin robar el foco. Tomarla por el anillo y arrastrar = moverla (posición
guardada en indicador_pos.json); clic en Back + R3 = minimizarla a la barra de tareas ("Teclamando");
al pulsarla ahí vuelve a su sitio.
"""
import ctypes
import json
import os
from ctypes import wintypes
import time
import tkinter as tk

import guia_mando as gm
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
    r = tk.Toplevel(raiz)
    r.overrideredirect(True)
    r.attributes("-topmost", True)
    r.configure(bg=CLAVE)
    r.attributes("-transparentcolor", CLAVE)
    r.attributes("-alpha", OPACIDAD)       # vidrio: se ve lo de atrás, como en la PS3
    # Estilo "anillo de luz" (elegido 2026-10-31): el anillo del mando encendido en el cuadrante del
    # jugador 1 con el logo al centro, y Back + R3 grandes. Sin nombre ni textos. Sin botón –:
    # tomar el anillo (el mando) y arrastrar = moverla; clic en Back + R3 = minimizarla.
    e = r.winfo_fpixels("1i") / 96
    W, H = round(ANCHO * e), round(ALTO * e)
    cv = tk.Canvas(r, width=W, height=H, bg=CLAVE, highlightthickness=0, cursor="fleur")
    cv.pack()
    g = Glifos(cv, e, alto=42)
    g.redondo(0, 0, W - 1, H - 1, H / 2, gm.PLACA, gm.BORDE)
    cv.create_line(H / 2, 2, W - H / 2, 2, fill="#2a2e36")
    # el anillo
    m, d = round(8 * e), H - 2 * round(8 * e)
    cx, cy = m + d / 2, H / 2
    cv.create_oval(m, m, m + d, m + d, fill="#121418", outline="")
    a = d * 0.10                                     # el anillo va un poco adentro del borde
    caja = (m + a, m + a, m + d - a, m + d - a)
    grosor = max(4, round(7 * e))
    for inicio in (5, 275, 185):                     # los otros tres cuadrantes, apagados
        cv.create_arc(*caja, start=inicio, extent=80, style="arc", outline="#2c313b", width=grosor)
    cv.create_arc(*caja, start=95, extent=80, style="arc", outline=gm.LUZ, width=grosor)   # jugador 1
    ri = d * 0.31
    cv.create_oval(cx - ri, cy - ri, cx + ri, cy + ri, fill="#1b1e24", outline="#2c313b")
    # el logo (mando que se desvanece en teclado) al centro, achicado a la medida del círculo
    logo = tk.PhotoImage(file=os.path.join(CARPETA, "icono_ancho.png"))     # 84 x 56
    for zoom, sub in ((1, 1), (5, 6), (3, 4), (2, 3), (3, 5), (1, 2)):
        if logo.width() * zoom / sub <= 2 * ri * 0.92:
            break
    if (zoom, sub) != (1, 1):
        logo = logo.zoom(zoom).subsample(sub)
    cv.create_image(cx, cy, image=logo)
    cv.logo = logo
    # Back + R3 (clic aquí = minimizar)
    xb = m + d + round(16 * e)
    xf = g.fila(xb, H / 2, ["Back", "+", "R3"])
    zona_min = (xb - round(6 * e), 0, xf + round(4 * e), H)
    zona = cv.create_rectangle(*zona_min, fill="", outline="")
    cv.tag_bind(zona, "<Enter>", lambda ev: cv.config(cursor="hand2"))
    cv.tag_bind(zona, "<Leave>", lambda ev: cv.config(cursor="fleur"))
    cv.tag_raise(zona)
    pos = list(leer_pos(r, W, H))
    r.geometry("+%d+%d" % tuple(pos))
    arrastre = {}

    def apretar(e):
        if zona_min[0] <= e.x <= zona_min[2]:                   # Back + R3: minimizar
            arrastre.clear()
            minimizar()
            return
        arrastre["d"] = (e.x_root - r.winfo_x(), e.y_root - r.winfo_y())

    def mover(e):
        if "d" in arrastre:
            dx, dy = arrastre["d"]
            pos[:] = [e.x_root - dx, e.y_root - dy]
            r.geometry("+%d+%d" % tuple(pos))

    def soltar(e):
        if arrastre.pop("d", None):
            guardar_pos(*pos)

    def minimizar():
        r.withdraw()
        raiz.iconify()          # botón "Teclamando" en la barra; su vista previa es la guía

    def restaurar(e=None):
        if raiz.state() == "normal":     # clic en la barra de tareas
            raiz.withdraw()
            r.deiconify()
            r.geometry("+%d+%d" % tuple(pos))
            r.attributes("-topmost", True)

    def poner_icono():
        # Icono de la ventana (barra de tareas y vista previa) directo con la API de Windows:
        # iconbitmap/iconphoto no alcanzan a la ventana real y sale el de Python.
        hw = u.GetParent(raiz.winfo_id()) or raiz.winfo_id()
        ruta = os.path.join(CARPETA, "icono.ico")
        u.LoadImageW.restype = ctypes.c_void_p
        u.SendMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_void_p]
        for tipo, lado in ((1, 48), (0, 16)):          # ICON_BIG, ICON_SMALL
            h = u.LoadImageW(None, ruta, 1, lado, lado, 0x10)   # IMAGE_ICON, LR_LOADFROMFILE
            if h:
                u.SendMessageW(hw, 0x80, tipo, h)        # WM_SETICON

    cv.bind("<ButtonPress-1>", apretar)
    cv.bind("<B1-Motion>", mover)
    cv.bind("<ButtonRelease-1>", soltar)
    raiz.bind("<Map>", restaurar)
    r.update()
    u = ctypes.WinDLL("user32")
    hwnd = u.GetParent(r.winfo_id()) or r.winfo_id()
    get = u.GetWindowLongPtrW
    get.restype = ctypes.c_ssize_t
    u.SetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_ssize_t]
    # sin robar el foco y sin botón propio en la barra (el de la barra es el de la raíz)
    u.SetWindowLongPtrW(hwnd, -20, get(hwnd, -20) | 0x08000000 | 0x80)
    raiz.update()
    hw_raiz = u.GetParent(raiz.winfo_id()) or raiz.winfo_id()
    poner_icono()
    vista.activar(hw_raiz)
    if antes:
        u.SetForegroundWindow(antes)   # Tk se queda el foco al crearse: devolverlo
    seguir_al_padre(raiz)
    raiz.mainloop()


if __name__ == "__main__":
    main()
