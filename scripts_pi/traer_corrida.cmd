@echo off
rem Lanza traer_corrida.ps1 sin depender de la directiva de ejecucion de
rem PowerShell (ver entrar.cmd). Acepta los mismos parametros:
rem     traer_corrida.cmd -Video        traer_corrida.cmd -Cuantas 10
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0traer_corrida.ps1" %*
