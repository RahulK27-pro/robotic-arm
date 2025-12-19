# Quick Test Guide - Continuous Grab

## The Issue

You're currently using **visual servoing** which only centers the object.
You need to use the **continuous grab** endpoint instead.

## Current Behavior (Visual Servoing Only)

```bash
# This ONLY centers, doesn't grab
POST /start_servoing {"target_object": "bottle"}
```

**Result**: Object gets centered and stays there ✓ (This is what you're seeing)

## Correct Usage (Continuous Grab)

```bash
# This centers AND grabs
POST /start_continuous_grab {"target_object": "bottle"}
```

**Result**: 
1. Centers object (Phase 1)
2. Moves forward while maintaining center (Phase 2)
3. Closes gripper (Phase 3)
4. Lifts object (Phase 4)

## How to Test

### Stop Current Servoing
```bash
curl -X POST http://localhost:5000/stop_servoing
```

### Start Continuous Grab
```bash
curl -X POST http://localhost:5000/start_continuous_grab \
  -H "Content-Type: application/json" \
  -d '{"target_object": "bottle"}'
```

### Monitor Status
```bash
curl http://localhost:5000/continuous_grab_status
```

## Expected Console Output

```
🎯 CONTINUOUS GRAB WORKFLOW - STARTING
==========================================================

📍 PHASE 1: CENTERING OBJECT
------------------------------------------------------------
Opening gripper...
Centering... ErrX:+45px ErrY:-12px
Centering... ErrX:+32px ErrY:-8px
Centered! (1/5)
Centered! (2/5)
Centered! (3/5)
Centered! (4/5)
Centered! (5/5)
✅ Object fully centered! Starting approach...

🚀 PHASE 2: APPROACHING (with continuous alignment)
------------------------------------------------------------
[  0] Dist: 35.2cm | ErrX:  +2px | ErrY:  -1px | Centered:✓ | Base:45°→45° | Sh:42° El:95°
[  1] Dist: 32.8cm | ErrX:  +3px | ErrY:  +1px | Centered:✓ | Base:45°→45° | Sh:45° El:88°
[  2] Dist: 30.1cm | ErrX:  -1px | ErrY:  +2px | Centered:✓ | Base:45°→45° | Sh:48° El:82°
...
[ 15] Dist:  2.5cm | ErrX:  +1px | ErrY:  -1px | Centered:✓ | Base:45°→45° | Sh:78° El:45°
[ 16] Dist:  1.8cm | ErrX:  +0px | ErrY:  +0px | Centered:✓ | Base:45°→45° | Sh:82° El:38°

✅ OBJECT WITHIN REACH! Distance: 1.8cm

🤏 PHASE 3: CLOSING GRIPPER
------------------------------------------------------------

📦 PHASE 4: LIFTING OBJECT
------------------------------------------------------------

✅ CONTINUOUS GRAB COMPLETE!
```

## Troubleshooting

### "Grab already in progress"
Stop existing operations first:
```bash
curl -X POST http://localhost:5000/stop_servoing
curl -X POST http://localhost:5000/stop_continuous_grab
```

### Object not detected
- Ensure object is in camera view
- Check distance estimation is working
- Verify object name matches (e.g., 'bottle', 'cup', 'cube')

### Centering timeout
- Increase timeout in `continuous_grab_controller.py` line 144:
  ```python
  centering_timeout = 30.0  # Increase from 15.0
  ```

### Approach not starting
- Check console for "✅ Object fully centered! Starting approach..."
- If not appearing, centering phase is still running
- Verify `required_centered_frames` is not too high (currently 5)
