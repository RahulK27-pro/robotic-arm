# Phase 8: Stabilization and Tuning

## 1. Problem Identification
The visual servoing system experienced severe oscillation ("hunting") during the alignment and stalking phases.
- **Symptoms**: The robot arm would swing wildly past the center, correct, and swing back, never settling on the target.
- **Root Causes**:
    1.  **Latency Stacking**: The visual servoing loop was running faster than the camera frame rate (~30fps vs ~10fps). The robot would read the *same* delayed frame multiple times, effectively reacting to an error that no longer existed (e.g., "Move Left 50px" x 4 times = Move Left 200px).
    2.  **High Gain**: The Proportional Gain (0.04) was too aggressive for the physical system's inertia.
    3.  **Sensor Noise**: Small fluctuations in the bounding box caused constant micro-corrections.

## 2. Implemented Solutions

### A. The "Sense-Act-Wait" Protocol (Fixing Latency)
To solve the "Blind Stacking" issue, we implemented a timestamp-based synchronization between the Camera and the Servoing Agent.

*   **Camera Update**: Added a high-precision `timestamp` to every detection object in `camera.py`.
*   **Servoing Logic**: In `visual_servoing.py`, the loop now explicitly checks this timestamp.
    ```python
    if det_time <= last_processed_time:
        time.sleep(0.05)
        continue # Wait for FRESH frame
    ```
    **Result**: The robot moves **exactly once** per camera frame. It never "double-dipps" on stale data.

### B. Adaptive Control Strategy
We replaced fixed gains with an intelligent adaptive controller:

1.  **Adaptive Gain**:
    *   **High Gain (0.01)**: Active when Error > 100px. Used for coarse approach.
    *   **Low Gain (0.005)**: Active when Error < 100px. Used for precision alignment (Stalking).
2.  **Expanded Deadzone**:
    *   Increased from `20px` to **`30px`**. The robot stops correcting earlier, reducing the chance of over-correcting on noise.
3.  **Hysteresis (Anti-Stiction)**:
    *   **Min-Move Threshold**: 1.0 degree.
    *   Moves < 0.5° are ignored to prevent jitter.
    *   Moves 0.5°-1.0° are boosted to 1.0° to ensure the servo overcomes static friction.

### C. Ultra-Stable Tuning Parameters
Per user request, we applied extremely conservative limits to guarantee stability:

| Parameter | Old Value | **New Value** | Effect |
| :--- | :--- | :--- | :--- |
| **Max Step (Deg)** | 2.0° | **1.0°** | Prevents large jumps between frames. |
| **Max Reach Step** | 2.0 cm | **1.0 cm** | Slows down the stalking approach. |
| **Gain (High)** | 0.04 | **0.01** | Reduces reaction strength by 75%. |
| **Gain (Stalk)** | 0.01 | **0.005** | Extremely gentle corrections during approach. |

## 3. Future Improvements
- **Blind Commit Tuning**: Fine-turning the blind zone threshold (currently 5.0cm).
- **Gripper Timing**: synchronizing the close action with the final push.
