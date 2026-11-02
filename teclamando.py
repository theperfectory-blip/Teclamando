"""Punto de entrada de Teclamando.exe (la versión compilada): un solo programa con todas las partes.

  Teclamando.exe              encender ya activo
  Teclamando.exe espera       queda dormido hasta Back + Start (Share + Options en PlayStation)
  Teclamando.exe --configurar enseñarle los botones de un mando que no es de Xbox
  --guia / --indicador        la guía de botones y la mini ventana (las lanza el propio programa)
"""
import sys


def main():
    if "--guia" in sys.argv:
        import guia_mando
        guia_mando.main()
    elif "--indicador" in sys.argv:
        import indicador_mando
        indicador_mando.main()
    elif "--configurar" in sys.argv:
        import configurar_mando
        configurar_mando.main()
    else:
        import mando_raton
        mando_raton.main()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # sin consola: dejar el error donde se pueda leer (%APPDATA%\Teclamando\errores.txt)
        import time
        import traceback
        import rutas
        with open(rutas.datos("errores.txt"), "a", encoding="utf-8") as f:
            f.write("\n%s %s\n%s" % (time.strftime("%Y-%m-%d %H:%M:%S"), sys.argv[1:], traceback.format_exc()))
        raise
