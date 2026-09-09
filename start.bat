@echo off
chcp 65001 >nul
cd /d "%~dp0"
title AI Image Generator - local server

if not exist "proxy.py" goto NO_FILE

where python >nul 2>nul
if %errorlevel%==0 goto RUN_PYTHON

where py >nul 2>nul
if %errorlevel%==0 goto RUN_PY

echo.
echo [x] 没找到 Python。
echo.
echo     请安装 Python 3.7 或更高版本： https://www.python.org/downloads/
echo     安装时务必勾选 "Add Python to PATH"，装完重新双击本文件。
echo.
pause
goto :eof

:NO_FILE
echo.
echo [x] 当前目录下找不到 proxy.py。
echo     请把本文件和 proxy.py、index.html 放在同一个文件夹里。
echo.
pause
goto :eof

:RUN_PYTHON
python proxy.py %*
goto DONE

:RUN_PY
py proxy.py %*

:DONE
echo.
echo 服务已停止。
pause
