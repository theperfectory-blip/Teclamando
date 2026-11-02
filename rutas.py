"""Dónde están los archivos del programa y dónde se guardan los tuyos.

Desde el código (.py): todo en la carpeta del programa, como siempre.
Compilado (Teclamando.exe del instalador): los archivos del programa junto al .exe y lo tuyo
(ajustes, palabras aprendidas, posición de la mini ventana, mapa de otro mando) en
%APPDATA%\\Teclamando, que no se borra al reinstalar ni al actualizar.
"""
import os
import sys

COMPILADO = "__compiled__" in globals() or getattr(sys, "frozen", False)   # Nuitka o PyInstaller
PROGRAMA = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
if COMPILADO:
    DATOS = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "Teclamando")
    os.makedirs(DATOS, exist_ok=True)
else:
    DATOS = PROGRAMA


def programa(nombre):
    """Archivo que viene con el programa (diccionario, iconos, sonidos, ayudante)."""
    return os.path.join(PROGRAMA, nombre)


def datos(nombre):
    """Archivo tuyo, que el programa escribe."""
    return os.path.join(DATOS, nombre)


def orden(opcion, script):
    """Cómo lanzar otra parte del programa (guía, mini ventana, configurar mando) en su proceso:
    compilado, el mismo .exe con una opción; desde el código, python con su .py."""
    if COMPILADO:
        return [os.path.abspath(sys.argv[0]), opcion]    # el propio Teclamando.exe
    return [sys.executable, programa(script)]
