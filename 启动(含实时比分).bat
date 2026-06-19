@echo off
chcp 65001 >nul
cd /d "C:\Users\Administrator\Desktop\世界杯赛程"

echo ========================================
echo   2026 世界杯赛程 - 本地实时比分
echo ========================================
echo.
echo [0/2] 清理旧代理进程...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8765 ^| findstr LISTENING') do taskkill /f /pid %%a >nul 2>&1

echo [1/2] 启动比分代理服务 (端口 8765)...
start "WorldCup Proxy" /MIN python scores_proxy.py

echo [2/2] 打开赛程页面...
timeout /t 2 /nobreak >nul
start "" "http://localhost:8765"

echo.
echo ========================================
echo   已启动!
echo   本机访问: http://localhost:8765
echo.
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4"') do echo   局域网访问: http://%%a:8765
echo ========================================
echo.
echo 关闭此窗口不影响服务运行。
echo.
pause