@echo off
rem ==============================================================================
rem INICIALIZADOR E PREPARADOR DO QUIZ - FACULDADE
rem ==============================================================================
chcp 65001 >nul
cd /d "%~dp0.."
title Servidor do Quiz - Uninter

echo ================================================================
echo    PREPARANDO O SISTEMA DE EXERCICIOS
echo    Complementos necessarios serao verificados e instalados.
echo    Aguarde ate a conclusao desta janela.
echo ================================================================
echo.

set "ERRO=0"
set "PY_BASE="

echo [1/4] Verificando o Python...
where python >nul 2>nul
if not errorlevel 1 set "PY_BASE=python"
if not defined PY_BASE (
    where py >nul 2>nul
    if not errorlevel 1 set "PY_BASE=py -3"
)
if not defined PY_BASE (
    where winget >nul 2>nul
    if errorlevel 1 (
        echo ERRO: Python nao encontrado e o winget nao esta disponivel.
        echo Instale o Python 3.10+ em https://www.python.org/downloads/
        set "ERRO=1"
        goto :falha
    )
    echo Python nao encontrado. Instalando Python 3.12 pelo Windows Package Manager...
    winget install --id Python.Python.3.12 -e --accept-source-agreements --accept-package-agreements
    if errorlevel 1 (
        echo ERRO: nao foi possivel instalar o Python.
        set "ERRO=1"
        goto :falha
    )
    set "PATH=%LocalAppData%\Programs\Python\Python312;%LocalAppData%\Programs\Python\Python312\Scripts;%PATH%"
    if exist "%LocalAppData%\Programs\Python\Python312\python.exe" set "PY_BASE=%LocalAppData%\Programs\Python\Python312\python.exe"
)
if not defined PY_BASE (
    echo ERRO: Python ainda nao esta disponivel nesta sessao.
    echo Feche e abra o inicializador novamente.
    set "ERRO=1"
    goto :falha
)
%PY_BASE% --version
if errorlevel 1 (
    echo ERRO: a instalacao do Python nao pode ser executada.
    set "ERRO=1"
    goto :falha
)

echo [2/4] Criando ou atualizando o ambiente virtual...
if not exist ".venv\Scripts\python.exe" (
    %PY_BASE% -m venv .venv
    if errorlevel 1 (
        echo ERRO: nao foi possivel criar o ambiente virtual.
        set "ERRO=1"
        goto :falha
    )
)
set "PY_CMD=.venv\Scripts\python.exe"

echo [3/4] Instalando dependencias Python...
%PY_CMD% -m pip install --upgrade pip -q
if errorlevel 1 (
    echo ERRO: nao foi possivel atualizar o pip.
    set "ERRO=1"
    goto :falha
)
%PY_CMD% -m pip install -r requirements.txt
if errorlevel 1 (
    echo ERRO: nao foi possivel instalar as dependencias Python.
    set "ERRO=1"
    goto :falha
)

:iniciar
echo [4/4] Preparacao concluida. Iniciando o sistema...
echo.
%PY_CMD% main.py

if errorlevel 1 goto :falha
goto :fim

:falha
if "%ERRO%"=="1" (
    echo.
    echo A preparacao nao foi concluida. Corrija o problema e tente novamente.
    pause
)

:fim
