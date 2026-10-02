@echo off
rem Lanza entrar.ps1 sin depender de la directiva de ejecucion de PowerShell.
rem La carpeta del proyecto esta en Google Drive (G:), que Windows trata como
rem ubicacion remota: ahi ".\entrar.ps1" falla con "no esta firmado
rem digitalmente" (paso el 2026-10-02). Un .cmd no tiene esa restriccion.
rem Acepta los mismos parametros:  entrar.cmd -Ip 192.168.43.57
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0entrar.ps1" %*
