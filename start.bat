@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
rem ---------- 0. Java shares the same SQLite file as Python (EXPENSE_DB_PATH) ----------
set "EXPENSE_DB_PATH=%~dp0data\expenseai.db"

echo ==========================================
echo   ExpenseAI 一键启动（Day 25）
echo   FastAPI 8000 / Gradio 7860 / Java 8080
echo ==========================================
echo.

rem ---------- 1. 环境检查 ----------
if not exist ".venv\Scripts\python.exe" (
    echo [错误] 找不到 .venv\Scripts\python.exe，请先创建虚拟环境并安装依赖。
    pause
    exit /b 1
)
if not exist "expense-approval\pom.xml" (
    echo [错误] 找不到 expense-approval\pom.xml，Java 工程不完整。
    pause
    exit /b 1
)
.venv\Scripts\python.exe -c "import fastapi, uvicorn, gradio, httpx" >nul 2>&1
if errorlevel 1 echo [提示] Python 依赖可能没装全，如启动失败请运行：.venv\Scripts\pip install -r requirements.txt

rem ---------- 2. 端口检查（已占用则跳过，避免重复启动） ----------
call :check_port 8000 FASTAPI_BUSY
call :check_port 7860 GRADIO_BUSY
call :check_port 8080 JAVA_BUSY

if "!FASTAPI_BUSY!"=="1" echo [提示] 端口 8000 已被占用，跳过 FastAPI
if "!GRADIO_BUSY!"=="1"  echo [提示] 端口 7860 已被占用，跳过 Gradio
if "!JAVA_BUSY!"=="1"    echo [提示] 端口 8080 已被占用，跳过 Java
echo.

rem ---------- 3. 启动三个服务（各自独立窗口，Ctrl+C 或关窗即停） ----------
if not "!FASTAPI_BUSY!"=="1" (
    start "ExpenseAI-FastAPI" cmd /k "cd /d %~dp0 && .venv\Scripts\uvicorn.exe app.main:app --port 8000"
)
if not "!GRADIO_BUSY!"=="1" (
    start "ExpenseAI-Gradio" cmd /k "cd /d %~dp0 && .venv\Scripts\python.exe -m app.gradio_ui"
)
if not "!JAVA_BUSY!"=="1" (
    echo 首次启动 Java 会下载 Maven 依赖，可能需要几分钟，请耐心等待 Java 窗口。
    start "ExpenseAI-Java" cmd /k "cd /d %~dp0\expense-approval && mvnw.cmd spring-boot:run"
)

rem ---------- 4. 健康检查（连接失败会重试，最多等 N 秒） ----------
echo.
echo 正在检查服务是否就绪（Java 首次启动请多等一会）...
set HEALTH_FAIL=0
if not "!FASTAPI_BUSY!"=="1" call :wait_health "FastAPI-8000"  "http://127.0.0.1:8000/"       60
if not "!GRADIO_BUSY!"=="1"  call :wait_health "Gradio-7860"   "http://127.0.0.1:7860/"       60
if not "!JAVA_BUSY!"=="1"    call :wait_health "Java-8080"     "http://127.0.0.1:8080/ping"   90

echo.
if "!HEALTH_FAIL!"=="0" (
    echo ==========================================
    echo   全部服务已就绪：
    echo     FastAPI  http://127.0.0.1:8000
    echo     Gradio   http://127.0.0.1:7860
    echo     Java     http://127.0.0.1:8080/ping
    echo ==========================================
) else (
    echo [警告] 有服务未在时限内就绪，请查看对应窗口的报错信息。
)
pause
exit /b 0

rem ==========================================
rem  子过程：端口检查
rem  用法：call :check_port 端口号 结果变量名
rem ==========================================
:check_port
netstat -ano | findstr /C:":%~1 " | findstr "LISTENING" >nul
if errorlevel 1 ( set %~2=0 ) else ( set %~2=1 )
goto :eof

rem ==========================================
rem  子过程：健康检查（每 2 秒重试）
rem  用法：call :wait_health "名称" "URL" 最大等待秒数
rem ==========================================
:wait_health
set /a WAIT_MAX=%~3
set /a WAIT_ELAPSED=0
:health_loop
curl -s -o NUL "%~2" >nul 2>&1
if not errorlevel 1 (
    echo   [OK] %~1 已就绪
    goto :eof
)
ping -n 3 127.0.0.1 >nul
set /a WAIT_ELAPSED+=2
if !WAIT_ELAPSED! lss !WAIT_MAX! goto health_loop
echo   [失败] %~1 在 %WAIT_MAX% 秒内未就绪
set HEALTH_FAIL=1
goto :eof