# Teclamando

Usa Windows con el mando desde el sofá: ratón, navegador y YouTube con un mando de Xbox o de PlayStation, y un teclado en pantalla al estilo de la PS3, con tildes, ñ y palabras sugeridas que aprenden de lo que escribes.

## Descargar

Baja `Teclamando-x.y.z-instalador.exe` desde [Releases](../../releases) y ábrelo. No pide administrador ni necesita Python.

> Windows puede mostrar "Windows protegió su PC", porque el instalador no tiene firma digital (cuesta dinero y esto es gratis). Pulsa **Más información → Ejecutar de todas formas**. El código está entero en este repositorio.

## Encenderlo

Conecta el mando (cable o Bluetooth) y pulsa **Back + Start** a la vez (**Share + Options** en PlayStation). Vibra corto = encendido; otra vez = pausa.
Si dejaste marcado *Arrancar con Windows*, queda esperando cada vez que inicias sesión.

| Botón | Qué hace |
|---|---|
| Stick izquierdo | cursor |
| Stick derecho | scroll |
| A / RT | clic / clic derecho |
| LT (mantener) | cursor lento |
| B | atrás |
| Start | Enter |
| L3 | teclado en pantalla (también se abre solo al hacer clic en un campo de texto) |
| Back + R3 | guía con todos los botones (mantenido 3 s: configurar un mando que no es de Xbox) |

## Requisitos

- Windows 10 u 11 de 64 bits.
- Mando XInput (Xbox 360, Xbox One/Series y compatibles). Los de PlayStation y genéricos USB funcionan por DirectInput; si un botón no corresponde, usa *Configurar otro mando* en el menú Inicio o mantén Back + R3 3 segundos. Un mando genérico nuevo se ofrece configurar solo.

## Privacidad

Nada sale de tu PC. Los ajustes y las palabras aprendidas quedan en `%APPDATA%\Teclamando`.

## Compilar desde el código

Hace falta Python 3 e [Inno Setup 6](https://jrsoftware.org/isinfo.php); el compilador de C (Zig) lo baja Nuitka solo. Luego:

```
instalador\construir.bat
```

Sin compilar también funciona: `pythonw teclamando.py` (solo usa la biblioteca estándar).

## Créditos

Las 12 000 palabras de reserva del teclado (`palabras_reserva.txt`) salen de [FrequencyWords](https://github.com/hermitdave/FrequencyWords) de Hermit Dave (español, 2018, a partir de OpenSubtitles; CC-BY-SA 4.0), filtradas. Esa lista mantiene su licencia CC-BY-SA 4.0.

## Licencia

Código: MIT. Sin relación con Microsoft, Sony ni Valve; Xbox y PlayStation son marcas de sus dueños.
