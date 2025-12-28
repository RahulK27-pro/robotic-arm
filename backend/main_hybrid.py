"""
Hybrid 2-Axis Runtime Controller

Execution Flow:
1. ALIGN: Use ANFIS to center object on X-axis (Base)
2. PREDICT: Use MLP to predict Shoulder/Elbow from [Pixel_Y, Depth]
3. BLIND ACTION: Move to predicted angles (S-Curve interpolation)
4. GRASP: Close gripper
"""

import time
import numpy as np
import joblib
import torch
from hardware.robot_driver import RobotArm
from camera import VideoCamera
from brain.anfis_pytorch import ANFIS
import os

# Configuration
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FIXED_WRIST_ANGLE = 90
FIXED_ROLL = 12
GRIPPER_OPEN = 170
GRIPPER_CLOSED = 120
MAX_ALIGNMENT_ITERATIONS = 50
MODEL_PATH = os.path.join(SCRIPT_DIR, "brain", "models", "reach_model.pkl")
SCALER_PATH = os.path.join(SCRIPT_DIR, "brain", "models", "reach_scaler.pkl")

class HybridController:
    def __init__(self):
        # Initialize hardware
        self.robot = RobotArm(simulation_mode=False, port='COM4')
        self.camera = VideoCamera(detection_mode='yolo')
        
        # Load ANFIS for X-axis
        self.brain_x = self._load_anfis()
        
        # Load MLP for Y/Z-axes
        self.reach_model = joblib.load(MODEL_PATH)
        self.scaler = joblib.load(SCALER_PATH)
        
        print("✅ Hybrid Controller initialized")
    
    def _load_anfis(self):
        """Load ANFIS model for X-axis alignment."""
        path = os.path.join(SCRIPT_DIR, 'brain', 'models', 'anfis_x.pth')
        if os.path.exists(path):
            model = ANFIS(n_inputs=1, n_rules=5, input_ranges=[(-400, 400)])
            model.load_state_dict(torch.load(path))
            model.eval()
            print("[ANFIS] Loaded X-axis model")
            return model
        else:
            print("[ANFIS] ⚠️  Model not found")
            return None
    
    def _predict_x(self, error_x):
        """Predict X-axis correction."""
        if not self.brain_x:
            return 1.0 if error_x > 0 else -1.0
        
        with torch.no_grad():
            inp = torch.tensor([[error_x]], dtype=torch.float32)
            return self.brain_x(inp).item()
    
    def align_base(self, target_object="bottle"):
        """
        PHASE 1: ALIGN
        Use ANFIS to center object on X-axis.
        Returns: (centered_base, pixel_y, depth_cm) or None
        """
        print("\n" + "="*60)
        print("PHASE 1: X-AXIS ALIGNMENT (ANFIS)")
        print("="*60)
        
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
                print(f"  [{iteration+1}] No object detected")
                continue
            
            det = detections[0]
            error_x = det['error_x']
            
            # Check if centered
            if abs(error_x) < 20:
                pixel_y = det['error_y']
                depth_cm = det['distance_cm']
                
                print(f"✅ X-Axis Aligned! Base={base}°")
                print(f"   Input Vector: [Pixel_Y={pixel_y:.0f}px, Depth={depth_cm:.1f}cm]")
                
                return (base, pixel_y, depth_cm)
            
            # Predict correction
            correction = self._predict_x(error_x)
            correction = max(-30, min(30, correction))
            
            base += correction
            base = max(0, min(180, base))
            
            print(f"  [{iteration+1}] ErrX={error_x:.0f}px → Corr={correction:.1f}° → Base={base:.1f}°")
            
            self.robot.move_to([base, shoulder, elbow, FIXED_WRIST_ANGLE, FIXED_ROLL, GRIPPER_OPEN])
        
        print("❌ Alignment failed")
        return None
    
    def predict_reach(self, pixel_y, depth_cm):
        """
        PHASE 2: PREDICT
        Use MLP to predict Shoulder/Elbow angles AND Base Correction.
        Returns: (shoulder_target, elbow_target, base_correction)
        """
        print("\n" + "="*60)
        print("PHASE 2: REACH PREDICTION (MLP)")
        print("="*60)
        
        # Prepare input
        X = np.array([[pixel_y, depth_cm]])
        X_scaled = self.scaler.transform(X)
        
        # Predict
        y_pred = self.reach_model.predict(X_scaled)
        shoulder_target, elbow_target, base_correction = y_pred[0]
        
        # Clamp to safe ranges
        shoulder_target = np.clip(shoulder_target, 0, 180)
        elbow_target = np.clip(elbow_target, 0, 180)
        base_correction = np.clip(base_correction, -30, 30) # Limit correction
        
        print(f"🎯 Predicted Angles:")
        print(f"   Shoulder: {shoulder_target:.1f}°")
        print(f"   Elbow: {elbow_target:.1f}°")
        print(f"   Base Correction: {base_correction:.1f}°")
        
        return (shoulder_target, elbow_target, base_correction)
    
    def s_curve(self, t):
        """S-Curve smoothing function (0 to 1)."""
        return 3*t**2 - 2*t**3
    
    def blind_reach(self, base, shoulder_target, elbow_target, base_correction):
        """
        PHASE 3: BLIND ACTION
        Move Shoulder/Elbow AND Base Correction using S-Curve interpolation.
        """
        print("\n" + "="*60)
        print("PHASE 3: BLIND REACH (S-Curve)")
        print("="*60)
        
        # Current position
        shoulder_current = self.robot.current_angles[1]
        elbow_current = self.robot.current_angles[2]
        base_initial = base
        base_target = base + base_correction
        
        print(f"Moving from Shoulder={shoulder_current:.0f}° to {shoulder_target:.0f}°")
        print(f"Moving from Elbow={elbow_current:.0f}° to {elbow_target:.0f}°")
        print(f"Applying Base Correction: {base_initial:.1f}° → {base_target:.1f}°")
        
        # Interpolate with S-Curve (20 steps over 2 seconds)
        steps = 20
        for i in range(steps + 1):
            t = i / steps
            t_smooth = self.s_curve(t)
            
            shoulder = shoulder_current + (shoulder_target - shoulder_current) * t_smooth
            elbow = elbow_current + (elbow_target - elbow_current) * t_smooth
            current_base = base_initial + (base_target - base_initial) * t_smooth
            
            self.robot.move_to([
                int(current_base),             # Interpolated Base
                int(shoulder),                # Interpolated
                int(elbow),                   # Interpolated
                FIXED_WRIST_ANGLE,           # Wrist fixed
                FIXED_ROLL,                  # Roll fixed
                GRIPPER_OPEN                 # Gripper open
            ])
            
            time.sleep(0.1)
        
        print("✅ Reach complete")
        return base_target  # Return final base for grasp
    
    def grasp(self, base, shoulder, elbow):
        """
        PHASE 4: GRASP
        Close gripper.
        """
        print("\n" + "="*60)
        print("PHASE 4: GRASP")
        print("="*60)
        
        self.robot.move_to([
            int(base),
            int(shoulder),
            int(elbow),
            FIXED_WRIST_ANGLE,
            FIXED_ROLL,
            GRIPPER_CLOSED
        ])
        
        time.sleep(1)
        print("✅ Gripper closed")
    
    def run(self, target_object="bottle"):
        """Main execution loop."""
        print("\n" + "="*60)
        print("HYBRID 2-AXIS CONTROLLER")
        print("="*60)
        
        try:
            # Phase 1: Align
            result = self.align_base(target_object)
            if not result:
                print("\n❌ Alignment failed. Aborting.")
                return
            
            base, pixel_y, depth_cm = result
            
            # Phase 2: Predict
            shoulder_target, elbow_target, base_correction = self.predict_reach(pixel_y, depth_cm)
            
            # Phase 3: Blind Reach
            final_base = self.blind_reach(base, shoulder_target, elbow_target, base_correction)
            
            # Phase 4: Grasp
            self.grasp(final_base, shoulder_target, elbow_target)
            
            print("\n" + "="*60)
            print("✅ HYBRID REACH COMPLETE")
            print("="*60)
            
        except KeyboardInterrupt:
            print("\n\n🛑 Interrupted by user")
        except Exception as e:
            print(f"\n❌ Error: {e}")

def main():
    controller = HybridController()
    controller.run(target_object="bottle")

if __name__ == "__main__":
    main()
