from hardware.robot_driver import RobotArm
import time

def test_smooth_motion():
    print("🧪 Testing Cinematic Movement (S-Curve)...")
    
    # Initialize in simulation mode to verify logic first
    # Or hardware mode if user has it connected (default checks connection)
    arm = RobotArm(simulation_mode=True) 
    
    start_pos = [0, 130, 130, 90, 12, 170]
    target_pos = [90, 90, 90, 90, 90, 170]
    
    print("\n1. Resetting to Start")
    arm.move_to(start_pos)
    time.sleep(1)
    
    print("\n2. Executing Smooth Move (2.0s duration)")
    start_time = time.time()
    arm.move_smooth(target_pos, duration=2.0)
    end_time = time.time()
    
    print(f"\n⏱️ Actual Duration: {end_time - start_time:.4f}s")
    
    # Check final position
    current = arm.current_angles
    # Round for float comparison
    current_check = [round(x) for x in current]
    target_check = [round(x) for x in target_pos]
    
    if current_check == target_check:
        print("✅ SUCCESS: Target reached accurately.")
    else:
        print(f"❌ FAILURE: Final position mismatch. Got {current_check}, Expected {target_check}")

if __name__ == "__main__":
    test_smooth_motion()
