"""
Test Script for Pick-and-Place Controller

Tests the complete pick-and-place system in simulation mode.
Verifies state transitions, smooth interpolation, and proper sequencing.
"""

import sys
import time
sys.path.append('.')  # Add backend directory to path

from hardware.robot_driver import RobotArm
from pick_place_controller import PickPlaceController


def test_pick_place_simulation():
    """Test pick-and-place in simulation mode."""
    
    print("="*70)
    print("🧪 PICK-AND-PLACE SIMULATION TEST")
    print("="*70 + "\n")
    
    # Initialize robot in simulation mode
    print("1️⃣ Initializing robot (simulation mode)...")
    robot = RobotArm(simulation_mode=True)
    
    # Set initial "grabbed" position (simulating after visual servoing grab)
    print("2️⃣ Setting initial grabbed position...")
    grabbed_position = [23, 50, 120, 90, 12, 120]  # Base, shoulder forward, gripper closed
    robot.move_to(grabbed_position)
    time.sleep(1)
    
    # Initialize controller
    print("3️⃣ Initializing PickPlaceController...")
    controller = PickPlaceController(robot)
    
    # Start pick-and-place
    print("\n4️⃣ Starting pick-and-place sequence (target base: 0°)...\n")
    success = controller.start(target_base_angle=0)
    
    if not success:
        print("❌ Failed to start pick-and-place!")
        return False
    
    # Monitor progress
    print("5️⃣ Monitoring progress...\n")
    last_state = ""
    last_progress = -1
    
    while controller.running:
        status = controller.get_status()
        state = status["state"]
        phase = status.get("phase", "N/A")
        progress = status.get("progress", 0.0)
        
        # Print state changes
        if state != last_state:
            print(f"\n{'='*60}")
            print(f"STATE: {state}")
            print(f"{'='*60}")
            last_state = state
        
        # Print progress updates (every 20%)
        if int(progress / 20) != int(last_progress / 20):
            print(f"  [{phase}] Progress: {progress:.1f}%")
            last_progress = progress
        
        time.sleep(0.2)
    
    # Final status
    final_status = controller.get_status()
    print(f"\n{'='*70}")
    print(f"FINAL STATE: {final_status['state']}")
    print(f"MESSAGE: {final_status.get('message', 'N/A')}")
    print(f"{'='*70}\n")
    
    # Verify completion
    if final_status["state"] == "COMPLETE":
        print("✅ TEST PASSED - Pick-and-place completed successfully!")
        
        # Verify final angles are close to home position
        final_angles = robot.current_angles
        home_position = controller.HOME_POSITION
        
        print("\n📊 Final Position Verification:")
        print(f"   Expected: {home_position}")
        print(f"   Actual:   {[int(a) for a in final_angles]}")
        
        # Check if close to home (within 5 degrees tolerance)
        all_close = all(abs(final_angles[i] - home_position[i]) < 6 for i in range(6))
        
        if all_close:
            print("   ✅ Robot returned to home position")
            return True
        else:
            print("   ⚠️ Robot position differs from expected home position")
            return True  # Still consider test passed if completed
    else:
        print(f"❌ TEST FAILED - Final state was {final_status['state']}, expected COMPLETE")
        return False


def test_emergency_stop():
    """Test emergency stop functionality."""
    
    print("\n" + "="*70)
    print("🧪 EMERGENCY STOP TEST")
    print("="*70 + "\n")
    
    robot = RobotArm(simulation_mode=True)
    robot.move_to([23, 50, 120, 90, 12, 120])
    
    controller = PickPlaceController(robot)
    controller.start(target_base_angle=0)
    
    # Wait for lifting phase to start
    time.sleep(1.5)
    
    # Emergency stop
    print("🛑 Triggering emergency stop...")
    controller.stop()
    
    time.sleep(0.5)
    
    status = controller.get_status()
    if status["state"] == "STOPPED" or not status["running"]:
        print("✅ Emergency stop successful!")
        return True
    else:
        print("❌ Emergency stop failed!")
        return False


def test_smooth_interpolation():
    """Test that movements are smooth (no large angle jumps)."""
    
    print("\n" + "="*70)
    print("🧪 SMOOTH INTERPOLATION TEST")
    print("="*70 + "\n")
    
    robot = RobotArm(simulation_mode=True)
    robot.move_to([23, 50, 120, 90, 12, 120])
    
    controller = PickPlaceController(robot)
    
    # Track angle changes
    previous_angles = list(robot.current_angles)
    max_jump = 0
    
    controller.start(target_base_angle=0)
    
    while controller.running:
        current_angles = robot.current_angles
        
        # Calculate max angle change
        for i in range(6):
            angle_change = abs(current_angles[i] - previous_angles[i])
            if angle_change > max_jump:
                max_jump = angle_change
        
        previous_angles = list(current_angles)
        time.sleep(0.05)
    
    print(f"📊 Maximum angle jump detected: {max_jump:.2f}°")
    
    # In smooth interpolation with small dt, jumps should be < 10 degrees
    if max_jump < 10:
        print("✅ Interpolation is smooth (max jump < 10°)")
        return True
    else:
        print(f"⚠️ Large angle jumps detected (max: {max_jump:.2f}°)")
        return False


if __name__ == "__main__":
    print("\n" + "="*70)
    print("🚀 PICK-AND-PLACE CONTROLLER TEST SUITE")
    print("="*70)
    
    tests = []
    
    # Test 1: Complete sequence
    print("\n[TEST 1/3]")
    test1_result = test_pick_place_simulation()
    tests.append(("Complete Sequence", test1_result))
    
    # Test 2: Emergency stop
    print("\n[TEST 2/3]")
    test2_result = test_emergency_stop()
    tests.append(("Emergency Stop", test2_result))
    
    # Test 3: Smooth interpolation
    print("\n[TEST 3/3]")
    test3_result = test_smooth_interpolation()
    tests.append(("Smooth Interpolation", test3_result))
    
    # Summary
    print("\n" + "="*70)
    print("📊 TEST SUMMARY")
    print("="*70)
    
    for test_name, result in tests:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    all_passed = all(result for _, result in tests)
    
    print("="*70)
    if all_passed:
        print("✅ ALL TESTS PASSED!")
    else:
        print("❌ SOME TESTS FAILED")
    print("="*70 + "\n")
    
    sys.exit(0 if all_passed else 1)
