@echo off
setlocal
cd /d "%~dp0"

echo ==========================================
echo   ExpenseAI local launcher
echo ==========================================
echo.

rem ---------- 1. 定位 JDK 21（覆盖系统里的 Java 8）----------
if not defined JDK21_HOME (
    if exist "C:\Program Files\Eclipse Adoptium" (
        for /d %%D in ("C:\Program Files\Eclipse Adoptium\jdk-21*") do set "JDK21_HOME=%%D"
    )
)
if not defined JDK21_HOME if exist "G:\python project\.tools\jdk21" set "JDK21_HOME=G:\python project\.tools\jdk21"
if not defined JDK21_HOME (
    echo [ERROR] JDK 21 not found. Install it first:
    echo   winget install --id EclipseAdoptium.Temurin.21.JDK
    echo Then rerun this script, or set JDK21_HOME to your JDK 21 path.
    pause
    exit /b 1
)
echo [OK] JAVA_HOME=%JDK21_HOME%
set "JAVA_HOME=%JDK21_HOME%"
set "PATH=%JAVA_HOME%\bin;%PATH%"

rem ---------- 2. Java 与 Python 共用同一个 SQLite 文件 ----------
set "EXPENSE_DB_PATH=%~dp0data\expenseai.db"
echo [OK] EXPENSE_DB_PATH=%EXPENSE_DB_PATH%
echo.

rem ---------- 3. 复用项目自带的一键启动脚本 ----------
call start.bat
