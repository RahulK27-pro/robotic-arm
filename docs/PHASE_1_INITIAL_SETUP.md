# Phase 1: Initial Setup

This phase covers the fundamental hardware connections and software environment setup required to get the robotic arm operational.

## Hardware Wiring
The robotic arm is controlled by an Arduino Uno. The 6 servos are connected to the following PWM-capable pins:

| Servo Number | Function | Arduino Pin |
|--------------|----------|-------------|
| 1 | Base Rotation | Pin 3 |
| 2 | Shoulder | Pin 5 |
| 3 | Elbow | Pin 6 |
| 4 | Wrist Pitch | Pin 9 |
| 5 | Wrist Roll | Pin 10 |
| 6 | Gripper | Pin 11 |

> [!IMPORTANT]
> Servos must be powered by an external 5V power supply. Do NOT power all 6 servos directly from the Arduino 5V pin, as it cannot provide enough current and may damage the board.

### Sensors
- **HC-SR04 Ultrasonic Sensor**:
    - TRIG_PIN: 7
    - ECHO_PIN: 8

## Serial Communication Protocol
The Python backend communicates with the Arduino via Serial at **115200 baud**.

### Command Format
Angular commands are sent as bracketed, comma-separated strings:
- Format: `<angle1,angle2,angle3,angle4,angle5,angle6>`
- Example: `<90,130,115,90,12,170>`
- Acknowledgment: The Arduino returns `K` after successfully moving the servos.

### Distance Reading
- Command: `<GET_DIST>`
- Response: `<distance_in_cm>` (e.g., `<15.42>`)

## Software Environment
- **Backend**: Python 3.x
- **Frontend**: Vite + React + TypeScript
- **Serial Library**: `pyserial`
- **Environment Variables**: Managed via `.env` in the `backend` folder.
    - `GROQ_API_KEY`: API key for LLM integration.
    - `CAMERA_INDEX`: Index of the camera to use (e.g., `1` for external webcam).
