# Phase 5: Continuous Grab Controller (Distance & Z-Axis)

This phase covers the advanced autonomous behavior of approaching and grabbing an object while maintaining visual alignment.

## Continuous Alignment Logic (`continuous_grab_controller.py`)
Unlike static movements, the `ContinuousGrabController` maintains active centering while moving forward. This compensates for any mechanical inconsistencies or object movement.

### The Feedback Loop
While moving towards the object, the system continuously polls the camera:
1. **Distance Estimation**: Get real-time Z-distance (cm) from `distance_estimator.py`.
2. **X-Axis Fine-Tuning**: If the object drifts horizontally during the approach, the Base servo adjusts slightly (`base_correction`) to keep it centered.
3. **IK-Based Approach**: The Shoulder and Elbow angles are calculated specifically for the current Z-distance using the `visual_ik_solver.py`.

## Approach Workflow
- **Start**: Open gripper to 170°.
- **Iterative Movement**:
    - Calculate required Shoulder/Elbow angles for current distance.
    - Adjust Base for X-alignment.
    - Move servos and wait for a small stabilization delay (0.15s).
- **Grab Threshold**: Once `distance_cm` is less than or equal to the `grab_distance` (approx. 2.0cm), the approach stops.

## Grabbing and Lifting
1. **Close Gripper**: Once in range, the gripper closes to 120° (tuned for the test cube).
2. **Wait**: A delay of 0.8s ensures the gripper has fully clamped the object.
3. **Lift**: The shoulder servo increases its angle (moves up) by 15° to lift the object off the surface.

## Safety & Error Handling
- **Reachability Check**: Before every move, `check_reachability()` ensures the target distance is physically possible for the arm.
- **Timeouts**: If the object is lost for too long or the approach takes more than 30 seconds, the operation fails and the arm stops.
- **Angle Clamping**: All calculated IK angles are clamped to safe ranges (e.g., Elbow is capped at 150° maximum) to prevent mechanical binding.
