@echo off
REM NeuraGraph 启动脚本

echo ========================================
echo   NeuraGraph - AI Workflow Platform
echo ========================================
echo.

REM 激活虚拟环境
echo [1/3] 激活虚拟环境...
cd /d "%~dp0"
call venv\Scripts\activate.bat

REM 设置 PYTHONPATH
echo [2/3] 设置环境变量...
set PYTHONPATH=%CD%

REM 启动应用
echo [3/3] 启动 Flask 应用...
echo.
echo 访问地址: http://localhost:5001
echo 按 Ctrl+C 停止服务
echo.

python -m ui.app

pause
