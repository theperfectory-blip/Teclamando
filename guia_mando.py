"""Guía visual de botones del mando-ratón. La abre/cierra mando_raton.py con Back + R3.

Estilo "anillo de luz" (elegido por el usuario el 2026-10-31 entre tres propuestas): el mando
dibujado con una línea desde cada botón hasta lo que hace, teclas con relieve, los botones A B X Y
como domos de color y lo elegido encendido en verde. Pensada para leerse desde el sofá (3-4 m).
Páginas con pestañas: Ratón · Combinaciones · Teclado, y "Ver más" (solo con el extra modo_juego.py y
si el juego está instalado en este PC; su nombre sale recién al abrirla). Todas muestran el mando dibujado; solo
cambian las líneas y lo que dicen. Ventana semitransparente (vidrio, como la PS3).
LB / RB cambian de página (las manda mando_raton.py por stdin) y también se pueden pulsar con A.
Sin animaciones.

Ventana sin bordes, siempre encima y SIN robar el foco, pegada al borde derecho.
Solo tkinter (viene con Python). Si cambias un botón en mando_raton.py, cámbialo aquí también.
"""
import ctypes
import queue
import sys
import threading
import tkinter as tk
from tkinter import font as tkfont

try:
    ctypes.WinDLL("user32").SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
except (AttributeError, OSError):
    pass

# Colores (los mismos del teclado y la mini ventana). Contrastes sobre FONDO: TEXTO 17:1, SUAVE 11:1,
# EXTRA 8:1.
FONDO, PLACA, BORDE, LINEA = "#0f1013", "#1e2127", "#343944", "#5b6170"
TEXTO, SUAVE, EXTRA, OSCURO = "#f1f3f6", "#c9ced8", "#a9b0bd", "#111111"
CARA, SOMBRA, CANTO = "#2f343e", "#181a1f", "#424855"        # teclas con relieve
STICK, STICK_SOMBRA = "#3a3f4b", "#23262d"
LUZ = "#3ff06b"            # lo elegido / encendido (el anillo de luz del mando)
COLOR = {"A": "#4cc75a", "B": "#f0524a", "X": "#4b8ff0", "Y": "#f1c232"}
LETRA = "Bahnschrift"      # viene con Windows 10/11
CLAVE = "#010203"          # color que se vuelve transparente (esquinas redondeadas)
OPACIDAD = 0.88            # ventana semitransparente, estilo vidrio de la PS3 (pedido 2026-10-31)

# Cada página = el mando dibujado con una línea desde cada botón hasta lo que hace (pedido 2026-10-31:
# en todas las páginas, no solo en Ratón). Señal: (botones, qué hace, detalle, botón del mando al que
# apunta). "+" separa combinaciones; flechas sueltas = cruceta en esa dirección. Sticks con su nombre
# de Xbox: LS / RS (L3 / R3 al apretarlos). Ordenadas de arriba abajo para que las líneas no se crucen.
# "abajo" = lo que va en la fila de abajo, sin línea.
RATON = {
    "izq": [(["LT"], "Más lento", "precisión", "LT"),
            (["LB"], "Página anterior", "", "LB"),
            (["LS"], "Mover cursor", "stick izquierdo", "LS"),
            (["Back"], "Favoritos", "al soltar", "Back"),
            (["Cruceta"], "Flechas", "vídeo: ±10 s, volumen", "Cruceta")],
    "der": [(["RT"], "Clic derecho", "", "RT"),
            (["RB"], "Página siguiente", "", "RB"),
            (["Y"], "Menú del navegador", "", "Y"),
            (["B"], "Atrás", "mantén: cerrar pestaña", "B"),
            (["Start"], "Enter", "al soltar", "Start"),
            (["A"], "Clic", "mantén: pestaña nueva", "A"),
            (["RS"], "Desplazar página", "stick derecho", "RS")],
    "abajo": [(["L3"], "apretar LS · teclado en pantalla"), (["R3", "+", "RS"], "zoom"),
              (["X", "+", "Cruceta"], "página arriba / abajo")],
}
COMBINACIONES = {   # Start (pulgar derecho) + mano izquierda · Back (pulgar izquierdo) + mano derecha
    "izq": [(["Start", "+", "LT"], "Bajar volumen", "", "LT"),
            (["Start", "+", "LB"], "Pestaña anterior", "", "LB"),
            (["Start", "+", "L3"], "Ver ventanas", "todas las abiertas", "LS"),
            (["Start", "+", "↑↓"], "Velocidad del cursor", "", "Cruceta"),
            (["Start", "+", "←→"], "Velocidad del scroll", "", "Cruceta")],
    "der": [(["Back", "+", "RT"], "Subir volumen", "", "RT"),
            (["Back", "+", "RB"], "Pestaña siguiente", "", "RB"),
            (["Back", "+", "Y"], "Pantalla completa", "", "Y"),
            (["Back", "+", "B"], "Esc", "", "B"),
            (["Back", "+", "Start"], "Encender / pausar", "", "Start"),
            (["Back", "+", "A"], "Reproducir / pausar", "", "A"),
            (["Back", "+", "R3"], "Esta guía", "", "RS")],
    "abajo": [(["Start"], "y"), (["Back"], "se mantienen mientras pulsas el otro botón")],
}
TECLADO = {
    "izq": [(["LT"], "Números y símbolos", "", "LT"),
            (["LB"], "Cursor ←", "", "LB"),
            (["LS"], "Moverse por las teclas", "", "LS"),
            (["Cruceta"], "Moverse por las teclas", "arriba del todo: palabras", "Cruceta")],
    "der": [(["RT"], "Mayúscula", "2 veces: bloqueo · 3: normal", "RT"),
            (["RB"], "Cursor →", "", "RB"),
            (["Y"], "Espacio", "", "Y"),
            (["X"], "Borrar", "", "X"),
            (["B"], "Cerrar teclado", "", "B"),
            (["Start"], "Enter y cerrar", "", "Start"),
            (["A"], "Escribir", "mantén en una vocal: tilde", "A"),
            (["RS"], "Mover el teclado", "", "RS")],
    "abajo": [(["L3"], "también cierra el teclado")],
}
# Páginas: (pestaña, título dentro de la página o None, señales).
PAGINAS = [
    ("Ratón", None, RATON),
    ("Combinaciones", None, COMBINACIONES),
    ("Teclado", None, TECLADO),
]
try:
    import modo_juego          # extra opcional: pestaña "Ver más"
except ImportError:
    modo_juego = None

# El mando dibujado: coordenadas de diseño, ventana de 1280 x 760.
MANDO_X, MANDO_Y = 390, 222
ANCLAS = {   # punto del mando al que apunta la línea de cada botón
    "LT": (520, 212), "LB": (500, 246), "LS": (515, 340), "Back": (595, 334), "Cruceta": (575, 427),
    "RT": (760, 212), "RB": (780, 246), "Y": (775, 308), "X": (743, 340), "B": (807, 340),
    "A": (775, 372), "Start": (685, 334), "RS": (705, 427),
}
# Contorno del mando de Xbox 360 (curvas cúbicas desde (70, 40)): hombros, empuñaduras y el valle
# de abajo entre ellas. Relativo a MANDO_X, MANDO_Y.
CONTORNO = [((120, 20), (200, 26), (250, 30)), ((300, 26), (380, 20), (430, 40)),
            ((475, 58), (492, 110), (500, 170)), ((508, 240), (506, 300), (478, 330)),
            ((452, 356), (412, 350), (392, 318)), ((370, 284), (350, 262), (320, 258)),
            ((290, 254), (210, 254), (180, 258)), ((150, 262), (130, 284), (108, 318)),
            ((88, 350), (48, 356), (22, 330)), ((-6, 300), (-8, 240), (0, 170)),
            ((8, 110), (25, 58), (70, 40))]
BRILLO = [((120, 20), (200, 26), (250, 30)), ((300, 26), (380, 20), (430, 40)),
          ((458, 50), (474, 76), (482, 104)), ((390, 74), (110, 74), (18, 104)),
          ((26, 76), (42, 50), (70, 40))]


def seguir_al_padre(raiz):
    """Con "--padre <pid>" (lo pasa mando_raton.py): cerrar esta ventana si el programa principal muere,
    para que no se acumulen copias huérfanas del indicador o de la guía."""
    if "--padre" not in sys.argv:
        return
    try:
        pid = int(sys.argv[sys.argv.index("--padre") + 1])
    except (IndexError, ValueError):
        return
    k = ctypes.WinDLL("kernel32")
    k.OpenProcess.restype = ctypes.c_void_p
    proceso = k.OpenProcess(0x00100000, False, pid)   # SYNCHRONIZE
    if not proceso:
        raiz.destroy()
        return

    def mirar():
        if k.WaitForSingleObject(ctypes.c_void_p(proceso), 0) == 0:   # el padre terminó
            raiz.destroy()
        else:
            raiz.after(1000, mirar)
    raiz.after(1000, mirar)


def aclarar(color, t=0.45):
    """El mismo color mezclado con blanco (el brillo de los domos A B X Y)."""
    r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02x%02x%02x" % tuple(round(c + (255 - c) * t) for c in (r, g, b))


def bezier(puntos, pasos=14):
    """Curva cúbica (p0, c1, c2, p1) convertida en puntos, para dibujar el mando con polígonos."""
    (x0, y0), (x1, y1), (x2, y2), (x3, y3) = puntos
    out = []
    for i in range(1, pasos + 1):
        t = i / pasos
        a, b, c, d = (1 - t) ** 3, 3 * t * (1 - t) ** 2, 3 * t * t * (1 - t), t ** 3
        out += [a * x0 + b * x1 + c * x2 + d * x3, a * y0 + b * y1 + c * y2 + d * y3]
    return out


class Glifos:
    """Dibuja los botones del mando con relieve (también lo usa indicador_mando.py): A B X Y = domos
    de color, sticks = círculos con anillo, el resto = teclas con su nombre, cruceta = cruz.
    `k` = píxeles de pantalla por píxel de diseño; `alto` = alto del botón en diseño."""

    def __init__(self, cv, k, alto=34):
        self.cv, self.k, self.h = cv, k, alto
        self.f_letra = tkfont.Font(family=LETRA, size=-round(alto * 0.47 * k), weight="bold")
        self.f_chip = tkfont.Font(family=LETRA, size=-round(alto * 0.42 * k), weight="bold")
        self.f_mas = tkfont.Font(family=LETRA, size=-round(alto * 0.6 * k))

    def px(self, n):
        return n * self.k

    def redondo(self, x1, y1, x2, y2, r, relleno, borde="", ancho=1, guiones=None):
        """Rectángulo redondeado (coordenadas ya en píxeles de pantalla)."""
        r = min(r, (x2 - x1) / 2, (y2 - y1) / 2)
        pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
               x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
        return self.cv.create_polygon(pts, smooth=True, fill=relleno, outline=borde or relleno, width=ancho,
                                      dash=guiones)

    def tecla(self, x1, y1, x2, y2, r, cara=CARA, sombra=SOMBRA, canto=CANTO):
        h = self.px(3)
        self.redondo(x1, y1 + h, x2, y2, r, sombra)
        self.redondo(x1, y1, x2, y2 - h, r, cara)
        if canto:
            self.cv.create_line(x1 + r, y1 + 1, x2 - r, y1 + 1, fill=canto)

    def ancho(self, nombre):
        p, h = self.px, self.px(self.h)
        if nombre in COLOR or nombre in ("LS", "RS", "L3", "R3") or nombre in ("Cruceta", "↑↓", "←→", "↑", "↓", "←", "→"):
            return h
        if nombre == "+":
            return p(18)
        return max(h, self.f_chip.measure(nombre) + p(20))

    def boton(self, x, y, nombre, modificador=False):
        """Dibuja `nombre` con su centro vertical en y, empezando en x. Devuelve la x final."""
        cv, p, h = self.cv, self.px, self.px(self.h)
        if nombre in COLOR:                                  # domo de color con brillo
            cv.create_oval(x, y - h / 2 + p(2), x + h, y + h / 2 + p(2), fill="#000000", outline="")
            cv.create_oval(x, y - h / 2, x + h, y + h / 2, fill=COLOR[nombre], outline="")
            cv.create_oval(x + h * 0.22, y - h * 0.38, x + h * 0.55, y - h * 0.12, fill=aclarar(COLOR[nombre]),
                           outline="")
            cv.create_text(x + h / 2, y + p(1), text=nombre, fill=OSCURO, font=self.f_letra)
            return x + h
        if nombre == "+":
            cv.create_text(x + p(9), y, text="+", fill=EXTRA, font=self.f_mas)
            return x + p(18)
        if nombre in ("Cruceta", "↑↓", "←→", "↑", "↓", "←", "→"):
            return self.cruceta(x, y, nombre)
        if nombre in ("LS", "RS", "L3", "R3"):               # stick: círculo con anillo
            cv.create_oval(x, y - h / 2 + p(3), x + h, y + h / 2 + p(3), fill=STICK_SOMBRA, outline="")
            cv.create_oval(x, y - h / 2, x + h, y + h / 2, fill=STICK, outline="")
            m = h * 0.16
            cv.create_oval(x + m, y - h / 2 + m, x + h - m, y + h / 2 - m, outline="#2a2e36",
                           width=max(1, p(2)), fill=STICK_SOMBRA if nombre in ("L3", "R3") else "")
            cv.create_text(x + h / 2, y, text=nombre, fill=TEXTO, font=self.f_chip)
            return x + h
        # LB RB LT RT Start Back: tecla con el nombre; Start/Back que se mantienen = letra encendida
        w = self.ancho(nombre)
        r = p(11) if nombre in ("LT", "RT") else p(7)
        self.tecla(x, y - h / 2, x + w, y + h / 2, r)
        cv.create_text(x + w / 2, y - p(1), text=nombre, fill=LUZ if modificador else TEXTO, font=self.f_chip)
        return x + w

    def cruceta(self, x, y, nombre):
        """Cruz de la cruceta; los brazos de la dirección indicada van encendidos."""
        cv, p, h = self.cv, self.px, self.px(self.h)
        t = h / 3
        cx, cy = x + h / 2, y
        brazos = {"↑": (cx - t / 2, cy - h / 2, cx + t / 2, cy - t / 2),
                  "↓": (cx - t / 2, cy + t / 2, cx + t / 2, cy + h / 2),
                  "←": (cx - h / 2, cy - t / 2, cx - t / 2, cy + t / 2),
                  "→": (cx + t / 2, cy - t / 2, cx + h / 2, cy + t / 2)}
        activos = set() if nombre == "Cruceta" else set(nombre)
        self.redondo(cx - t / 2, cy - h / 2 + p(2), cx + t / 2, cy + h / 2 + p(2), p(3), SOMBRA)
        self.redondo(cx - h / 2, cy - t / 2 + p(2), cx + h / 2, cy + t / 2 + p(2), p(3), SOMBRA)
        cv.create_rectangle(cx - t / 2, cy - t / 2, cx + t / 2, cy + t / 2, fill=STICK, outline="")
        for d, caja in brazos.items():
            self.redondo(*caja, p(3), LUZ if d in activos else STICK)
        return x + h

    def fila(self, x, y, botones):
        """Dibuja una combinación entera. Start/Back delante de "+" = se mantienen (letra encendida)."""
        modificador = len(botones) > 1 and botones[0] in ("Start", "Back") and botones[1] == "+"
        for i, b in enumerate(botones):
            x = self.boton(x, y, b, modificador and i == 0) + self.px(8)
        return x

    def ancho_fila(self, botones):
        return sum(self.ancho(b) + self.px(8) for b in botones) - self.px(8)


class Guia:
    ANCHO, ALTO = 1280, 760          # medidas de diseño; se escalan para que quepa en la pantalla

    def __init__(self, contenedor=None):
        """Sin contenedor: ventana flotante propia. Con contenedor: solo dibuja la primera página
        (lo usa indicador_mando.py para la vista previa de la barra de tareas)."""
        self.antes = ctypes.WinDLL("user32").GetForegroundWindow()
        self.raiz = contenedor or tk.Tk()
        r = self.raiz
        r.configure(bg=FONDO)
        if contenedor is None:
            r.overrideredirect(True)
            r.attributes("-topmost", True)
            r.configure(bg=CLAVE)
            r.attributes("-transparentcolor", CLAVE)
            r.attributes("-alpha", OPACIDAD)
        # escala: la de la pantalla (ppp), pero sin pasar el 92 % del ancho / alto útil
        e = r.winfo_fpixels("1i") / 96
        if contenedor is None:
            sw, sh = r.winfo_screenwidth(), r.winfo_screenheight() - round(48 * e)
            self.k = min(e, 0.92 * sw / self.ANCHO, 0.92 * sh / self.ALTO)
        else:
            self.k = 1.0
        k = self.k
        f = lambda tam, peso="normal": tkfont.Font(family=LETRA, size=-round(tam * k), weight=peso)
        self.f_titulo, self.f_pestana = f(28, "bold"), f(19)
        self.f_txt, self.f_extra, self.f_sub, self.f_pagina = f(21), f(15), f(17), f(18)
        self.contenedor = contenedor
        # Modo juego: pestaña "Ver más" solo si el juego está en este PC ("--juego" = abrirla ahí,
        # porque el juego está al frente)
        self.paginas = list(PAGINAS)
        if contenedor is None and modo_juego and modo_juego.juego_instalado():
            self.paginas.append(modo_juego.PAGINA_JUEGO)
        self.actual = len(self.paginas) - 1 if "--juego" in sys.argv and len(self.paginas) > 3 else 0
        self.cv = tk.Canvas(r, bg=FONDO if contenedor else CLAVE, highlightthickness=0, width=round(self.ANCHO * k),
                            height=round(self.ALTO * k))
        self.cv.pack()
        self.cv.bind("<Button-1>", self._clic)
        self.glifos = Glifos(self.cv, k)
        self.chico = Glifos(self.cv, k, alto=28)
        self.pestanas = []               # (x1, y1, x2, y2, índice) para los clics
        self.dibujar()
        if contenedor is not None:
            return
        sw, sh = r.winfo_screenwidth(), r.winfo_screenheight()
        w, h = round(self.ANCHO * k), round(self.ALTO * k)
        r.geometry("%dx%d+%d+%d" % (w, h, sw - w - round(16 * k), max(round(10 * k), (sh - h) // 2 - round(20 * k))))
        r.update()
        self.sin_foco()
        self._ordenes = queue.Queue()
        threading.Thread(target=self._leer_stdin, daemon=True).start()
        r.after(50, self._atender)

    def px(self, n):
        return n * self.k

    # ----- órdenes de mando_raton.py (LB / RB) -----
    def _leer_stdin(self):
        try:
            for linea in sys.stdin:
                self._ordenes.put(linea.strip())
        except (OSError, ValueError):
            pass

    def _atender(self):
        try:
            while True:
                orden = self._ordenes.get_nowait().split()
                if orden and orden[0] == "PESTANA" and len(orden) == 2:
                    self.ir(self.actual + int(orden[1]))
        except (queue.Empty, ValueError):
            pass
        self.raiz.after(50, self._atender)

    def ir(self, i):
        self.actual = i % len(self.paginas)
        self.dibujar()

    def _clic(self, ev):
        for x1, y1, x2, y2, i in self.pestanas:
            if x1 <= ev.x <= x2 and y1 <= ev.y <= y2:
                self.ir(i)
                return

    # ----- dibujo -----
    def dibujar(self):
        cv, p, g = self.cv, self.px, self.glifos
        cv.delete("all")
        W, H = p(self.ANCHO), p(self.ALTO)
        g.redondo(0, 0, W - 1, H - 1, p(22), FONDO, BORDE)

        # encabezado: nombre, pestañas entre LB y RB, y cómo se cierra
        y = p(52)
        cv.create_text(p(40), y, text="Teclamando", anchor="w", fill=TEXTO, font=self.f_titulo)
        x = p(40) + self.f_titulo.measure("Teclamando") + p(26)
        x = self.chico.boton(x, y, "LB") + p(10)
        self.pestanas = []
        for i, (nombre, _, _) in enumerate(self.paginas):
            w = self.f_pestana.measure(nombre) + p(44)
            y1, y2 = y - p(22), y + p(22)
            if i == self.actual:
                g.redondo(x, y1, x + w, y2, p(22), PLACA, LUZ, max(2, p(2)))
                color = LUZ
            elif modo_juego and nombre == modo_juego.PAGINA_JUEGO[0]:
                g.redondo(x, y1, x + w, y2, p(22), FONDO, "#4a505d", max(1, p(1.5)), (4, 3))
                color = SUAVE
            else:
                g.redondo(x, y1, x + w, y2, p(22), "#1a1d22", BORDE)
                color = SUAVE
            cv.create_text(x + w / 2, y, text=nombre, fill=color, font=self.f_pestana)
            self.pestanas.append((x, y1, x + w, y2, i))
            x += w + p(10)
        self.chico.boton(x, y, "RB")
        x = W - p(40) - self.f_extra.measure("cerrar") - p(8) - self.chico.ancho_fila(["Back", "+", "R3"])
        x = self.chico.fila(x, y, ["Back", "+", "R3"])
        cv.create_text(x, y, text="cerrar", anchor="w", fill=SUAVE, font=self.f_extra)

        _, titulo, senales = self.paginas[self.actual]
        if titulo:
            nombre, _, resto = titulo.partition(" · ")
            yt = p(116)
            cv.create_text(p(40), yt, text=nombre, anchor="w", fill=TEXTO, font=self.f_sub)
            cv.create_text(p(40) + self.f_sub.measure(nombre) + p(12), yt, text=resto, anchor="w",
                           fill=EXTRA, font=self.f_extra)
        self.dibujar_mando(senales)

    def dibujar_mando(self, senales):
        """El mando dibujado y una línea desde cada botón hasta lo que hace en esta página."""
        cv, p, g = self.cv, self.px, self.glifos
        ox, oy = MANDO_X, MANDO_Y

        def pt(x, y):
            return p(ox + x), p(oy + y)

        def caja(x1, y1, x2, y2, r, relleno, borde=""):
            a, b = pt(x1, y1)
            c, d = pt(x2, y2)
            g.redondo(a, b, c, d, p(r), relleno, borde)

        def circulo(cx, cy, r, relleno, borde="", ancho=1):
            a, b = pt(cx - r, cy - r)
            c, d = pt(cx + r, cy + r)
            cv.create_oval(a, b, c, d, fill=relleno, outline=borde, width=ancho)

        def curva(inicio, tramos, dx=0, dy=0):
            puntos = [inicio]
            for tramo in tramos:
                b = bezier([puntos[-1]] + list(tramo))
                puntos += [(b[i], b[i + 1]) for i in range(0, len(b), 2)]
            return [c for x, y in puntos for c in pt(x + dx, y + dy)]

        def poligono(puntos, relleno, borde="", ancho=1, suave=True):
            cv.create_polygon([c for x, y in puntos for c in pt(x, y)], fill=relleno, outline=borde,
                              width=ancho, smooth=suave)

        def stick(cx, cy):
            circulo(cx, cy, 34, "#c4c8cf")                       # hueco en la carcasa
            circulo(cx, cy + 2, 29, "#15171b")                   # sombra del capuchón
            circulo(cx, cy, 29, "#2b2e35", "#454a54", max(1, p(3)))   # capuchón con su anillo de goma
            circulo(cx, cy, 17, "#23262c")                       # centro cóncavo
            a, b = pt(cx - 25, cy - 25)
            c, d = pt(cx + 25, cy + 25)
            cv.create_arc(a, b, c, d, start=100, extent=70, style="arc", outline="#5d6370", width=max(1, p(2)))

        # gatillos detrás y bumpers curvos sobre los hombros
        caja(95, -14, 165, 24, 14, "#3a3e46", "#4a4f59")
        caja(335, -14, 405, 24, 14, "#3a3e46", "#4a4f59")
        poligono([(58, 46), (66, 30), (96, 18), (150, 12), (196, 14), (204, 26), (198, 32), (150, 28),
                  (100, 34), (72, 46)], "#8d939d", "#a6abb4")
        poligono([(442, 46), (434, 30), (404, 18), (350, 12), (304, 14), (296, 26), (302, 32), (350, 28),
                  (400, 34), (428, 46)], "#8d939d", "#a6abb4")
        # sombra, cuerpo blanco y brillo de arriba
        cv.create_polygon(curva((70, 40), CONTORNO, 0, 9), fill="#07080a", outline="")
        cv.create_polygon(curva((70, 40), CONTORNO), fill="#eceef1", outline="#c9cdd4", width=max(1, p(1.5)))
        cv.create_polygon(curva((70, 40), BRILLO), fill="#f8f9fa", outline="")
        # empuñaduras un poco más oscuras abajo
        poligono([(30, 250), (60, 236), (100, 262), (104, 312), (70, 336), (30, 320), (16, 286)], "#e2e5e9",
                 suave=True)
        poligono([(470, 250), (440, 236), (400, 262), (396, 312), (430, 336), (470, 320), (484, 286)], "#e2e5e9",
                 suave=True)
        # sticks y cruceta sobre su disco
        stick(125, 118)
        stick(315, 205)
        circulo(185, 205, 33, "#c4c8cf")
        circulo(185, 207, 28, "#15171b")
        circulo(185, 205, 28, "#3a3e46", "#4c515b", max(1, p(2)))
        caja(177, 182, 193, 228, 4, "#2b2e35")
        caja(162, 197, 208, 213, 4, "#2b2e35")
        for x1, y1, x2, y2, x3, y3 in ((185, 186, 181, 191, 189, 191), (185, 224, 181, 219, 189, 219),
                                       (166, 205, 171, 201, 171, 209), (204, 205, 199, 201, 199, 209)):
            cv.create_polygon(*pt(x1, y1), *pt(x2, y2), *pt(x3, y3), fill="#6b717d", outline="")
        # Back y Start: redondos, con su flecha, a los lados del botón guía
        for cx, flecha in ((205, -1), (295, 1)):
            circulo(cx, 112, 11, "#c4c8cf")
            circulo(cx, 112, 9, "#9aa0aa", "#80868f")
            cv.create_polygon(*pt(cx - 4 * flecha, 108), *pt(cx - 4 * flecha, 116), *pt(cx + 4 * flecha, 112),
                              fill="#2b2e35", outline="")
        # botón guía plateado con el anillo de luz (cuadrante del jugador 1 encendido)
        circulo(250, 94, 27, "#c4c8cf")
        a, b = pt(227, 71)
        c, d = pt(273, 117)
        for inicio, color in ((5, "#8a909a"), (95, LUZ), (185, "#8a909a"), (275, "#8a909a")):
            cv.create_arc(a, b, c, d, start=inicio, extent=80, style="arc", outline=color, width=max(2, p(4)))
        circulo(250, 94, 17, "#d9dde3", "#aeb3bc", max(1, p(1.5)))
        circulo(246, 90, 7, "#eef0f3")
        # A B X Y: botones de color en su hueco, con brillo
        for letra, (cx, cy) in {"Y": (385, 86), "X": (353, 118), "B": (417, 118), "A": (385, 150)}.items():
            circulo(cx, cy, 17, "#c4c8cf")
            circulo(cx, cy + 1.5, 14.5, "#15171b")
            circulo(cx, cy, 14.5, COLOR[letra])
            a, b = pt(cx - 9, cy - 11)
            c, d = pt(cx + 3, cy - 4)
            cv.create_oval(a, b, c, d, fill=aclarar(COLOR[letra], 0.5), outline="")
            cv.create_text(*pt(cx, cy + 1), text=letra, fill=OSCURO, font=g.f_letra)

        # líneas y etiquetas, repartidas de arriba abajo a cada lado
        for lado in ("izq", "der"):
            lista = senales[lado]
            paso = min(70, (590 - 166) / max(1, len(lista) - 1))
            for n, (botones, texto, extra, destino) in enumerate(lista):
                y = 166 + n * paso
                ax, ay = ANCLAS[destino]
                inicio, codo = (352, 470) if lado == "izq" else (928, 810)
                cv.create_line(p(inicio), p(y), p(codo), p(y), p(ax), p(ay), fill=LINEA, width=max(1, p(1.5)))
                cv.create_oval(p(ax - 4), p(ay - 4), p(ax + 4), p(ay + 4), fill=LUZ, outline="")
                w = g.ancho_fila(botones)
                if lado == "izq":
                    gx = p(344) - w
                    g.fila(gx, p(y), botones)
                    tx, ancla = gx - p(12), "e"
                else:
                    gx = p(936)
                    g.fila(gx, p(y), botones)
                    tx, ancla = gx + w + p(12), "w"
                cv.create_text(tx, p(y - (9 if extra else 0)), text=texto, anchor=ancla, fill=TEXTO,
                               font=self.f_txt)
                if extra:
                    cv.create_text(tx, p(y + 15), text=extra, anchor=ancla, fill=EXTRA, font=self.f_extra)

        # abajo: lo que no tiene una línea propia
        chico = self.chico
        piezas = senales.get("abajo", [])
        total = sum(chico.ancho_fila(b) + p(10) + self.f_extra.measure(t) for b, t in piezas) + p(40) * (len(piezas) - 1)
        x = (p(self.ANCHO) - total) / 2
        y = p(self.ALTO - 48)
        for botones, texto in piezas:
            x = chico.fila(x, y, botones) + p(2)
            cv.create_text(x, y, text=texto, anchor="w", fill=SUAVE, font=self.f_extra)
            x += self.f_extra.measure(texto) + p(40)

    def sin_foco(self):
        """Que la ventana nunca tome el foco (sigue escribiendo en lo que estabas)."""
        u = ctypes.WinDLL("user32")
        hwnd = u.GetParent(self.raiz.winfo_id()) or self.raiz.winfo_id()
        GWL_EXSTYLE, NOACTIVATE, TOOLWINDOW = -20, 0x08000000, 0x00000080
        get = u.GetWindowLongPtrW
        get.restype = ctypes.c_ssize_t
        stilo = get(hwnd, GWL_EXSTYLE)
        u.SetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_ssize_t]
        u.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, stilo | NOACTIVATE | TOOLWINDOW)
        if self.antes:
            u.SetForegroundWindow(self.antes)   # Tk se queda el foco al crearse: devolverlo


def main():
    g = Guia()
    seguir_al_padre(g.raiz)
    g.raiz.mainloop()


if __name__ == "__main__":
    main()
