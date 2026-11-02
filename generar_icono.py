"""Genera los iconos del mando-ratón: un mando Xbox 360 que se va armando en teclas de teclado.

La mitad izquierda es el mando (stick, cruceta, botón guía); a partir del centro el cuerpo
se parte en teclas, los botones A B X Y pasan a ser teclas de color y algunas teclas se sueltan.
  icono.png / icono.ico   cuadrado oscuro (barra de tareas)
  icono_ancho.png         solo el dibujo, para el indicador en pantalla
Ejecutar tras cambiar el dibujo:  python generar_icono.py   (requiere Pillow)
"""
import os
from PIL import Image, ImageDraw, ImageChops

CARPETA = os.path.dirname(os.path.abspath(__file__))
CUERPO, BORDE_TECLA = (236, 239, 244), (178, 185, 200)
DETALLE, OSCURO = (150, 158, 176), (22, 25, 33)
VERDE, ROJO, AZUL, AMARILLO = (16, 185, 64), (232, 64, 56), (40, 120, 240), (245, 186, 30)
E = 8                 # supermuestreo
BW, BH = 150, 100     # lienzo base del dibujo
CORTE = 72            # x donde empieza a partirse en teclas
CELDA = 15


def silueta(k):
    m = Image.new("L", (int(BW * k), int(BH * k)), 0)
    d = ImageDraw.Draw(m)
    P = lambda *v: [x * k for x in v]
    d.ellipse(P(4, 30, 60, 94), fill=255)                     # asa izquierda
    d.ellipse(P(80, 30, 136, 94), fill=255)                   # asa derecha
    d.rounded_rectangle(P(10, 10, 130, 66), radius=27 * k, fill=255)
    d.ellipse(P(47, 60, 93, 104), fill=0)                     # hueco entre asas
    return m


def dibujo(k):
    """Dibujo del mando-teclado a escala k (píxeles por unidad base)."""
    W, H = int(BW * k), int(BH * k)
    P = lambda *v: [x * k for x in v]
    m = silueta(k)
    out = Image.new("RGBA", (W, H), CUERPO + (0,))
    d = ImageDraw.Draw(out)

    # 1) parte sólida: el mando hasta el corte
    solido = Image.new("L", (W, H), 0)
    ImageDraw.Draw(solido).rectangle(P(0, 0, CORTE, BH), fill=255)
    solido = ImageChops.multiply(solido, m)
    out.paste(Image.new("RGBA", (W, H), CUERPO + (255,)), (0, 0), solido)
    d.ellipse(P(21, 22, 47, 48), fill=BORDE_TECLA)            # stick izquierdo
    d.ellipse(P(25, 26, 43, 44), fill=DETALLE)
    d.rounded_rectangle(P(45, 46, 52, 66), radius=1.5 * k, fill=DETALLE)   # cruceta
    d.rounded_rectangle(P(38.5, 52.5, 58.5, 59.5), radius=1.5 * k, fill=DETALLE)
    d.ellipse(P(58, 14, 78, 34), fill=(255, 255, 255))        # botón guía
    d.ellipse(P(61, 17, 75, 31), fill=VERDE)

    # 2) a partir del corte, el cuerpo se parte en teclas
    colores = {(1, 2): AMARILLO, (2, 1): AZUL, (2, 3): ROJO, (3, 2): VERDE}   # Y X B A en rombo
    for fila in range(7):
        for col in range(5):
            x0 = CORTE + 2 + col * CELDA
            y0 = 8 + fila * CELDA
            hueco = (1.4, 2.6, 3.2)[min(col, 2)]           # las primeras teclas casi pegadas
            caja = (x0 + hueco / 2, y0 + hueco / 2, x0 + CELDA - hueco / 2, y0 + CELDA - hueco / 2)
            # solo las teclas que caen dentro de la silueta
            rec = m.crop(tuple(int(v * k) for v in caja))
            cobertura = sum(rec.get_flattened_data()) / (255 * max(1, rec.width * rec.height))
            if cobertura < 0.75:
                continue
            tecla(d, caja, k, colores.get((fila, col)))
    # 3) teclas que se sueltan hacia la derecha
    for x, y, t in ((140, 26, 9), (142, 58, 6.5)):
        tecla(d, (x, y, x + t, y + t), k)
    return out


def tecla(d, caja, k, color=None):
    x1, y1, x2, y2 = (v * k for v in caja)
    r = max(1.0, (x2 - x1) * 0.22)
    sombra = tuple(max(0, c - 70) for c in color) if color else BORDE_TECLA
    d.rounded_rectangle((x1, y1, x2, y2), radius=r, fill=sombra)               # canto
    d.rounded_rectangle((x1, y1, x2, y2 - (y2 - y1) * 0.16), radius=r, fill=color or CUERPO)


def reducir(im, ancho):
    alto = round(im.height * ancho / im.width)
    return im.resize((ancho, alto), Image.LANCZOS)


def cuadrado(lado):
    base = Image.new("RGBA", (lado * E, lado * E), (0, 0, 0, 0))
    ImageDraw.Draw(base).rounded_rectangle((0, 0, lado * E - 1, lado * E - 1),
                                           radius=int(lado * E * 0.22), fill=OSCURO)
    base = base.resize((lado, lado), Image.LANCZOS)
    fig = reducir(dibujo(E * lado / 170), int(lado * 0.88))
    base.alpha_composite(fig, ((lado - fig.width) // 2, (lado - fig.height) // 2))
    return base


if __name__ == "__main__":
    grande = cuadrado(256)
    grande.save(os.path.join(CARPETA, "icono.png"))
    grande.save(os.path.join(CARPETA, "icono.ico"), sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (256, 256)])
    reducir(dibujo(E), 84).save(os.path.join(CARPETA, "icono_ancho.png"))
    print("ok")
