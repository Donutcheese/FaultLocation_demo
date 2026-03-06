@echo off
REM 在项目根目录运行，创建 .venv 并安装依赖（Windows）
cd /d "%~dp0"
if exist .venv (
    echo .venv 已存在，跳过创建。直接运行: .venv\Scripts\activate
    goto install
)
echo 正在创建虚拟环境 .venv ...
python -m venv .venv
if errorlevel 1 (
    echo 失败。请确保已安装 Python 并加入 PATH。
    exit /b 1
)
:install
echo 正在安装依赖...
.venv\Scripts\pip install -r python\requirements.txt
echo.
echo 完成。激活环境请执行: .venv\Scripts\activate
