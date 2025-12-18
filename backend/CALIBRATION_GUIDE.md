# Distance Calibration & Grab Testing Guide

## Issue: Distance Off by 10-12cm

The distance estimation is showing incorrect values because the focal length needs to be calibrated with your specific camera setup.

## Solution: Calibrate Focal Length

### Step 1: Run Calibration Tool

```bash
cd backend
python calibrate_camera.py
```

### Step 2: Follow Instructions

1. **Place object at known distance**
   - Use a ruler to measure exactly 20cm from camera lens to your 3cm cube
   - Place cube at this measured distance

2. **Enter measurements**
   ```
   Enter measured distance (cm): 20
   Enter object width (cm) [default: 3.0]: 3
   ```

3. **Capture calibration**
   - Point camera at cube
   - Press `c` to capture when cube is detected
   - Script will calculate correct focal length

4. **Update focal length**
   - Script will show calculated value (e.g., `FOCAL_LENGTH_DEFAULT = 1650`)
   - Update in `backend/camera.py` or use override parameter

### Step 3: Test Distance Accuracy

After calibration:
1. Place cube at 20cm → Should show ~20cm
2. Place cube at 30cm → Should show ~30cm
3. Place cube at 40cm → Should show ~40cm

**Tolerance**: ±2cm is acceptable

---

## Testing Grab Functionality

### Quick Test via API

```bash
# Start visual grab
curl -X POST http://localhost:5000/start_visual_grab \
  -H "Content-Type: application/json" \
  -d '{"target_object": "bottle"}'

# Monitor status
curl http://localhost:5000/visual_grab_status
```

### Expected Behavior

**Phase 1: Alignment (10-30 seconds)**
- Base rotates to center object
- Elbow adjusts for Y-axis
- Status: `"state": "aligning"`

**Phase 2: Approach (15-30 seconds)**
- Gripper opens (170°)
- Shoulder and elbow move based on distance
- **Only shoulder and elbow move** (base stays fixed)
- When distance <= 2cm: Gripper closes (120°)
- Status: `"state": "approaching"`

**Phase 3: Lift (2 seconds)**
- Shoulder lifts 15°
- Object is lifted
- Status: `"state": "complete"`

### What to Watch

1. **Distance Display**: Should decrease as arm approaches
2. **Servo Movement**: Only shoulder (servo 1) and elbow (servo 2) should move during approach
3. **Gripper**: Opens at start, closes when distance shows ~2cm
4. **Base**: Should NOT move during approach (stays from alignment)

---

## Troubleshooting

### Distance still wrong after calibration

**Check**:
- Camera resolution is 1280x720 (check terminal output)
- Object width is correct (3cm for cube)
- Measured distance is accurate (use ruler)

**Fix**:
- Recalibrate with different distance (try 30cm)
- Average multiple calibrations

### Gripper closes too early/late

**Adjust threshold** in `grab_controller.py`:
```python
# Line ~255
if current_distance <= 2.0:  # Change this value
```

### Arm moves too fast/slow

**Adjust sleep time** in `grab_controller.py`:
```python
# Line ~302
time.sleep(0.3)  # Increase for slower, decrease for faster
```

### Object out of reach

**Check**:
- Object distance < 39cm
- Object is centered before approach starts
- Distance estimation is accurate

---

## Manual Focal Length Override

If you know the correct focal length, you can override it in `app.py`:

```python
# Line 19
global_camera = VideoCamera(
    detection_mode='yolo',
    focal_length_override=1650  # Your calibrated value
)
```

Then restart backend:
```bash
python app.py
```

---

## Expected Console Output

```
🚀 Visual Grab started for 'bottle'
==========================================================
🎯 VISUAL GRAB WORKFLOW - STARTING
==========================================================

📍 PHASE 1: X/Y ALIGNMENT
------------------------------------------------------------
✅ Object centered!

🚀 PHASE 2: Z-AXIS APPROACH
------------------------------------------------------------
   Opening gripper...
   Iteration 0: Distance = 35.2cm
      → Moving: Shoulder=42.3°, Elbow=95.1°
   Iteration 1: Distance = 32.8cm
      → Moving: Shoulder=45.1°, Elbow=88.3°
   ...
   Iteration 15: Distance = 1.8cm
✅ Ready to grab! Distance: 1.8cm
   🤏 Closing gripper...

📦 PHASE 3: LIFT OBJECT
------------------------------------------------------------
   Lifting...
✅ Grab complete!
==========================================================
✅ VISUAL GRAB COMPLETE!
==========================================================
```

---

## Next Steps

1. ✅ Calibrate focal length
2. ✅ Test distance accuracy
3. ✅ Test grab with real object
4. ⏳ Fine-tune thresholds if needed
5. ⏳ Add frontend button for easy triggering
