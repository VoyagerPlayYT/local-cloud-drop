@echo off
chcp 65001 > nul
title Local Cloud File Drop
echo ========================================================
echo   Local Cloud File Drop (Домашний аналог AirDrop)
echo ========================================================
echo [INFO] Запуск файлового сервера на порту 8005 ...
start http://localhost:8005
python main.py
pause
