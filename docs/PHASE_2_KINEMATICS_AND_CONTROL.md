# Phase 2: Kinematics and Control

This phase details how the robotic arm's movements are computed and executed.

## Robot Driver (`robot_driver.py`)
The `RobotArm` class in `backend/hardware/robot_driver.py` serves as the primary interface between the high-level Python logic and the Arduino firmware.

### Key Features:
- **Port Discovery**: Automatically finds the correct COM port for the Arduino.
- **Angle Tracking**: Maintains the `current_angles` state of the arm.
- **Hardware/Simulation Modes**: Can run in `hardware=True` (actual serial comms) or `hardware=False` (log only).
- **Movement Methods**:
    - `move_to(angles)`: Sends raw angles to the Arduino.
    - `set_servo_angle(index, angle)`: Moves a specific servo by updating its value in the current angle array and sending the full set.

## Kinematics Engine (`kinematics.py`)
The kinematics module handles the translation between 3D Cartesian coordinates (X, Y, Z) and the 6 servo angles.

### Forward Kinematics
Calculates the end-effector position (x, y, z) based on the current angles of the shoulder, elbow, and wrist.

### Inverse Kinematics (IK)
Calculates the required angles to reach a target (x, y, z) coordinate.
- Uses geometric derivation for the 3-DOF arm structure (Base, Shoulder, Elbow).
- Constraints are applied to ensure angles stay within the 0-180 degree physical limits of the servos.

## Manual Controls
The frontend provides a `ManualControls` component that allows for:
1. **Real-time Slide Control**: Throttled slider inputs (every 100ms) to prevent serial flooding.
2. **Coordinate Display**: Live feedback of X, Y, Z, and Gripper status.
3. **Smooth Interpolation**: When resetting or moving to default positions, the backend interpolates movements over multiple steps (e.g., 40 steps at 0.05s intervals) to prevent sudden jerky motions.
