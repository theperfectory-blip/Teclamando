@echo off
rem Compila Teclamando.exe con Nuitka y arma el instalador con Inno Setup.
rem Necesita: Python 3 (python.org) e Inno Setup 6. El compilador de C (Zig) lo baja Nuitka solo.
rem Resultado: instalador\salida\Teclamando-<version>-instalador.exe
rem El extra personal modo_juego.py NUNCA entra en el .exe (--nofollow-import-to).
setlocal
set VERSION=1.0.4
cd /d "%~dp0.."

if not exist .venv-construir\Scripts\python.exe (
    python -m venv .venv-construir || goto :error
)
.venv-construir\Scripts\python -m pip install -q --disable-pip-version-check nuitka==4.3.4 || goto :error

.venv-construir\Scripts\python -m nuitka teclamando.py ^
    --mode=standalone --zig --assume-yes-for-downloads ^
    --enable-plugin=tk-inter --windows-console-mode=disable ^
    --nofollow-import-to=modo_juego ^
    --windows-icon-from-ico=icono.ico ^
    --output-dir=instalador\build --output-filename=Teclamando.exe ^
    --product-name=Teclamando --file-description=Teclamando ^
    --product-version=%VERSION% --file-version=%VERSION% ^
    --company-name=Teclamando --copyright="Licencia MIT" ^
    --include-data-files=palabras_es.txt=palabras_es.txt ^
    --include-data-files=palabras_reserva.txt=palabras_reserva.txt ^
    --include-data-files=vigilar_foco.ps1=vigilar_foco.ps1 ^
    --include-data-files=icono.ico=icono.ico ^
    --include-data-files=icono.png=icono.png ^
    --include-data-files=icono_ancho.png=icono_ancho.png ^
    --include-data-files=sonido_mover.wav=sonido_mover.wav ^
    --include-data-files=sonido_tecla.wav=sonido_tecla.wav ^
    || goto :error

set ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe
if not exist "%ISCC%" set ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe
if not exist "%ISCC%" (
    echo No encuentro Inno Setup 6. El programa compilado quedo en instalador\build\teclamando.dist
    goto :fin
)
"%ISCC%" /Qp /DVersion=%VERSION% instalador\teclamando.iss || goto :error
echo.
echo Listo: instalador\salida\Teclamando-%VERSION%-instalador.exe
goto :fin

:error
echo.
echo Fallo la compilacion.
exit /b 1
:fin
endlocal
