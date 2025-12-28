"""
Manual Keyboard Control for Shoulder and Elbow

Controls:
- W: Increase Shoulder angle
- S: Decrease Shoulder angle
- A: Decrease Elbow angle
- D: Increase Elbow angle
- Q: Quit
"""

import sys
import os
from hardware.robot_driver import RobotArm
import msvcrt  # Windows keyboard input

def main():
    print("🎮 Manual Keyboard Control")
    print("=" * 50)
    print("Controls:")
    print("  W/S: Shoulder Up/Down")
    print("  A/D: Elbow Down/Up")
    print("  Q: Quit")
    print("=" * 50)
    
    # Initialize robot
    # Change to simulation_mode=False if connected to hardware
    robot = RobotArm(simulation_mode=False, port='COM4')
    
    # Starting position
    base = 90
    shoulder = 100
    elbow = 130
    pitch = 90
    roll = 12
    gripper = 170
    
    # Move to initial position
    robot.move_to([base, shoulder, elbow, pitch, roll, gripper])
    print(f"\n✅ Initial Position: Shoulder={shoulder}°, Elbow={elbow}°")
    
    step_size = 1  # Degrees per key press
    
    try:
        while True:
            print(f"\rShoulder: {shoulder:3d}° | Elbow: {elbow:3d}°  ", end='', flush=True)
            
            # Check for key press (Windows)
            if msvcrt.kbhit():
                key = msvcrt.getch().decode('utf-8').lower()
                
                moved = False
                
                if key == 'w':
                    shoulder = min(180, shoulder + step_size)
                    moved = True
                    print(f"\n⬆️  Shoulder increased to {shoulder}°")
                    
                elif key == 's':
                    shoulder = max(0, shoulder - step_size)
                    moved = True
                    print(f"\n⬇️  Shoulder decreased to {shoulder}°")
                    
                elif key == 'd':
                    elbow = min(180, elbow + step_size)
                    moved = True
                    print(f"\n➡️  Elbow increased to {elbow}°")
                    
                elif key == 'a':
                    elbow = max(0, elbow - step_size)
                    moved = True
                    print(f"\n⬅️  Elbow decreased to {elbow}°")
                    
                elif key == 'q':
                    print("\n\n👋 Exiting...")
                    break
                
                # Send command if moved
                if moved:
                    robot.move_to([base, shoulder, elbow, pitch, roll, gripper])
                    
    except KeyboardInterrupt:
        print("\n\n🛑 Interrupted by user.")
    
    finally:
        print("Shutdown complete.")

if __name__ == "__main__":
    main()
