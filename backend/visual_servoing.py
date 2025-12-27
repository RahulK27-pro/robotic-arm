import time
import threading
from hardware.robot_driver import RobotArm
from camera import VideoCamera
from brain.kinematics import compute_forward_kinematics, LINK_1
import math
import torch
import os
from brain.anfis_pytorch import ANFIS
from tools.collect_data import DataCollector

class VisualServoingAgent:
    """
    Visual Servoing Agent (ANFIS Powered)
    
    1. SEARCH: Sweep until object found.
    2. ALIGN: Use 'anfis_center' to align X (Base) and Y (Elbow-based height adjust).
    3. APPROACH: Use 'anfis_shoulder' & 'anfis_elbow' to drive towards object.
    4. GRAB: Blind grab sequence.
    """
    
    def __init__(self, robot: RobotArm, camera: VideoCamera):
        self.robot = robot
        self.camera = camera
        self.running = False
        self.thread = None
        self.frame_count = 0
        self.state = "SEARCHING" 
        self.search_dir = 1 
        self.missed_frames = 0
        
        # Telemetry
        self.current_telemetry = {
            "mode": "IDLE",
            "active_brain": "None",
            "correction_x": 0.0,
            "target_shoulder": 0,
            "target_elbow": 0,
            "distance": 0
        }
        
        # Continuous grab settings
        self.enable_grab = True 
        self.centered_frames = 0 
        self.required_centered_frames = 3

        # --- LOADER HELPER ---
        def load_anfis(name, inputs, rules, ranges):
            base_dir = os.path.dirname(os.path.abspath(__file__))
            path = os.path.join(base_dir, f'brain/models/{name}.pth')
            model = ANFIS(n_inputs=inputs, n_rules=rules, input_ranges=ranges)
            try:
                if os.path.exists(path):
                    model.load_state_dict(torch.load(path))
                    model.eval()
                    print(f"[ANFIS] Loaded {name} from {path}")
                    return model
                else:
                    print(f"[ANFIS] Warning: {path} not found.")
                    return None
            except Exception as e:
                print(f"[ANFIS] Error loading {name}: {e}")
                return None

        # --- LOAD MODELS ---
        # 1. Centering Brain (Error -> Correction)
        # 1 Input (Error px), ~5 Rules (Based on check_dims.py trace)
        self.brain_center = load_anfis("anfis_center", inputs=1, rules=5, ranges=[(-600, 600)])
        
        # 2. Kinematics Brains (Dist, Y_px -> Angle)
        # 2 Inputs, ~12 Rules (Based on train_kinematics.py)
        # Ranges: Dist(0-100), Y(-300, 300)
        ranges_kin = [(0, 100), (-300, 300)]
        self.brain_shoulder = load_anfis("anfis_shoulder", inputs=2, rules=12, ranges=ranges_kin)
        self.brain_elbow = load_anfis("anfis_elbow", inputs=2, rules=12, ranges=ranges_kin)
        
        self.use_anfis = (self.brain_center is not None)
        if not self.use_anfis:
            print("[ANFIS] CRITICAL: Centering brain missing. Falling back might be unstable.")

    def get_status(self):
        """Get current servoing status & telemetry."""
        return {
            "active": self.running,
            "mode": self.state,
            "telemetry": self.current_telemetry
        }

    def predict_center(self, error):
        """ (Error) -> Correction Angle """
        if not self.brain_center: return 0.0
        with torch.no_grad():
            inp = torch.tensor([[error]], dtype=torch.float32)
            return self.brain_center(inp).item()

    def predict_joints(self, dist, y_px):
        """ (Dist, Y) -> (Shoulder, Elbow) """
        if not self.brain_shoulder or not self.brain_elbow: return None
        with torch.no_grad():
            inp = torch.tensor([[dist, y_px]], dtype=torch.float32)
            s = self.brain_shoulder(inp).item()
            e = self.brain_elbow(inp).item()
            return s, e

    def start(self, target_object_name):
        if self.running: return
        self.target_object = target_object_name
        self.camera.set_target_object(target_object_name)
        self.running = True
        self.thread = threading.Thread(target=self._servoing_loop, daemon=True)
        self.thread.start()
        print(f"🚀 Servoing STARTED for '{target_object_name}'")
        
    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
        print("🛑 Servoing STOPPED")

    def _servoing_loop(self):
        print("=" * 60)
        print("🎯 ANFIS SERVOING STARTED")
        print("=" * 60)
        
        # Initial Pose
        BASE_START = 23      
        SHOULDER = 100      
        ELBOW_START = 140   
        WRIST_PITCH = 90    
        WRIST_ROLL = 12     
        GRIPPER = 155 
        
        self.robot.move_to([BASE_START, SHOULDER, ELBOW_START, WRIST_PITCH, WRIST_ROLL, GRIPPER])
        time.sleep(1.5)
        
        current_base = BASE_START
        current_elbow = ELBOW_START
        current_shoulder = SHOULDER
        
        while self.running:
            self.frame_count += 1
            
            # --- STAGE 1: SEARCH ---
            # Stop and get current detection
            time.sleep(0.3)  # Wait for robot to stabilize
            detections = self.camera.last_detection
            
            if not detections:
                self.state = "SEARCHING"
                self.current_telemetry["mode"] = "SEARCHING"
                self.current_telemetry["active_brain"] = "None"
                
                # Simple Sweep (reduced speed)
                step = 1.0
                current_base += (self.search_dir * step)
                if current_base <= 0 or current_base >= 180:
                    self.search_dir *= -1
                    current_base = max(0, min(180, current_base))
                
                # Move to new position
                self.robot.move_to([current_base, current_shoulder, current_elbow, WRIST_PITCH, WRIST_ROLL, GRIPPER])
                continue
                
            # --- STAGE 2: CENTER / ALIGN (STOP-AND-GO) ---
            det = detections[0]
            error_x = det['error_x']
            error_y = det['error_y']
            dist_cm = det.get('distance_cm', 25.0)
            
            # Update Telemetry
            self.current_telemetry["distance"] = dist_cm
            
            # Check if centered
            if abs(error_x) < 20:
                self.centered_frames += 1
                print(f"✅ Aligned ({self.centered_frames}/{self.required_centered_frames})")
            else:
                self.centered_frames = 0
            
            # If centered for required frames, proceed to approach
            if self.centered_frames >= self.required_centered_frames:
                 print("🎯 Centered! Starting approach...")
                 self.state = "APPROACHING"
                 self._approach_sequence(current_base, current_shoulder, current_elbow, WRIST_PITCH, WRIST_ROLL)
                 return

            # ALIGNMENT LOGIC (Iterative Step)
            self.state = "ALIGNING"
            self.current_telemetry["mode"] = "ALIGNING"
            self.current_telemetry["active_brain"] = "Simple Step"
            
            # Inner Loop: Step until error is zero (or minimal)
            # User requested loop "untill error becomes zero"
            while abs(error_x) > 20: 
                if not self.running: break
                
                # Direction Logic:
                # User reported previous logic moved AWAY from object. Inverting.
                # error_x > 0 (object LEFT) -> need camera LEFT -> INCREASE base? 
                # (Whatever the previous mapping was, we just flip it here)
                step = 1.0 if error_x > 0 else -1.0
                
                current_base += step
                current_base = max(0, min(180, current_base))
                
                self.current_telemetry["correction_x"] = step
                print(f"[Align Loop] ErrX: {error_x:.0f} -> Step: {step:.1f} -> Base: {current_base:.1f}")
                
                # Move
                self.robot.move_to([current_base, current_shoulder, current_elbow, WRIST_PITCH, WRIST_ROLL, GRIPPER])
                
                # Wait for stabilization and new frame
                time.sleep(0.5)
                
                # Update Error
                detections = self.camera.last_detection
                if not detections:
                    print("⚠️ Lost Object during alignment!")
                    break
                
                det = detections[0]
                error_x = det['error_x']
                self.current_telemetry["distance"] = det.get('distance_cm', 25.0)

            # Once aligned (error < 20) or object lost, continue to outer loop to verify or search

    def _approach_sequence(self, base, shoulder, elbow, pitch, roll):
        print("\n" + "=" * 60)
        print("🚀 STAGE 3: ANFIS APPROACH (STOP-AND-GO)")
        print("=" * 60)
        
        start_dist = self.current_telemetry["distance"]
        if start_dist <= 0: start_dist = 25.0
        
        current_base = base
        target_dist = start_dist
        step_cms = 0.5  # Move 0.5cm per step
        
        while self.running:
            # 1. STOP - Wait for robot to stabilize
            time.sleep(0.3)  # Stabilization time
            
            # 2. MEASURE - Get current vision data
            detections = self.camera.last_detection
            if not detections:
                print("⚠️ Lost Object during approach!")
                break
                
            det = detections[0]
            real_dist = det.get('distance_cm', target_dist)
            error_x = det['error_x']
            error_y = det['error_y']
            
            # 3. Check if reached blind zone
            if real_dist < 6.0:
                print("🎯 Blind Zone Reached! Grabbing...")
                self._grab_sequence(current_base, shoulder, elbow, pitch, roll)
                return

            # 4. PROCESS - Calculate corrections while stopped
            # Maintain X Alignment (servo direction: increase base = LEFT)
            if abs(error_x) > 30:
                # error_x > 0 (object LEFT) → need RIGHT → DECREASE base → NEGATIVE
                # error_x < 0 (object RIGHT) → need LEFT → INCREASE base → POSITIVE
                corr = -0.3 if error_x > 0 else 0.3
                current_base += corr
                current_base = max(0, min(180, current_base))
                print(f"   (X-Adjust needed: {corr:.2f})")
            
            # Calculate next distance target
            target_dist = real_dist - step_cms
            
            # Use ANFIS to predict joint angles for target distance
            pred_s, pred_e = self.predict_joints(target_dist, 0)
            
            if pred_s is None:
                print("❌ ANFIS Kinematics Failed.")
                break
                
            shoulder = pred_s
            elbow = pred_e
            
            # Update telemetry
            self.current_telemetry["mode"] = "APPROACHING"
            self.current_telemetry["active_brain"] = "Kinematics"
            self.current_telemetry["target_shoulder"] = shoulder
            self.current_telemetry["target_elbow"] = elbow
            self.current_telemetry["distance"] = target_dist
            
            print(f"[Appr] Stopped at {real_dist:.1f}cm | Moving to {target_dist:.1f}cm | S={shoulder:.1f}° E={elbow:.1f}°")
            
            # 5. MOVE - Execute movement to new calculated position
            self.robot.move_to([current_base, shoulder, elbow, pitch, roll, 170])
            # Loop will stop and measure again at top

    def _grab_sequence(self, base, s, e, p, r):
        print("👊 GRABBING")
        self.current_telemetry["mode"] = "GRABBING"
        
        # Gradual gripper closing for secure grab
        # 1. Already open at 170
        
        # 2. Partial close
        print("  Partial close...")
        self.robot.move_to([base, s, e, p, r, 130])
        time.sleep(0.5)
        
        # 3. Full close
        print("  Full close...")
        self.robot.move_to([base, s, e, p, r, 90])
        time.sleep(0.8)
        
        # 4. Lift
        print("  Lifting...")
        self.robot.move_to([base, s+20, e-20, p, r, 90])
        time.sleep(1.0)
        print("✅ Done.")
        self.running = False
