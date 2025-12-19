# Phase 6: Autonomous Pick and Place

This phase integrates all previous subsystems (Vision, Kinematics, Control) into a high-level autonomous workflow.

## Visual Grab Workflow (`grab_controller.py`)
The `VisualGrabController` manages the state machine for the entire pick operation:
`IDLE` → `ALIGNING` → `APPROACHING` → `GRAB_READY` → `GRABBING` → `COMPLETE`

### Execution Phases:
1. **ALIGNING (X/Y)**:
    - Triggers the `VisualServoingAgent` to center the object.
    - Monitors the detection stream until `is_centered` is true.
2. **APPROACHING (Z)**:
    - Opens the gripper (170°).
    - Moves forward incrementally using Inverse Kinematics.
    - Tracks progress from 40cm down to 2cm.
3. **GRABBING**:
    - Closes the gripper (120°).
    - Performs the "Lift" action to confirm a successful pick.

## Pick and Place Sequence
A full "Pick and Place" operation involves:
1. **Scanning**: AI identifies the target and destination.
2. **Picking**: The workflow described above.
3. **Transport**: Rotating the base to the destination coordinates while holding the object.
4. **Placing**:
    - Approaching the destination from above.
    - Lowering to the target height.
    - Opening the gripper to 90°.
    - Lifting away.

## Smooth Movement Control
To ensure the arm doesn't "jump" between distant points:
- **Interpolation**: Large movements are broken down into small increments (e.g., 40 steps).
- **Sequential Servo Control**: For complex poses, servos can be moved one-by-one (Base → Shoulder → Elbow) to maintain stability.
