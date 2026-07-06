@echo off
setlocal EnableDelayedExpansion

chcp 65001 >nul

set "ROOT_DIR=%~dp0"
if "%ROOT_DIR:~-1%"=="\" set "ROOT_DIR=%ROOT_DIR:~0,-1%"

set "SERVER_DIR=%ROOT_DIR%\server"
set "CLIENT_DIR=%ROOT_DIR%\client"
set "FRONTEND_URL=http://localhost:3000"

if not exist "%SERVER_DIR%\app.py" (
    echo [ERROR] Could not find "%SERVER_DIR%\app.py".
    exit /b 1
)

if not exist "%CLIENT_DIR%\package.json" (
    echo [ERROR] Could not find "%CLIENT_DIR%\package.json".
    exit /b 1
)

if exist "%CLIENT_DIR%\node_modules" (
    set "FRONTEND_RUN=npm run dev"
) else (
    set "FRONTEND_RUN=npm install && npm run dev"
)

set "PYTHON_EXE=python"
set "PYTHON_CMD=python app.py"

if exist "%SERVER_DIR%\.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%SERVER_DIR%\.venv\Scripts\python.exe"
    set "PYTHON_CMD=.venv\Scripts\python.exe app.py"
)

REM ===== 请修改为你的数据库配置 =====
set "MYSQL_HOST=127.0.0.1"
set "MYSQL_PORT=3306"
set "MYSQL_USER=your_mysql_user"
set "MYSQL_PASSWORD=your_mysql_password"
set "MYSQL_DATABASE=db_enterprise_qa"

set "FRONTEND_CMD=cd /d ""%CLIENT_DIR%" && %FRONTEND_RUN%"

if /I "%~1"=="--dry-run" (
    echo [Backend]
    echo cd /d "%SERVER_DIR%"
    echo(!BACKEND_CMD!
    echo.
    echo [Frontend]
    echo(!FRONTEND_CMD!
    echo.
    echo [Browser]
    echo(!FRONTEND_URL!
    exit /b 0
)

set "BACKEND_IMPORT_CHECK=import flask, flask_cors, flask_sqlalchemy, pymysql, cryptography, ebooklib, bs4, striprtf, openpyxl"

echo [INFO] Checking backend Python dependencies...
pushd "%SERVER_DIR%" >nul
%PYTHON_EXE% -c "%BACKEND_IMPORT_CHECK%" >nul 2>&1
if errorlevel 1 (
    if exist "%SERVER_DIR%\.venv\Scripts\python.exe" (
        echo [WARN] Project .venv is missing required packages. Trying system Python...
        python -c "%BACKEND_IMPORT_CHECK%" >nul 2>&1
        if not errorlevel 1 (
            set "PYTHON_EXE=python"
            set "PYTHON_CMD=python app.py"
        )
    )

    %PYTHON_EXE% -c "%BACKEND_IMPORT_CHECK%" >nul 2>&1
    if errorlevel 1 (
        echo [INFO] Missing backend dependency detected. Installing from requirements.txt...
        %PYTHON_EXE% -m pip install -r requirements.txt
        if errorlevel 1 (
            popd >nul
            echo [ERROR] Backend dependency installation failed. Please inspect the pip output above.
            exit /b 1
        )
    )
)
popd >nul

set "BACKEND_CMD=set MYSQL_HOST=%MYSQL_HOST%&&set MYSQL_PORT=%MYSQL_PORT%&&set MYSQL_USER=%MYSQL_USER%&&set MYSQL_PASSWORD=%MYSQL_PASSWORD%&&set MYSQL_DATABASE=%MYSQL_DATABASE%&&%PYTHON_CMD%"

start "EnterpriseQA Backend" /D "%SERVER_DIR%" cmd /k "%BACKEND_CMD%"
start "EnterpriseQA Frontend" cmd /k "%FRONTEND_CMD%"

timeout /t 6 /nobreak >nul
start "" "%FRONTEND_URL%"

exit /b 0
