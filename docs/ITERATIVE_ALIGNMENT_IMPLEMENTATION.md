# Iterative Alignment Implementation Guide

## Overview
This document summarizes the **iterative step-based alignment** approach implemented for X-axis control in the visual servoing system. This same pattern can be replicated for Y-axis (elbow) alignment.

---

## Core Concept

### Stop-and-Go Philosophy
Instead of continuously correcting errors while the robot is in motion, the system:
1. **Stops** the robot
2. **Measures** the error from the camera/vision system
3. **Calculates** a correction step
4. **Moves** by a small increment (e.g., 1 degree)
5. **Waits** for stabilization
6. **Repeats** until the error is minimized

This ensures accurate error measurement and prevents overshoot/oscillation.

---

## X-Axis Implementation (Base Servo)

### Location
File: `backend/visual_servoing.py`  
Function: `_servoing_loop()` - Stage 2: ALIGN

### Implementation Details

#### 1. Entry Condition
```python
# Robot has detected an object
det = detections[0]
error_x = det['error_x']  # Horizontal pixel error from center
```

#### 2. Iterative Loop Structure
```python
while abs(error_x) > 20:  # Threshold: 20 pixels
    if not self.running: break
    
    # Calculate step direction
    step = 1.0 if error_x > 0 else -1.0
    
    # Apply step
    current_base += step
    current_base = max(0, min(180, current_base))  # Safety clamp
    
    # Move robot
    self.robot.move_to([current_base, shoulder, elbow, pitch, roll, gripper])
    
    # Wait for stabilization
    time.sleep(1.0)
    
    # Get fresh detection
    detections = self.camera.last_detection
    if not detections:
        break  # Lost object
    
    # Update error
    error_x = detections[0]['error_x']
```

#### 3. Direction Logic
- **`error_x > 0`**: Object is LEFT of center → Camera needs to move LEFT → **Increase base angle** (`step = +1.0`)
- **`error_x < 0`**: Object is RIGHT of center → Camera needs to move RIGHT → **Decrease base angle** (`step = -1.0`)

> **Note**: Direction logic depends on your servo mounting orientation. If the robot moves **away** from the object, invert the step signs.

#### 4. Key Parameters
| Parameter | Value | Purpose |
|-----------|-------|---------|
| Error Threshold | 20 pixels | Defines "aligned" state |
| Step Size | 1.0 degrees | Movement increment per iteration |
| Stabilization Delay | 1.0 seconds | Wait time after movement |

---

## Applying to Y-Axis (Elbow Servo)

### Conceptual Mapping

| Aspect | X-Axis (Base) | Y-Axis (Elbow) |
|--------|---------------|----------------|
| **Error Source** | `error_x` (horizontal pixels) | `error_y` (vertical pixels) |
| **Servo** | Base servo | Elbow servo |
| **Variable** | `current_base` | `current_elbow` |
| **Direction** | +/- 1 degree | +/- 1 degree |

### Implementation Template for Y-Axis

```python
# Stage 2: ALIGN - Y-Axis Alignment Loop
while abs(error_y) > 20:  # Vertical alignment threshold
    if not self.running: break
    
    # Direction Logic:
    # error_y > 0: Object is ABOVE center → Camera needs UP → Adjust elbow
    # error_y < 0: Object is BELOW center → Camera needs DOWN → Adjust elbow
    step = 1.0 if error_y > 0 else -1.0
    
    # Apply to elbow
    current_elbow += step
    current_elbow = max(0, min(180, current_elbow))  # Safety limits
    
    # Move robot
    self.robot.move_to([current_base, current_shoulder, current_elbow, WRIST_PITCH, WRIST_ROLL, GRIPPER])
    
    # Wait for stabilization
    time.sleep(1.0)
    
    # Get fresh detection
    detections = self.camera.last_detection
    if not detections:
        print("⚠️ Lost Object during Y alignment!")
        break
    
    det = detections[0]
    error_y = det['error_y']
    
    # Telemetry update
    self.current_telemetry["correction_y"] = step
    print(f"[Y-Align Loop] ErrY: {error_y:.0f} → Step: {step:.1f} → Elbow: {current_elbow:.1f}")
```

### Integration Strategy

#### Option 1: Sequential (X then Y)
```python
# STAGE 2: ALIGN

# First align X-axis
while abs(error_x) > 20:
    # ... X alignment loop ...

# Then align Y-axis
while abs(error_y) > 20:
    # ... Y alignment loop ...

# Both aligned, proceed to approach
```

#### Option 2: Simultaneous (Both axes in one loop)
```python
# STAGE 2: ALIGN
while abs(error_x) > 20 or abs(error_y) > 20:
    if abs(error_x) > 20:
        # Correct X
        step_x = 1.0 if error_x > 0 else -1.0
        current_base += step_x
    
    if abs(error_y) > 20:
        # Correct Y
        step_y = 1.0 if error_y > 0 else -1.0
        current_elbow += step_y
    
    # Move both servos
    self.robot.move_to([current_base, shoulder, current_elbow, ...])
    
    # Wait and refresh
    time.sleep(1.0)
    detections = self.camera.last_detection
    # ... update errors ...
```

---

## Tuning Guidelines

### If the robot oscillates:
- **Increase stabilization delay** (e.g., 1.5s)
- **Reduce step size** (e.g., 0.5 degrees)
- **Tighten error threshold** (e.g., 15 pixels)

### If alignment is too slow:
- **Decrease stabilization delay** (e.g., 0.5s)
- **Increase step size** (e.g., 2.0 degrees)
- **Use adaptive steps**: Larger steps when error is large

### If servo direction is wrong:
- **Invert the step sign**:
  ```python
  step = -1.0 if error_y > 0 else 1.0  # Flip signs
  ```

---

## Current Status

### X-Axis (Base)
- ✅ Implemented with ANFIS prediction
- ✅ Falls back to simple 1-degree steps
- ✅ Stop-and-go behavior confirmed
- ✅ Direction corrected via user testing

### Y-Axis (Elbow)
- ⏳ **Pending Implementation**
- Use this document as reference
- Test direction logic carefully
- Start with conservative parameters (small steps, long delays)

---

## Testing Checklist

When implementing Y-axis:
- [ ] Verify `error_y` is calculated correctly in camera/detection code
- [ ] Test step direction with small movements
- [ ] Confirm servo limits (0-180°) are respected
- [ ] Check stabilization delay is sufficient
- [ ] Observe alignment in real-time
- [ ] Validate transition to APPROACH stage after alignment

---

## Code References

### Main Files
- **Visual Servoing Logic**: [`visual_servoing.py`](file:///d:/Projects/Big%20Projects/robotic-arm/backend/visual_servoing.py#L164-L204)
- **Robot Driver**: `hardware/robot_driver.py`
- **Camera/Detection**: `camera.py`

### Key Variables
- `error_x`: Horizontal pixel error (-640 to +640)
- `error_y`: Vertical pixel error (-480 to +480)
- `current_base`: Base servo angle (0-180°)
- `current_elbow`: Elbow servo angle (0-180°)

---

## Notes

- The **stabilization delay** is critical. Camera feed and servo movement both need time to settle.
- Always include **object loss detection** to exit the loop gracefully.
- **Telemetry updates** help debug and monitor progress.
- Consider logging alignment time for performance tuning.

---

**Last Updated**: 2025-12-28  
**Author**: Visual Servoing Implementation Team
