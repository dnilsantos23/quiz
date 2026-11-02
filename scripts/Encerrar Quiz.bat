@echo off
rem ==============================================================================
rem ENCERRAMENTO DO SERVIDOR DO QUIZ
rem 
rem Finaliza qualquer processo ativo na porta 5000
rem ==============================================================================
chcp 65001 >nul
cd /d "%~dp0.."
title Encerrar Quiz - Uninter

echo ========================================================
echo    Encerrando Servidor do Quiz...
echo ========================================================
echo.

powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 5000 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }"
echo Servidor finalizado com sucesso!
timeout /t 2 /nobreak >nul
exit
