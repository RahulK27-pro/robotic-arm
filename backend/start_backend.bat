@echo off
REM Quick Start Script for 6-DOF Robotic Arm Manual Control
REM Run this after uploading Arduino code

echo ================================================
echo 6-DOF Robotic Arm - Quick Start
echo ================================================
echo.

echo Step 1: Checking Python dependencies...
python -c "import serial, flask, flask_cors" 2>nul
if errorlevel 1 (
    echo Installing required packages...
    pip install pyserial flask flask-cors python-dotenv
) else (
    echo ✓ All dependencies installed
)
echo.

echo Step 2: Detecting COM ports...
python -m serial.tools.list_ports
echo.

echo Step 3: Testing Arduino connection...
python test_serial.py
echo.

echo ================================================
echo If Arduino test FAILED:
echo 1. Upload robotic_arm_controller.ino to Arduino
echo 2. Check COM port in app.py (line 21)
echo 3. Close Arduino Serial Monitor
echo ================================================
echo.

echo Step 4: Starting Flask backend...
echo Press Ctrl+C to stop the server
echo.

python app.py
