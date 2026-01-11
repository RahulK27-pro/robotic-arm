@echo off
echo ==================================================
echo   STOPPING BACKEND TO FREE CAMERA
echo ==================================================
taskkill /F /IM python.exe
timeout /t 2 /nobreak >nul

echo.
echo ==================================================
echo   STARTING ANFIS DATA COLLECTION
echo ==================================================
echo   1. Open http://localhost:5000/video_feed
echo   2. Place target object
echo   3. Close this window to stop
echo.

python backend/tools/collect_x_anfis.py
pause
