@echo off
title Quiz Bot Multi-Layer Launcher
cd /d "C:\Users\Elite\myBot"

echo ================================= >> bot_system.log
echo [%date% %time%] SYSTEM START >> bot_system.log

:wait_for_system
echo [%date% %time%] Waiting for system stabilization... >> bot_system.log
timeout /t 30 >nul

:check_python
echo [%date% %time%] Checking Python... >> bot_system.log
"venv\Scripts\python.exe" -c "print('Python OK')" >nul 2>&1
if %errorlevel% neq 0 (
    echo [%date% %time%] Python check failed, retrying... >> bot_system.log
    timeout /t 10 >nul
    goto check_python
)

:main_loop
echo [%date% %time%] Starting main bot... >> bot_system.log
"venv\Scripts\python.exe" bot.py

echo [%date% %time%] Bot stopped, exit code: %errorlevel% >> bot_system.log

if %errorlevel% == 0 (
    echo [%date% %time%] Normal shutdown >> bot_system.log
    exit /b 0
) else (
    echo [%date% %time%] Crash detected, restarting in 15 seconds... >> bot_system.log
    timeout /t 15 >nul
    goto main_loop
)