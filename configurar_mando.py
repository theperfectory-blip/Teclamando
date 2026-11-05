"""Enseña a Teclamando los botones de un mando que no es de Xbox (PlayStation, genérico USB...).

Abre una ventana con el mando dibujado: te pide pulsar cada botón (el que toca va rodeado de luz) y
mover cada stick. Al terminar, Enter guarda lo aprendido en mando_generico.json (mando_raton.py lo
recarga solo en unos segundos). Espacio = saltar un botón que tu mando no tenga; Retroceso = volver
un paso (si te equivocaste); Esc = salir sin guardar. Los mandos de Xbox no lo necesitan.
"""
import tkinter as tk
from tkinter import font as tkfont

import guia_mando as gm
import mando_generico as mg

PASOS = [   # (clave, texto). Nombres de Xbox y, entre paréntesis, los de PlayStation
    ("A", "Pulsa A  (abajo de los 4 botones; PlayStation: ✕)"),
    ("B", "Pulsa B  (derecha; PlayStation: ○)"),
    ("X", "Pulsa X  (izquierda; PlayStation: □)"),
    ("Y", "Pulsa Y  (arriba; PlayStation: △)"),
    ("LB", "Pulsa LB  (botón de arriba izquierdo; PlayStation: L1)"),
    ("RB", "Pulsa RB  (botón de arriba derecho; PlayStation: R1)"),
    ("LT", "Aprieta LT  (gatillo izquierdo; PlayStation: L2)"),
    ("RT", "Aprieta RT  (gatillo derecho; PlayStation: R2)"),
    ("BACK", "Pulsa Back  (botón chico izquierdo; PlayStation: Share / Create)"),
    ("START", "Pulsa Start  (botón chico derecho; PlayStation: Options)"),
    ("L3", "Hunde el stick izquierdo (L3)"),
    ("R3", "Hunde el stick derecho (R3)"),
    ("ARRIBA", "Pulsa la cruceta hacia ARRIBA"),
    ("ABAJO", "Pulsa la cruceta hacia ABAJO"),
    ("IZQUIERDA", "Pulsa la cruceta hacia la IZQUIERDA"),
    ("DERECHA", "Pulsa la cruceta hacia la DERECHA"),
    ("LX", "Mueve el stick IZQUIERDO hacia la DERECHA"),
    ("LY", "Mueve el stick IZQUIERDO hacia ARRIBA"),
    ("RX", "Mueve el stick DERECHO hacia la DERECHA"),
    ("RY", "Mueve el stick DERECHO hacia ARRIBA"),
]
STICKS = ("LX", "LY", "RX", "RY")
CRUCETA = ("ARRIBA", "ABAJO", "IZQUIERDA", "DERECHA")
# Qué se resalta en el dibujo en cada paso: (zona del mando, flecha de la dirección del stick)
RESALTE = {c: (c, None) for c, _ in PASOS}
RESALTE.update({"LX": ("LS", (1, 0)), "LY": ("LS", (0, -1)), "RX": ("RS", (1, 0)), "RY": ("RS", (0, -1))})

ANCHO, ALTO = 600, 670       # medidas de diseño; se escalan con la pantalla
MANDO = (46, 104)            # esquina del mando dentro de la ventana, en diseño


class Aprendiz:
    """La lógica de aprender un mando, sin ventana (la usan el configurador y la mini ventana):
    qué paso toca, qué se detectó, volver atrás y el mapa resultante. Quien la usa llama a `avanzar`
    cada ~30 ms con la lectura cruda del mando."""

    def iniciar(self, indice):
        self.indice = indice
        self.rangos, self.nombre = mg.rangos(indice)
        self.modelo = mg.modelo(indice)
        self.reposo = mg.leer_crudo(indice)      # posición de los ejes sin tocar nada
        self.paso = 0
        self.mapa = {"botones": {}, "gatillos": {}, "ejes": {}, "cruceta": {}}
        self.esperando_soltar = True
        self.captura = None
        self.terminado = False
        self.saltados_seguidos = 0              # pasos saltados uno tras otro (nadie pulsa nada)

    def centro(self, eje):
        a, b = self.rangos[eje]
        return (a + b) / 2

    def rango(self, eje):
        a, b = self.rangos[eje]
        return max(1, b - a)

    def movido(self, info, umbral, excluir=()):
        """Eje que más se alejó de su reposo (fracción del rango), si pasa el umbral."""
        mejor, cuanto = None, umbral
        for e in mg.EJES:
            if e in excluir:
                continue
            d = abs(mg.valor_eje(info, e) - mg.valor_eje(self.reposo, e)) / self.rango(e)
            if d > cuanto:
                mejor, cuanto = e, d
        return mejor

    def en_reposo(self, info):
        return (info.dwButtons == self.reposo.dwButtons and mg.pov_a_cruceta(info.dwPOV) == 0
                and self.movido(info, 0.25) is None)

    def avanzar(self, info):
        """Un vistazo al mando. Devuelve True si el estado visible cambió (se detectó el botón)."""
        if self.terminado or self.paso >= len(PASOS):
            return False
        clave = PASOS[self.paso][0]
        if self.esperando_soltar:
            if self.en_reposo(info):
                self.esperando_soltar = False
        elif self.captura is None:
            self.captura = self.detectar(clave, info)
            if self.captura is not None:
                return True                     # el anillo se vuelve blanco: lo detecté
        elif self.en_reposo(info):
            self.siguiente(self.captura)
        elif clave in ("LT", "RT") and "eje" in self.captura:
            # gatillo analógico: guardar hasta dónde llega apretado a fondo
            v = mg.valor_eje(info, self.captura["eje"])
            if abs(v - self.captura["reposo"]) > abs(self.captura["lleno"] - self.captura["reposo"]):
                self.captura["lleno"] = v
        return False

    def detectar(self, clave, info):
        nuevos = info.dwButtons & ~self.reposo.dwButtons
        if clave in STICKS:
            # no repetir un eje que ya es de otro stick (se pulsó el mismo stick dos veces)
            usados = {v["eje"] for v in self.mapa["ejes"].values()}
            e = self.movido(info, 0.4, usados)
            if e:
                return {"eje": e, "signo": 1 if mg.valor_eje(info, e) > self.centro(e) else -1}
            return None
        if clave in CRUCETA and mg.pov_a_cruceta(info.dwPOV):
            return {"pov": True}
        if nuevos:
            return {"boton": (nuevos & -nuevos).bit_length()}
        if clave in ("LT", "RT"):
            e = self.movido(info, 0.4)
            if e:
                return {"eje": e, "reposo": mg.valor_eje(self.reposo, e), "lleno": mg.valor_eje(info, e)}
        return None

    def siguiente(self, captura):
        if self.indice is None or self.paso >= len(PASOS):
            return
        clave = PASOS[self.paso][0]
        if captura:
            self.saltados_seguidos = 0
            if clave in STICKS:
                self.mapa["ejes"][clave] = captura
            elif clave in ("LT", "RT"):
                self.mapa["gatillos"][clave] = captura
            elif clave in CRUCETA:
                if "pov" in captura:
                    self.mapa["cruceta"] = "pov"
                elif isinstance(self.mapa["cruceta"], dict):
                    self.mapa["cruceta"][clave] = captura["boton"]
            else:
                self.mapa["botones"][clave] = captura["boton"]
        else:
            self.saltados_seguidos += 1
        self.paso += 1
        # Cruceta como POV (lo normal): las otras tres direcciones ya están
        while (self.paso < len(PASOS) and PASOS[self.paso][0] in CRUCETA
               and self.mapa["cruceta"] == "pov"):
            self.paso += 1
        self.captura = None
        self.esperando_soltar = True
        self.mostrar()

    def atras(self):
        """Volver un paso (por si te equivocaste) y olvidar lo que se había aprendido en ese."""
        if self.paso == 0 or self.indice is None:
            return
        self.terminado = False
        self.paso -= 1
        clave = PASOS[self.paso][0]
        if clave in CRUCETA:               # la cruceta se rehace entera, desde ARRIBA
            self.paso = [c for c, _ in PASOS].index("ARRIBA")
            self.mapa["cruceta"] = {}
        else:
            for grupo in ("botones", "gatillos", "ejes"):
                self.mapa[grupo].pop(clave, None)
        self.captura = None
        self.esperando_soltar = True
        self.mostrar()

    def mostrar(self):
        """Gancho: cambió el paso. Con todos los pasos hechos queda `terminado`."""
        if self.paso >= len(PASOS):
            self.terminado = True

    def guardar_mapa(self):
        if not self.mapa["cruceta"]:
            self.mapa["cruceta"] = "pov"
        mg.guardar_mapa(self.modelo, self.mapa)


class Configurador(Aprendiz):
    def __init__(self):
        self.raiz = tk.Tk()
        self.raiz.title("Teclamando · configurar mando")
        self.raiz.configure(bg=gm.FONDO)
        self.raiz.attributes("-topmost", True)
        e = self.raiz.winfo_fpixels("1i") / 96
        self.k = min(e, 0.92 * self.raiz.winfo_screenwidth() / ANCHO,
                     0.9 * (self.raiz.winfo_screenheight() - 60 * e) / ALTO)
        k = self.k
        f = lambda tam, peso="normal": tkfont.Font(family=gm.LETRA, size=-round(tam * k), weight=peso)
        self.f_titulo, self.f_texto, self.f_pie, self.f_chico = f(22, "bold"), f(19), f(13), f(15)
        self.cv = tk.Canvas(self.raiz, bg=gm.FONDO, highlightthickness=0, width=round(ANCHO * k),
                            height=round(ALTO * k))
        self.cv.pack()
        self.glifos = gm.Glifos(self.cv, k)
        self.raiz.bind("<space>", lambda ev: self.siguiente(None))
        self.raiz.bind("<BackSpace>", lambda ev: (self.atras(), self.programar()))
        self.raiz.bind("<Return>", lambda ev: self.guardar())
        self.raiz.bind("<Escape>", lambda ev: self.raiz.destroy())
        self.indice = None
        self.nombre = ""
        self.paso = 0
        self.mapa = {"botones": {}, "gatillos": {}, "ejes": {}, "cruceta": {}}
        self.esperando_soltar = True
        self.captura = None
        self.terminado = False
        self.mensaje = "Buscando mando…"
        self.vigilando = False
        self.dibujar()
        self.raiz.after(200, self.buscar)

    # ----- dibujo -----
    def dibujar(self):
        cv, g, k = self.cv, self.glifos, self.k
        p = g.px
        cv.delete("all")
        cv.create_text(p(30), p(36), text="Configurar mando", anchor="w", fill=gm.TEXTO, font=self.f_titulo)
        if self.indice is not None:
            cv.create_text(p(ANCHO - 30), p(36), text=self.nombre or "mando sin nombre", anchor="e",
                           fill=gm.EXTRA, font=self.f_chico)
            cv.create_text(p(30), p(62), text="No toques nada al empezar", anchor="w", fill=gm.EXTRA,
                           font=self.f_pie)
        zona, direccion = (None, None)
        if self.indice is not None and self.paso < len(PASOS):
            zona, direccion = RESALTE[PASOS[self.paso][0]]
        gm.dibujar_cuerpo(cv, p, g, MANDO[0], MANDO[1], zona, direccion, hecho=self.captura is not None)
        if self.indice is not None and self.paso < len(PASOS):
            # barra de avance
            x1, x2, y = p(30), p(ANCHO - 30), p(MANDO[1] + 372)
            cv.create_line(x1, y, x2, y, fill=gm.BORDE, width=max(2, p(4)))
            cv.create_line(x1, y, x1 + (x2 - x1) * self.paso / len(PASOS), y, fill=gm.LUZ, width=max(2, p(4)))
            cv.create_text(x2, y - p(14), text="%d / %d" % (self.paso + 1, len(PASOS)), anchor="e",
                           fill=gm.EXTRA, font=self.f_pie)
            texto = PASOS[self.paso][1]
        else:
            texto = self.mensaje
        cv.create_text(p(ANCHO / 2), p(MANDO[1] + 440), text=texto, fill=gm.TEXTO, font=self.f_texto,
                       width=p(ANCHO - 70), justify="center")
        cv.create_text(p(ANCHO / 2), p(ALTO - 30), fill=gm.EXTRA, font=self.f_pie, justify="center",
                       text="Espacio = mi mando no tiene ese botón  ·  Retroceso = volver un paso  ·  Esc = salir")

    # ----- mando -----
    def programar(self):
        if not self.vigilando:
            self.vigilando = True
            self.raiz.after(30, self.mirar)

    def buscar(self):
        for i in range(16):
            if mg.leer_crudo(i) is not None:
                self.iniciar(i)
                self.dibujar()
                self.programar()
                return
        self.mensaje = "No veo ningún mando. Conéctalo (o cambia su modo a PC / DirectInput)."
        self.dibujar()
        self.raiz.after(1000, self.buscar)

    def mirar(self):
        self.vigilando = False
        if self.terminado or self.paso >= len(PASOS):
            return
        info = mg.leer_crudo(self.indice) if self.indice is not None else None
        if info is None:
            self.indice = None
            self.mensaje = "Se desconectó el mando."
            self.dibujar()
            self.raiz.after(1000, self.buscar)
            return
        if self.avanzar(info):
            self.dibujar()                  # el anillo se vuelve blanco: lo detecté
        self.programar()

    def mostrar(self):
        super().mostrar()
        if self.terminado:
            self.mensaje = "Listo. Enter = guardar  ·  Retroceso = corregir el último"
        self.dibujar()

    def guardar(self):
        if not self.terminado:
            return
        self.guardar_mapa()
        self.terminado = False
        self.paso = len(PASOS)
        self.mensaje = "¡Guardado! Teclamando lo usa en unos segundos."
        self.dibujar()
        self.raiz.after(2500, self.raiz.destroy)


def main():
    Configurador().raiz.mainloop()


if __name__ == "__main__":
    main()
