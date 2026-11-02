"""Enseña a Teclamando los botones de un mando que no es de Xbox (PlayStation, genérico USB...).

Abre una ventana que pide pulsar cada botón y mover cada stick, y guarda lo aprendido en
mando_generico.json (mando_raton.py lo recarga solo en unos segundos). Espacio = saltar un
botón que tu mando no tenga; Esc = salir sin guardar. Los mandos de Xbox no lo necesitan.
"""
import json
import tkinter as tk

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


class Configurador:
    def __init__(self):
        self.raiz = tk.Tk()
        self.raiz.title("Teclamando · configurar mando")
        self.raiz.configure(bg="#13151b")
        self.raiz.attributes("-topmost", True)
        self.titulo = tk.Label(self.raiz, text="", bg="#13151b", fg="#8e95a8", font=("Segoe UI", 11))
        self.titulo.pack(padx=30, pady=(24, 6))
        self.texto = tk.Label(self.raiz, text="Buscando mando…", bg="#13151b", fg="#f2f4f8",
                              font=("Segoe UI Semibold", 18), wraplength=640)
        self.texto.pack(padx=30, pady=10)
        self.pie = tk.Label(self.raiz, text="Espacio = mi mando no tiene ese botón · Esc = salir sin guardar",
                            bg="#13151b", fg="#8e95a8", font=("Segoe UI", 10))
        self.pie.pack(padx=30, pady=(6, 24))
        self.raiz.bind("<space>", lambda e: self.siguiente(None))
        self.raiz.bind("<Escape>", lambda e: self.raiz.destroy())
        self.indice = None
        self.paso = 0
        self.mapa = {"botones": {}, "gatillos": {}, "ejes": {}, "cruceta": {}}
        self.esperando_soltar = True
        self.captura = None
        self.raiz.after(200, self.buscar)

    # ----- mando -----
    def buscar(self):
        for i in range(16):
            if mg.leer_crudo(i) is not None:
                self.indice = i
                self.rangos, nombre = mg.rangos(i)
                self.reposo = mg.leer_crudo(i)   # posición de los ejes sin tocar nada
                self.titulo.configure(text="Mando: %s  ·  no toques nada al empezar" % (nombre or "sin nombre"))
                self.mostrar()
                self.raiz.after(30, self.mirar)
                return
        self.texto.configure(text="No veo ningún mando. Conéctalo (o cambia su modo a PC / DirectInput).")
        self.raiz.after(1000, self.buscar)

    def centro(self, eje):
        a, b = self.rangos[eje]
        return (a + b) / 2

    def rango(self, eje):
        a, b = self.rangos[eje]
        return max(1, b - a)

    def movido(self, info, umbral):
        """Eje que más se alejó de su reposo (fracción del rango), si pasa el umbral."""
        mejor, cuanto = None, umbral
        for e in mg.EJES:
            d = abs(mg.valor_eje(info, e) - mg.valor_eje(self.reposo, e)) / self.rango(e)
            if d > cuanto:
                mejor, cuanto = e, d
        return mejor

    def en_reposo(self, info):
        return (info.dwButtons == self.reposo.dwButtons and mg.pov_a_cruceta(info.dwPOV) == 0
                and self.movido(info, 0.25) is None)

    def mirar(self):
        if self.paso >= len(PASOS):
            return
        info = mg.leer_crudo(self.indice)
        if info is None:
            self.indice = None
            self.texto.configure(text="Se desconectó el mando.")
            self.raiz.after(1000, self.buscar)
            return
        clave = PASOS[self.paso][0]
        if self.esperando_soltar:
            if self.en_reposo(info):
                self.esperando_soltar = False
        elif self.captura is None:
            self.captura = self.detectar(clave, info)
        elif self.en_reposo(info):
            self.siguiente(self.captura)
        elif clave in ("LT", "RT") and "eje" in self.captura:
            # gatillo analógico: guardar hasta dónde llega apretado a fondo
            v = mg.valor_eje(info, self.captura["eje"])
            if abs(v - self.captura["reposo"]) > abs(self.captura["lleno"] - self.captura["reposo"]):
                self.captura["lleno"] = v
        self.raiz.after(30, self.mirar)

    def detectar(self, clave, info):
        nuevos = info.dwButtons & ~self.reposo.dwButtons
        if clave in STICKS:
            e = self.movido(info, 0.4)
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

    # ----- pasos -----
    def siguiente(self, captura):
        if self.indice is None or self.paso >= len(PASOS):
            return
        clave = PASOS[self.paso][0]
        if captura:
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
        self.paso += 1
        # Cruceta como POV (lo normal): las otras tres direcciones ya están
        while (self.paso < len(PASOS) and PASOS[self.paso][0] in CRUCETA
               and self.mapa["cruceta"] == "pov"):
            self.paso += 1
        self.captura = None
        self.esperando_soltar = True
        self.mostrar()

    def mostrar(self):
        if self.paso < len(PASOS):
            self.texto.configure(text="%d/%d  ·  %s" % (self.paso + 1, len(PASOS), PASOS[self.paso][1]))
            return
        if not self.mapa["cruceta"]:
            self.mapa["cruceta"] = "pov"
        with open(mg.ARCHIVO_MAPA, "w", encoding="utf-8") as f:
            json.dump(self.mapa, f, indent=2)
        self.texto.configure(text="¡Listo! Guardado. Teclamando lo usa en unos segundos.")
        self.pie.configure(text="Esta ventana se cierra sola.")
        self.raiz.after(3000, self.raiz.destroy)


def main():
    Configurador().raiz.mainloop()


if __name__ == "__main__":
    main()
