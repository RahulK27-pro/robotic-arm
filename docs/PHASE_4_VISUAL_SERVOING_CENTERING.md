# Phase 4: Visual Servoing Centering (X/Y Alignment)

This phase focuses on the "look-and-move" feedback loop that centers a target object in the camera's field of view.

## Core Logic (`visual_servoing.py`)
The `VisualServoingAgent` implements a proportional control loop to minimize the error between the object center and the frame center.

### Axis Responsibilities
- **X-Axis (Base Servo)**: Rotates the entire arm left or right to align horizontally.
- **Y-Axis (Elbow Servo)**: Moves the arm up or down to align vertically.

### States
1. **SEARCHING**: If the target object is not detected, the arm performs a horizontal sweep (0° to 180°) using the Base servo until the object is found.
2. **TRACKING**: Once detected, the agent computes the pixel error (`error_x`, `error_y`).

### Proportional Control (P-Controller)
The correction applied to the servos is proportional to the pixel error:
- `Correction_X = error_x * GAIN_X`
- `Correction_Y = -(error_y * GAIN_Y)` (Negative because moving the elbow up requires decreasing the angle).

### Tuned Parameters
- **GAIN_X / GAIN_Y**: 0.02 (Reduced from 0.05 to prevent jitter/oscillation).
- **DEADZONE**: 20 pixels (The object is considered centered if the error is within ±20px).
- **MAX_STEP**: 2.0 degrees (Limits how much a servo can move in a single frame for safety).

## Sequential Alignment
To improve stability, the system performs **Sequential Alignment**:
1. First, it corrects the **X-axis** until the object is horizontally centered.
2. Once X is centered, it starts correcting the **Y-axis** while maintaining the X alignment.
3. Only when both X and Y are centered for several consecutive frames (e.g., 5 frames) does the system transition to the next phase (Approaching/Grabbing).
