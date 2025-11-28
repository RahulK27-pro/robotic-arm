import requests
import json

URL = "http://localhost:5000/process_command"

# Mock data simulating what the frontend + camera would send
# Note: In the real app, the camera state is internal to the backend.
# But for this test, we are relying on the backend to have some state OR 
# we can just test the LLM part if we can't easily mock the camera state from outside.
# actually, the `process_command` endpoint uses `global_camera.last_detection`.
# We need a way to set that state for testing.
# `app.py` has `/set_target_color` but that just sets what to look for.
# It doesn't force a detection result.
# However, we can use the fact that `process_command` takes the command.
# Wait, `app.py` constructs `vision_state` from `global_camera`.
# If `global_camera` sees nothing, `vision_state` is empty.
# The LLM might complain.

# To properly test this without a real camera, we might need to mock `global_camera` in `app.py` 
# OR just rely on the LLM handling empty state gracefully (which I implemented).
# BUT the user wants to test the "Brain".
# Let's try to inject a fake detection into `global_camera` if possible, 
# or just modify `app.py` temporarily? No, that's risky.

# Alternative: The user asked for a "Mock/Simulation Mode".
# Maybe I should have added a way to inject mock vision data?
# The prompt didn't explicitly ask for a mock vision injection endpoint.
# But I can probably just run the `brain/llm_engine.py` and `brain/kinematics.py` directly in a test script
# to verify the logic, bypassing Flask for the deep logic test.
# Then test Flask just for connectivity.

# Let's do a unit test style verification first.

import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from brain.kinematics import solve_angles
from brain.llm_engine import process_command
from hardware.robot_driver import RobotArm

def test_kinematics():
    print("Testing Kinematics...")
    # Test a known reachable point
    # x=10, y=10, z=10
    try:
        angles = solve_angles(10, 10, 10)
        print(f"Angles for (10,10,10): {angles}")
    except Exception as e:
        print(f"Kinematics Error: {e}")

def test_llm():
    print("\nTesting LLM Engine...")
    # Mock vision state
    vision_state = {
        "red_cube": [15, 0, 0],
        "blue_cube": [25, 5, 0]
    }
    command = "Pick up the red cube"
    
    # Note: This requires GROQ_API_KEY to be set in env
    try:
        response = process_command(command, vision_state)
        print("LLM Response:")
        print(json.dumps(response, indent=2))
    except Exception as e:
        print(f"LLM Error: {e}")

def test_driver():
    print("\nTesting Robot Driver...")
    arm = RobotArm(simulation_mode=True)
    arm.move_to([90, 45, 45, 0, 0, 0])

if __name__ == "__main__":
    test_kinematics()
    test_driver()
    test_llm()
