"""Mandos que no son de Xbox (PlayStation, genéricos USB, 8BitDo en modo D...): se leen con la API
de joystick de Windows (winmm, joyGetPosEx) y se traducen al mismo formato que XInput, así el resto
del programa no nota la diferencia. Solo ctypes, sin dependencias.

Qué número de botón o eje es cada cosa cambia de un mando a otro: lo dice `mando_generico.json`,
que crea configurar_mando.py (te pide pulsar cada botón). Sin ese archivo se usa la distribución
de los mandos de PlayStation (DualShock 4 / DualSense), que es también la de muchos genéricos.
"""
import ctypes
import json
import os
from ctypes import wintypes

import rutas

ARCHIVO_MAPA = rutas.datos("mando_generico.json")

winmm = ctypes.WinDLL("winmm")

JOY_RETURNALL = 0xFF
POV_CENTRO = 0xFFFF
EJES = "XYZRUV"     # dwXpos, dwYpos, dwZpos, dwRpos, dwUpos, dwVpos

# Mismos bits que XInput (mando_raton.py)
BITS = {"ARRIBA": 0x0001, "ABAJO": 0x0002, "IZQUIERDA": 0x0004, "DERECHA": 0x0008,
        "START": 0x0010, "BACK": 0x0020, "L3": 0x0040, "R3": 0x0080,
        "LB": 0x0100, "RB": 0x0200, "A": 0x1000, "B": 0x2000, "X": 0x4000, "Y": 0x8000}

# PlayStation por DirectInput: 1 cuadrado, 2 X, 3 círculo, 4 triángulo, 5 L1, 6 R1, 7 L2, 8 R2,
# 9 Share/Create, 10 Options, 11 L3, 12 R3. Sticks: X/Y izquierdo, Z/R derecho. Cruceta = POV.
MAPA_PS = {
    "botones": {"X": 1, "A": 2, "B": 3, "Y": 4, "LB": 5, "RB": 6, "BACK": 9, "START": 10,
                "L3": 11, "R3": 12},
    "gatillos": {"LT": {"boton": 7}, "RT": {"boton": 8}},
    "ejes": {"LX": {"eje": "X", "signo": 1}, "LY": {"eje": "Y", "signo": -1},
             "RX": {"eje": "Z", "signo": 1}, "RY": {"eje": "R", "signo": -1}},
    "cruceta": "pov",
}


class JOYINFOEX(ctypes.Structure):
    _fields_ = [("dwSize", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("dwXpos", wintypes.DWORD), ("dwYpos", wintypes.DWORD), ("dwZpos", wintypes.DWORD),
                ("dwRpos", wintypes.DWORD), ("dwUpos", wintypes.DWORD), ("dwVpos", wintypes.DWORD),
                ("dwButtons", wintypes.DWORD), ("dwButtonNumber", wintypes.DWORD),
                ("dwPOV", wintypes.DWORD), ("dwReserved1", wintypes.DWORD),
                ("dwReserved2", wintypes.DWORD)]


class JOYCAPSW(ctypes.Structure):
    _fields_ = [("wMid", wintypes.WORD), ("wPid", wintypes.WORD), ("szPname", wintypes.WCHAR * 32),
                ("wXmin", wintypes.UINT), ("wXmax", wintypes.UINT), ("wYmin", wintypes.UINT),
                ("wYmax", wintypes.UINT), ("wZmin", wintypes.UINT), ("wZmax", wintypes.UINT),
                ("wNumButtons", wintypes.UINT), ("wPeriodMin", wintypes.UINT),
                ("wPeriodMax", wintypes.UINT), ("wRmin", wintypes.UINT), ("wRmax", wintypes.UINT),
                ("wUmin", wintypes.UINT), ("wUmax", wintypes.UINT), ("wVmin", wintypes.UINT),
                ("wVmax", wintypes.UINT), ("wCaps", wintypes.UINT), ("wMaxAxes", wintypes.UINT),
                ("wNumAxes", wintypes.UINT), ("wMaxButtons", wintypes.UINT),
                ("szRegKey", wintypes.WCHAR * 32), ("szOEMVxD", wintypes.WCHAR * 260)]


def leer_crudo(indice):
    """Estado crudo del joystick `indice` (0-15), o None si no hay nada conectado ahí."""
    info = JOYINFOEX()
    info.dwSize = ctypes.sizeof(JOYINFOEX)
    info.dwFlags = JOY_RETURNALL
    if winmm.joyGetPosEx(indice, ctypes.byref(info)) != 0:
        return None
    return info


def rangos(indice):
    """{eje: (mínimo, máximo)} y nombre del mando según Windows."""
    caps = JOYCAPSW()
    if winmm.joyGetDevCapsW(indice, ctypes.byref(caps), ctypes.sizeof(JOYCAPSW)) != 0:
        return {e: (0, 65535) for e in EJES}, ""
    r = {"X": (caps.wXmin, caps.wXmax), "Y": (caps.wYmin, caps.wYmax),
         "Z": (caps.wZmin, caps.wZmax), "R": (caps.wRmin, caps.wRmax),
         "U": (caps.wUmin, caps.wUmax), "V": (caps.wVmin, caps.wVmax)}
    for e, (a, b) in r.items():
        if b <= a:
            r[e] = (0, 65535)
    return r, caps.szPname


def valor_eje(info, eje):
    return getattr(info, "dw%spos" % eje)


def pov_a_cruceta(pov):
    """Ángulo del POV (centésimas de grado, 0 = arriba) -> bits de la cruceta (con diagonales)."""
    if pov == POV_CENTRO or pov > 36000:
        return 0
    bits = 0
    if pov >= 31500 or pov <= 4500:
        bits |= BITS["ARRIBA"]
    if 4500 <= pov <= 13500:
        bits |= BITS["DERECHA"]
    if 13500 <= pov <= 22500:
        bits |= BITS["ABAJO"]
    if 22500 <= pov <= 31500:
        bits |= BITS["IZQUIERDA"]
    return bits


def cargar_mapa():
    try:
        with open(ARCHIVO_MAPA, encoding="utf-8") as f:
            mapa = json.load(f)
        if isinstance(mapa, dict) and "botones" in mapa and "ejes" in mapa:
            return mapa
    except (OSError, ValueError):
        pass
    return MAPA_PS


def mapa_cambiado(mtime_anterior):
    try:
        return os.path.getmtime(ARCHIVO_MAPA) != mtime_anterior
    except OSError:
        return mtime_anterior is not None


class MandoGenerico:
    """Busca el primer joystick conectado y lo devuelve con forma de XINPUT_GAMEPAD."""

    def __init__(self):
        self.indice = None
        self.rangos = {}
        self.nombre = ""
        self.mapa = cargar_mapa()
        self.mtime = self._mtime()

    def _mtime(self):
        try:
            return os.path.getmtime(ARCHIVO_MAPA)
        except OSError:
            return None

    def recargar_si_cambio(self):
        """El configurador puede reescribir el mapa con el programa en marcha."""
        if mapa_cambiado(self.mtime):
            self.mapa = cargar_mapa()
            self.mtime = self._mtime()

    def buscar(self):
        for i in range(16):
            if leer_crudo(i) is not None:
                self.indice = i
                self.rangos, self.nombre = rangos(i)
                return True
        self.indice = None
        return False

    def _normal(self, info, eje):
        """Eje en [-1, 1] respecto del centro de su rango."""
        a, b = self.rangos.get(eje, (0, 65535))
        mitad = (b - a) / 2
        return max(-1.0, min(1.0, (valor_eje(info, eje) - a - mitad) / mitad)) if mitad else 0.0

    def leer(self, g):
        """Rellena `g` (XINPUT_GAMEPAD). Devuelve False si el mando se desconectó."""
        if self.indice is None:
            return False
        info = leer_crudo(self.indice)
        if info is None:
            self.indice = None
            return False
        m = self.mapa
        botones = 0
        for nombre, numero in m["botones"].items():
            if nombre in BITS and numero and info.dwButtons & (1 << (int(numero) - 1)):
                botones |= BITS[nombre]
        cruceta = m.get("cruceta", "pov")
        if cruceta == "pov":
            botones |= pov_a_cruceta(info.dwPOV)
        elif isinstance(cruceta, dict):           # cruceta como botones sueltos
            for nombre, numero in cruceta.items():
                if nombre in BITS and numero and info.dwButtons & (1 << (int(numero) - 1)):
                    botones |= BITS[nombre]
        g.wButtons = botones
        for campo, clave in (("bLeftTrigger", "LT"), ("bRightTrigger", "RT")):
            gat = m.get("gatillos", {}).get(clave) or {}
            v = 0
            if "boton" in gat:
                v = 255 if info.dwButtons & (1 << (int(gat["boton"]) - 1)) else 0
            elif "eje" in gat:
                reposo, lleno = gat.get("reposo", 0), gat.get("lleno", 65535)
                if lleno != reposo:
                    f = (valor_eje(info, gat["eje"]) - reposo) / (lleno - reposo)
                    v = int(max(0.0, min(1.0, f)) * 255)
            setattr(g, campo, v)
        for campo, clave in (("sThumbLX", "LX"), ("sThumbLY", "LY"),
                             ("sThumbRX", "RX"), ("sThumbRY", "RY")):
            e = m["ejes"].get(clave)
            v = self._normal(info, e["eje"]) * e.get("signo", 1) if e else 0.0
            setattr(g, campo, int(max(-32767, min(32767, v * 32767))))
        return True
