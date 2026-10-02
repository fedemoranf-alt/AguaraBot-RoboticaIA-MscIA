@echo off
rem Lanza provisionar_pi.ps1 sin depender de la directiva de ejecucion de
rem PowerShell (ver entrar.cmd). Acepta los mismos parametros:
rem     provisionar_pi.cmd -Equipo admin@192.168.43.57
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0provisionar_pi.ps1" %*
