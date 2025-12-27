"""
Test Script to Determine Base Servo Direction

This script helps determine if increasing the base servo angle moves the camera LEFT or RIGHT.

Run this script and manually observe which direction the camera rotates.
"""

import sys
import time
sys.path.append('d:/Projects/Big Projects/robotic-arm/backend')

from hardware.robot_driver import RobotArm

def test_base_direction():
    """Test which direction base servo rotates when angle increases"""
    
    print("=" * 60)
    print("BASE SERVO DIRECTION TEST")
    print("=" * 60)
    print()
    print("This will move the base servo to test which direction is which.")
    print()
    
    robot = RobotArm()
    time.sleep(1)
    
    # Start at center
    print("1. Moving to CENTER position (base = 90°)...")
    robot.move_to([90, 100, 140, 90, 12, 155])
    time.sleep(2)
    
    # Move to LOWER angle
    print("\n2. Moving to LOWER angle (base = 60°)...")
    print("   OBSERVE: Did the camera view rotate LEFT or RIGHT?")
    robot.move_to([60, 100, 140, 90, 12, 155])
    time.sleep(3)
    
    # Return to center
    print("\n3. Returning to CENTER (base = 90°)...")
    robot.move_to([90, 100, 140, 90, 12, 155])
    time.sleep(2)
    
    # Move to HIGHER angle
    print("\n4. Moving to HIGHER angle (base = 120°)...")
    print("   OBSERVE: Did the camera view rotate LEFT or RIGHT?")
    robot.move_to([120, 100, 140, 90, 12, 155])
    time.sleep(3)
    
    # Return to center
    print("\n5. Returning to CENTER (base = 90°)...")
    robot.move_to([90, 100, 140, 90, 12, 155])
    time.sleep(1)
    
    print("\n" + "=" * 60)
    print("TEST COMPLETE - Please report your observations:")
    print("=" * 60)
    print()
    print("When base angle DECREASED (90° → 60°):")
    print("  Did camera view rotate LEFT or RIGHT? ___________")
    print()
    print("When base angle INCREASED (90° → 120°):")
    print("  Did camera view rotate LEFT or RIGHT? ___________")
    print()
    print("Based on this, we can determine the correct sign for corrections.")
    print("=" * 60)

if __name__ == "__main__":
    test_base_direction()
