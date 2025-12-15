"""
Orientation Tester for Visual Servoing
This script helps you find the correct sign mapping for your robot.
"""

print("""
╔════════════════════════════════════════════════════════════╗
║     VISUAL SERVOING ORIENTATION TESTER                     ║
╚════════════════════════════════════════════════════════════╝

This will help you find the correct direction mapping.

INSTRUCTIONS:
1. Make sure your robot is at Home Position (0, 15, 15)
2. Place a bottle in view of the camera
3. We'll test each direction one at a time
4. Watch which way the robot ACTUALLY moves
5. Record the results below

═══════════════════════════════════════════════════════════════
""")

# Test configurations to try
tests = [
    {
        "name": "Test 1: Object LEFT (error_x = +100)",
        "error_x": 100,
        "error_y": 0,
        "expected": "Robot should move LEFT to center the object"
    },
    {
        "name": "Test 2: Object RIGHT (error_x = -100)",
        "error_x": -100,
        "error_y": 0,
        "expected": "Robot should move RIGHT to center the object"
    },
    {
        "name": "Test 3: Object UP (error_y = +100)",
        "error_x": 0,
        "error_y": 100,
        "expected": "Robot should move FORWARD/UP to center the object"
    },
    {
        "name": "Test 4: Object DOWN (error_y = -100)",
        "error_x": 0,
        "error_y": -100,
        "expected": "Robot should move BACK/DOWN to center the object"
    }
]

print("STEP 1: Enable Diagnostic Mode")
print("─────────────────────────────────────────────────────────")
print("In visual_servoing.py, set:")
print("    self.DIAGNOSTIC_MODE = True")
print("")

print("STEP 2: Run each test")
print("─────────────────────────────────────────────────────────")
for i, test in enumerate(tests, 1):
    print(f"\n{test['name']}")
    print(f"Expected: {test['expected']}")
    print(f"In visual_servoing.py, uncomment line for error_x={test['error_x']}, error_y={test['error_y']}")
    print("Run: curl -X POST http://localhost:5000/start_servoing ...")
    result = input(f"Did robot move correctly? (y/n): ").strip().lower()
    tests[i-1]['result'] = result == 'y'

print("\n═══════════════════════════════════════════════════════════")
print("RESULTS ANALYSIS")
print("═══════════════════════════════════════════════════════════\n")

x_correct = tests[0]['result'] and tests[1]['result']
y_correct = tests[2]['result'] and tests[3]['result']

print(f"X-axis behavior: {'✅ CORRECT' if x_correct else '❌ NEEDS FLIP'}")
print(f"Y-axis behavior: {'✅ CORRECT' if y_correct else '❌ NEEDS FLIP'}")

print("\n═══════════════════════════════════════════════════════════")
print("RECOMMENDED FIX")
print("═══════════════════════════════════════════════════════════\n")

print("In visual_servoing.py around line 103-104, change to:")
print("")

if not x_correct and not y_correct:
    print("move_x_cm = (error_x_px * GAIN_X)  # FLIPPED")
    print("move_y_cm = -(error_y_px * GAIN_Y)  # FLIPPED")
elif not x_correct:
    print("move_x_cm = (error_x_px * GAIN_X)  # FLIPPED")
    print("move_y_cm = (error_y_px * GAIN_Y)  # UNCHANGED")
elif not y_correct:
    print("move_x_cm = -(error_x_px * GAIN_X)  # UNCHANGED")
    print("move_y_cm = -(error_y_px * GAIN_Y)  # FLIPPED")
else:
    print("move_x_cm = -(error_x_px * GAIN_X)  # UNCHANGED")
    print("move_y_cm = (error_y_px * GAIN_Y)  # UNCHANGED")
    print("\n✅ Your signs are already correct!")

print("\n═══════════════════════════════════════════════════════════")
print("After making changes:")
print("1. Set DIAGNOSTIC_MODE = False")
print("2. Restart backend")
print("3. Test with real object tracking")
print("═══════════════════════════════════════════════════════════\n")
