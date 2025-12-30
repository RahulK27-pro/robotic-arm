"""
Hybrid 2-Axis Data Collection Script

Workflow:
1. Auto-center object on X-axis using ANFIS
2. Lock Base servo
3. Capture [Pixel_Y, Depth] as input
4. User manually adjusts Shoulder/Elbow to reach object
5. Save [Pixel_Y, Depth, Shoulder, Elbow] to CSV

Controls during manual reach:
- W/S: Shoulder Up/Down
- A/D: Elbow Down/Up  
- SPACE: Save current position
- Q: Quit
"""

import cv2
import time
import msvcrt
import csv
import os
from hardware.robot_driver import RobotArm
from camera import VideoCamera
import torch
from brain.anfis_pytorch import ANFIS

# Configuration
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TOOLS_DIR = os.path.join(SCRIPT_DIR, "tools")
OUTPUT_FILE = os.path.join(TOOLS_DIR, "final_data.csv")
FIXED_WRIST_ANGLE = 90
FIXED_ROLL = 12
GRIPPER_OPEN = 170
MAX_ALIGNMENT_ITERATIONS = 50

class HybridDataCollector:
    def __init__(self):
        # Initialize hardware
        self.robot = RobotArm(simulation_mode=False, port='COM4')
        self.camera = VideoCamera(detection_mode='yolo')
        
        # Load ANFIS for X-axis alignment
        self.brain_x = self._load_anfis()
        
        # Ensure tools directory exists
        os.makedirs(TOOLS_DIR, exist_ok=True)
        
        # Initialize CSV
        if not os.path.exists(OUTPUT_FILE):
            with open(OUTPUT_FILE, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['pixel_y', 'depth_cm', 'shoulder', 'elbow'])
        
        print("✅ Hybrid Data Collector initialized")
    
    def _load_anfis(self):
        """Load ANFIS model for X-axis alignment."""
        path = 'brain/models/anfis_x.pth'
        if os.path.exists(path):
            model = ANFIS(n_inputs=1, n_rules=5, input_ranges=[(-400, 400)])
            model.load_state_dict(torch.load(path))
            model.eval()
            print("[ANFIS] Loaded X-axis model")
            return model
        else:
            print("[ANFIS] ⚠️  Model not found, using fallback")
            return None
    
    def _predict_x(self, error_x):
        """Predict X-axis correction using ANFIS."""
        if not self.brain_x:
            return 1.0 if error_x > 0 else -1.0
        
        with torch.no_grad():
            inp = torch.tensor([[error_x]], dtype=torch.float32)
            return self.brain_x(inp).item()
    
    def auto_center_base(self, target_object="bottle"):
        """
        Use ANFIS to automatically center object on X-axis.
        Returns: (centered_base_angle, pixel_y, depth_cm) or None if failed
        """
        print(f"\n🎯 Auto-centering '{target_object}' on X-axis...")
        self.camera.set_target_object(target_object)
        
        # Starting position
        base = 90
        shoulder = 90
        elbow = 120
        
        self.robot.move_to([base, shoulder, elbow, FIXED_WRIST_ANGLE, FIXED_ROLL, GRIPPER_OPEN])
        time.sleep(2)
        
        for iteration in range(MAX_ALIGNMENT_ITERATIONS):
            time.sleep(0.5)
            detections = self.camera.last_detection
            
            if not detections:
                print(f"  Iter {iteration+1}: No object detected")
                continue
            
            det = detections[0]
            error_x = det['error_x']
            
            # Check if centered
            if abs(error_x) < 20:
                print(f"✅ Centered! Base={base}°, Error={error_x:.0f}px")
                
                # Extract data
                pixel_y = det['error_y']  # Error from center
                depth_cm = det['distance_cm']
                
                return (base, pixel_y, depth_cm)
            
            # Predict correction
            correction = self._predict_x(error_x)
            correction = max(-30, min(30, correction))
            
            base += correction
            base = max(0, min(180, base))
            
            print(f"  Iter {iteration+1}: ErrX={error_x:.0f}px → Correction={correction:.1f}° → Base={base:.1f}°")
            
            self.robot.move_to([base, shoulder, elbow, FIXED_WRIST_ANGLE, FIXED_ROLL, GRIPPER_OPEN])
        
        print("❌ Failed to center object within max iterations")
        return None
    
    def manual_reach(self, locked_base):
        """
        Allow user to manually adjust Shoulder/Elbow to reach object.
        Returns: (shoulder, elbow) when user presses SPACE
        """
        print("\n🎮 Manual Reach Mode")
        print("Controls: W/S (Shoulder), A/D (Elbow), SPACE (Save), Q (Quit)")
        
        shoulder = 90
        elbow = 120
        
        self.robot.move_to([locked_base, shoulder, elbow, FIXED_WRIST_ANGLE, FIXED_ROLL, GRIPPER_OPEN])
        
        while True:
            print(f"\rShoulder: {shoulder:3d}° | Elbow: {elbow:3d}°  ", end='', flush=True)
            
            if msvcrt.kbhit():
                key = msvcrt.getch().decode('utf-8').lower()
                
                if key == 'w':
                    shoulder = min(180, shoulder + 1)
                    self.robot.move_to([locked_base, shoulder, elbow, FIXED_WRIST_ANGLE, FIXED_ROLL, GRIPPER_OPEN])
                    
                elif key == 's':
                    shoulder = max(0, shoulder - 1)
                    self.robot.move_to([locked_base, shoulder, elbow, FIXED_WRIST_ANGLE, FIXED_ROLL, GRIPPER_OPEN])
                    
                elif key == 'd':
                    elbow = min(180, elbow + 1)
                    self.robot.move_to([locked_base, shoulder, elbow, FIXED_WRIST_ANGLE, FIXED_ROLL, GRIPPER_OPEN])
                    
                elif key == 'a':
                    elbow = max(0, elbow - 1)
                    self.robot.move_to([locked_base, shoulder, elbow, FIXED_WRIST_ANGLE, FIXED_ROLL, GRIPPER_OPEN])
                    
                elif key == ' ':
                    print(f"\n💾 Saving: Shoulder={shoulder}°, Elbow={elbow}°")
                    return (shoulder, elbow)
                    
                elif key == 'q':
                    print("\n❌ Cancelled")
                    return None
    
    def collect_sample(self):
        """Collect one training sample."""
        # Step 1: Auto-center
        result = self.auto_center_base(target_object="bottle")
        
        if not result:
            print("⚠️  Auto-centering failed. Try again.")
            return False
        
        locked_base, pixel_y, depth_cm = result
        
        print(f"\n📊 Input Captured: Pixel_Y={pixel_y:.0f}px, Depth={depth_cm:.1f}cm")
        
        # Step 2: Manual reach
        reach_result = self.manual_reach(locked_base)
        
        if not reach_result:
            return False
        
        shoulder, elbow = reach_result
        
        # Step 3: Save to CSV
        with open(OUTPUT_FILE, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([pixel_y, depth_cm, shoulder, elbow])
        
        print(f"✅ Sample saved to {OUTPUT_FILE}")
        return True
    
    def run(self):
        """Main collection loop."""
        print("=" * 60)
        print("HYBRID DATA COLLECTION")
        print("=" * 60)
        print("\nPlace object at different positions (near/far, high/low)")
        print("Press ENTER to start collection, 'q' to quit\n")
        
        sample_count = 0
        
        try:
            while True:
                cmd = input(f"\n[Sample #{sample_count+1}] Press ENTER to collect (or 'q' to quit): ").strip().lower()
                
                if cmd == 'q':
                    break
                
                if self.collect_sample():
                    sample_count += 1
                    print(f"\n✅ Total samples collected: {sample_count}")
                else:
                    print("\n⚠️  Sample collection failed")
        
        except KeyboardInterrupt:
            print("\n\n🛑 Interrupted")
        
        finally:
            print(f"\n📁 Data saved to: {OUTPUT_FILE}")
            print(f"📊 Total samples: {sample_count}")

def main():
    collector = HybridDataCollector()
    collector.run()

if __name__ == "__main__":
    main()
    