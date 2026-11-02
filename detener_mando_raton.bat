@echo off
rem Cierra el mando-raton y su guia
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='pythonw.exe'\" | Where-Object { $_.CommandLine -like '*mando_raton.py*' -or $_.CommandLine -like '*guia_mando.py*' -or $_.CommandLine -like '*indicador_mando.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
