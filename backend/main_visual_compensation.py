"""
Visual-Compensation Runtime Inference Script

Runtime control system using trained MLP model.
Workflow:
1. ANFIS aligns X-axis
2. Capture visual features (pixel_y, depth_cm, bbox_width)  
3. MLP predicts (shoulder, elbow, base_correction)
4. Execute movements with S-curve interpolation
5. Close gripper and lift
"""

import torch
import torch.nn as nn
import numpy as np
import time
import os
from hardware.robot_driver import RobotArm
from camera import VideoCamera
from brain.anfis_pytorch import ANFIS

# Configuration
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(SCRIPT_DIR, "brain", "models")
MODEL_FILE = os.path.join(MODEL_DIR, "visual_compensation_model.pth")
ANFIS_FILE = os.path.join(MODEL_DIR, "anfis_x.pth")

FIXED_WRIST_ANGLE = 90
FIXED_ROLL = 12
GRIPPER_OPEN = 170
GRIPPER_CLOSED = 90
MAX_ALIGNMENT_ITERATIONS = 50

# MLP Model Definition (must match training)
class VisualCompensationMLP(nn.Module):
    def __init__(self, input_size=3, hidden1=16, hidden2=8, output_size=3):
        super(VisualCompensationMLP, self).__init__()
        self.network = nn.Sequential(
            nn.Linear(input_size, hidden1),
            nn.ReLU(),
            nn.Linear(hidden1, hidden2),
            nn.ReLU(),
            nn.Linear(hidden2, output_size)
        )
    
    def forward(self, x):
        return self.network(x)


class VisualCompensationController:
    def __init__(self, simulation_mode=False):
        print("=" * 60)
        print("VISUAL-COMPENSATION RUNTIME SYSTEM")
        print("=" * 60)
        
        # Initialize hardware
        self.robot = RobotArm(simulation_mode=simulation_mode, port='COM4')
        self.camera = VideoCamera(detection_mode='yolo')
        
        # Load ANFIS X-axis model
        self.brain_x = self._load_anfis()
        
        # Load MLP model and scalers
        self.mlp_model, self.scaler_X, self.scaler_y = self._load_mlp()
        
        print("\n✅ System initialized and ready")
    
    def _load_anfis(self):
        """Load ANFIS X-axis alignment model."""
        if os.path.exists(ANFIS_FILE):
            model = ANFIS(n_inputs=1, n_rules=5, input_ranges=[(-400, 400)])
            model.load_state_dict(torch.load(ANFIS_FILE))
            model.eval()
            print(f"✅ Loaded ANFIS X-axis model from: {ANFIS_FILE}")
            return model
        print(f"⚠️  ANFIS model not found: {ANFIS_FILE}")
        return None
    
    def _load_mlp(self):
        """Load trained MLP model and scalers."""
        if not os.path.exists(MODEL_FILE):
            raise FileNotFoundError(f"MLP model not found: {MODEL_FILE}")
        
        checkpoint = torch.load(MODEL_FILE)
        
        # Recreate model
        model = VisualCompensationMLP(
            input_size=checkpoint['input_size'],
            hidden1=checkpoint['hidden_size_1'],
            hidden2=checkpoint['hidden_size_2'],
            output_size=checkpoint['output_size']
        )
        model.load_state_dict(checkpoint['model_state_dict'])
        model.eval()
        
        scaler_X = checkpoint['scaler_X']
        scaler_y = checkpoint['scaler_y']
        
        print(f"✅ Loaded MLP model from: {MODEL_FILE}")
        return model, scaler_X, scaler_y
    
    def _predict_x(self, error_x):
        """ANFIS prediction for X-axis correction."""
        if not self.brain_x:
            return 1.0 if error_x > 0 else -1.0
        with torch.no_grad():
            inp = torch.tensor([[error_x]], dtype=torch.float32)
            return self.brain_x(inp).item()
    
    def align_x_axis(self, target_object="bottle"):
        """
        Stage 1: Auto-align X-axis using ANFIS.
        Returns (base_angle, pixel_y, depth_cm, bbox_width) on success, None on failure.
        """
        print(f"\n🎯 Stage 1: X-Axis Alignment for '{target_object}'")
        self.camera.set_target_object(target_object)
        
        # Search configuration
        BASE_START = 23
        SHOULDER = 100
        ELBOW_START = 140
        
        base = BASE_START
        shoulder = SHOULDER
        elbow = ELBOW_START
        
        # Move to search position
        self.robot.move_to([base, shoulder, elbow, FIXED_WRIST_ANGLE, FIXED_ROLL, GRIPPER_OPEN])
        time.sleep(2)
        
        search_dir = 1
        
        for iteration in range(MAX_ALIGNMENT_ITERATIONS):
            time.sleep(0.5)
            detections = self.camera.last_detection
            
            if not detections:
                # Sweep search
                step = 1.0
                base += (search_dir * step)
                if base <= 0 or base >= 180:
                    search_dir *= -1
                    base = max(0, min(180, base))
                
                self.robot.move_to([base, shoulder, elbow, FIXED_WRIST_ANGLE, FIXED_ROLL, GRIPPER_OPEN])
                print(f"  [Search {iteration+1}] Sweeping... Base={base:.1f}°")
                continue
            
            # Object found - start alignment
            det = detections[0]
            error_x = det['error_x']
            bbox = det['bbox']
            bbox_width = bbox[2] - bbox[0]
            
            if abs(error_x) < 20:
                print(f"✅ X-Axis Centered! Base={base}°")
                print(f"   Visual State: [Y={det['error_y']:.0f}px, D={det['distance_cm']:.1f}cm, W={bbox_width}px]")
                return (base, det['error_y'], det['distance_cm'], bbox_width)
            
            # ANFIS alignment
            correction = self._predict_x(error_x)
            correction = max(-30, min(30, correction))
            base += correction
            base = max(0, min(180, base))
            
            print(f"  [Align {iteration+1}] ErrX={error_x:.0f}px → Corr={correction:.1f}° → Base={base:.1f}°")
            
            self.robot.move_to([base, shoulder, elbow, FIXED_WRIST_ANGLE, FIXED_ROLL, GRIPPER_OPEN])
        
        print("❌ X-axis alignment failed")
        return None
    
    def predict_reach(self, pixel_y, depth_cm, bbox_width):
        """
        Stage 2: MLP prediction for reach angles and base correction.
        Returns (shoulder, elbow, base_correction).
        """
        print(f"\n🧠 Stage 2: MLP Prediction")
        print(f"   Input: [Y={pixel_y:.0f}px, D={depth_cm:.1f}cm, W={bbox_width}px]")
        
        # Prepare input
        features = np.array([[pixel_y, depth_cm, bbox_width]])
        features_normalized = self.scaler_X.transform(features)
        features_tensor = torch.FloatTensor(features_normalized)
        
        # Predict
        with torch.no_grad():
            output_normalized = self.mlp_model(features_tensor).numpy()
        
        # Denormalize
        output = self.scaler_y.inverse_transform(output_normalized)
        shoulder, elbow, base_correction = output[0]
        
        # Clamp to safe ranges
        shoulder = max(0, min(140, shoulder))
        elbow = max(70, min(160, elbow))
        base_correction = max(-90, min(90, base_correction))
        
        print(f"   Predicted: [Shoulder={shoulder:.1f}°, Elbow={elbow:.1f}°, BaseCorr={base_correction:.1f}°]")
        
        return shoulder, elbow, base_correction
    
    def execute_reach(self, locked_base, shoulder_target, elbow_target, base_correction):
        """
        Stage 3: Execute reach with S-curve interpolation and base correction.
        """
        print(f"\n🚀 Stage 3: Executing Reach")
        
        # Calculate final base position
        final_base = locked_base + base_correction
        final_base = max(0, min(180, final_base))
        
        print(f"   Target: [Base={final_base:.1f}° (locked={locked_base:.1f}° + corr={base_correction:.1f}°)]")
        print(f"           [Shoulder={shoulder_target:.1f}°, Elbow={elbow_target:.1f}°]")
        
        # Get current positions
        current_positions = self.robot.get_joint_angles()
        
        # S-curve interpolation parameters
        steps = 30
        duration = 2.0  # seconds
        dt = duration / steps
        
        for i in range(steps + 1):
            # S-curve interpolation factor (smooth acceleration and deceleration)
            t = i / steps
            if t < 0.5:
                s = 2 * t * t
            else:
                s = 1 - 2 * (1 - t) * (1 - t)
            
            # Interpolate angles
            base_angle = current_positions[0] + s * (final_base - current_positions[0])
            shoulder_angle = current_positions[1] + s * (shoulder_target - current_positions[1])
            elbow_angle = current_positions[2] + s * (elbow_target - current_positions[2])
            
            # Move robot
            self.robot.move_to([
                base_angle, 
                shoulder_angle, 
                elbow_angle, 
                FIXED_WRIST_ANGLE, 
                FIXED_ROLL, 
                GRIPPER_OPEN
            ])
            
            time.sleep(dt)
        
        print(f"✅ Reach complete")
    
    def grasp_and_lift(self):
        """
        Stage 4: Close gripper and lift object.
        """
        print(f"\n🤏 Stage 4: Grasp and Lift")
        
        # Close gripper
        current = self.robot.get_joint_angles()
        current[5] = GRIPPER_CLOSED
        self.robot.move_to(current)
        print(f"   Gripper closed")
        time.sleep(1)
        
        # Lift (move shoulder up ~20 degrees)
        current[1] = min(140, current[1] + 20)
        self.robot.move_to(current)
        print(f"   Lifted object")
        time.sleep(1)
        
        print(f"✅ Grasp complete")
        return True
    
    def execute_full_grasp(self, target_object="bottle"):
        """Execute complete grasp workflow."""
        print("\n" + "=" * 60)
        print(f"GRASPING: {target_object}")
        print("=" * 60)
        
        # Stage 1: X-Axis Alignment
        result = self.align_x_axis(target_object)
        if not result:
            print("❌ Failed to align X-axis")
            return False
        
        locked_base, pixel_y, depth_cm, bbox_width = result
        
        # Stage 2: MLP Prediction
        shoulder, elbow, base_correction = self.predict_reach(pixel_y, depth_cm, bbox_width)
        
        # Stage 3: Execute Reach
        self.execute_reach(locked_base, shoulder, elbow, base_correction)
        
        # Stage 4: Grasp and Lift
        success = self.grasp_and_lift()
        
        if success:
            print("\n" + "=" * 60)
            print("✅ GRASP SUCCESSFUL")
            print("=" * 60)
        
        return success


def main():
    # Initialize controller
    controller = VisualCompensationController(simulation_mode=False)
    
    print("\n📋 Visual-Compensation System Ready")
    print("   ANFIS: X-axis alignment")
    print("   MLP:   Y/Z reach + base correction")
    print()
    
    try:
        while True:
            target = input("Enter target object name (or 'q' to quit): ").strip()
            
            if target.lower() == 'q':
                break
            
            if not target:
                target = "bottle"
            
            controller.execute_full_grasp(target)
            
            # Ask to continue
            again = input("\nGrasp another object? (y/n): ").strip().lower()
            if again != 'y':
                break
    
    except KeyboardInterrupt:
        print("\n🛑 Interrupted")
    
    finally:
        print("\n👋 Shutting down...")


if __name__ == "__main__":
    main()
