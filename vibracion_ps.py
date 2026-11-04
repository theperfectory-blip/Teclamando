"""Vibración para mandos de PlayStation (DualShock 4 y DualSense), que winmm no sabe hacer vibrar.

Busca el mando por HID (Sony, VID 054C) y le escribe el informe de salida con la fuerza de los dos
motores, igual que hace la consola. DualShock 4 por cable y por Bluetooth; DualSense por cable.
Los demás mandos genéricos siguen sin vibración. Solo ctypes, sin dependencias.
"""
import ctypes
import zlib
from ctypes import wintypes

SONY = 0x054C
DS4 = {0x05C4, 0x09CC, 0x0BA0}          # DualShock 4 v1, v2 y el adaptador inalámbrico
DUALSENSE = {0x0CE6, 0x0DF2}            # DualSense y DualSense Edge

hid = ctypes.WinDLL("hid")
setupapi = ctypes.WinDLL("setupapi")
kernel32 = ctypes.WinDLL("kernel32")


class GUID(ctypes.Structure):
    _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD), ("Data3", wintypes.WORD),
                ("Data4", ctypes.c_ubyte * 8)]


class SP_DEVICE_INTERFACE_DATA(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("InterfaceClassGuid", GUID), ("Flags", wintypes.DWORD),
                ("Reserved", ctypes.c_void_p)]


class HIDD_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Size", wintypes.ULONG), ("VendorID", wintypes.USHORT), ("ProductID", wintypes.USHORT),
                ("VersionNumber", wintypes.USHORT)]


class HIDP_CAPS(ctypes.Structure):
    _fields_ = [("Usage", wintypes.USHORT), ("UsagePage", wintypes.USHORT),
                ("InputReportByteLength", wintypes.USHORT), ("OutputReportByteLength", wintypes.USHORT),
                ("FeatureReportByteLength", wintypes.USHORT), ("Reserved", wintypes.USHORT * 17),
                ("resto", wintypes.USHORT * 10)]


setupapi.SetupDiGetClassDevsW.restype = ctypes.c_void_p
setupapi.SetupDiGetClassDevsW.argtypes = [ctypes.POINTER(GUID), ctypes.c_wchar_p, ctypes.c_void_p, wintypes.DWORD]
setupapi.SetupDiEnumDeviceInterfaces.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(GUID),
                                                 wintypes.DWORD, ctypes.POINTER(SP_DEVICE_INTERFACE_DATA)]
setupapi.SetupDiGetDeviceInterfaceDetailW.argtypes = [ctypes.c_void_p, ctypes.POINTER(SP_DEVICE_INTERFACE_DATA),
                                                      ctypes.c_void_p, wintypes.DWORD,
                                                      ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
setupapi.SetupDiDestroyDeviceInfoList.argtypes = [ctypes.c_void_p]
kernel32.CreateFileW.restype = ctypes.c_void_p
kernel32.CreateFileW.argtypes = [ctypes.c_wchar_p, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                                 wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p]
kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
kernel32.WriteFile.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD,
                               ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
hid.HidD_GetAttributes.argtypes = [ctypes.c_void_p, ctypes.POINTER(HIDD_ATTRIBUTES)]
hid.HidD_GetPreparsedData.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
hid.HidD_FreePreparsedData.argtypes = [ctypes.c_void_p]
hid.HidP_GetCaps.argtypes = [ctypes.c_void_p, ctypes.POINTER(HIDP_CAPS)]
INVALIDO = ctypes.c_void_p(-1).value


def _rutas_hid():
    guid = GUID()
    hid.HidD_GetHidGuid(ctypes.byref(guid))
    lista = setupapi.SetupDiGetClassDevsW(ctypes.byref(guid), None, None, 0x12)   # PRESENT | DEVICEINTERFACE
    if not lista or lista == INVALIDO:
        return
    try:
        i = 0
        while True:
            datos = SP_DEVICE_INTERFACE_DATA()
            datos.cbSize = ctypes.sizeof(datos)
            if not setupapi.SetupDiEnumDeviceInterfaces(lista, None, ctypes.byref(guid), i, ctypes.byref(datos)):
                return
            i += 1
            n = wintypes.DWORD()
            setupapi.SetupDiGetDeviceInterfaceDetailW(lista, ctypes.byref(datos), None, 0, ctypes.byref(n), None)
            buf = ctypes.create_string_buffer(n.value)
            ctypes.cast(buf, ctypes.POINTER(wintypes.DWORD))[0] = 8 if ctypes.sizeof(ctypes.c_void_p) == 8 else 6
            if setupapi.SetupDiGetDeviceInterfaceDetailW(lista, ctypes.byref(datos), buf, n, None, None):
                yield ctypes.wstring_at(ctypes.addressof(buf) + 4)
    finally:
        setupapi.SetupDiDestroyDeviceInfoList(lista)


class VibracionPS:
    def __init__(self):
        self.h = None
        self.tipo = None          # "ds4" o "dualsense"
        self.largo = 0            # largo del informe de salida (32 = DS4 por cable, 78 = Bluetooth)

    def buscar(self):
        self.cerrar()
        for ruta in _rutas_hid():
            h = kernel32.CreateFileW(ruta, 0x40000000, 3, None, 3, 0, None)   # escribir, compartido
            if not h or h == INVALIDO:
                continue
            a = HIDD_ATTRIBUTES()
            a.Size = ctypes.sizeof(a)
            tipo = None
            if hid.HidD_GetAttributes(h, ctypes.byref(a)) and a.VendorID == SONY:
                tipo = "ds4" if a.ProductID in DS4 else "dualsense" if a.ProductID in DUALSENSE else None
            largo = 0
            if tipo:
                pp = ctypes.c_void_p()
                if hid.HidD_GetPreparsedData(h, ctypes.byref(pp)):
                    caps = HIDP_CAPS()
                    hid.HidP_GetCaps(pp, ctypes.byref(caps))
                    largo = caps.OutputReportByteLength
                    hid.HidD_FreePreparsedData(pp)
            if tipo and largo:
                self.h, self.tipo, self.largo = h, tipo, largo
                return True
            kernel32.CloseHandle(h)
        return False

    def cerrar(self):
        if self.h:
            kernel32.CloseHandle(self.h)
        self.h = None

    def _informe(self, fuerte, suave):
        if self.tipo == "ds4" and self.largo < 64:               # DualShock 4 por cable
            r = bytearray(self.largo)
            r[0:6] = bytes((0x05, 0x01, 0, 0, suave, fuerte))     # 0x01 = solo motores
            return r
        if self.tipo == "ds4" and self.largo == 78:              # DualShock 4 por Bluetooth (con CRC)
            r = bytearray(78)
            r[0:8] = bytes((0x11, 0xC0, 0xA0, 0x01, 0, 0, suave, fuerte))
            crc = zlib.crc32(bytes((0xA2,)) + bytes(r[:74])) & 0xFFFFFFFF
            r[74:78] = crc.to_bytes(4, "little")
            return r
        if self.tipo == "dualsense" and self.largo < 64:         # DualSense por cable
            r = bytearray(self.largo)
            r[0:5] = bytes((0x02, 0x03, 0x00, suave, fuerte))     # 0x03 = vibración compatible
            return r
        return None                                               # DualSense por Bluetooth: no

    def vibrar(self, fuerza):
        """fuerza 0-65535 en los dos motores (0 = parar). False si no hay mando PlayStation."""
        if self.h is None and not self.buscar():
            return False
        v = max(0, min(255, fuerza >> 8))
        r = self._informe(v, v)
        if r is None:
            return False
        escrito = wintypes.DWORD()
        b = (ctypes.c_ubyte * len(r)).from_buffer(r)
        if not kernel32.WriteFile(self.h, b, len(r), ctypes.byref(escrito), None):
            self.cerrar()                                         # se desconectó: buscarlo la próxima vez
            return False
        return True
