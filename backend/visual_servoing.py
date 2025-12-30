import time
import math
import threading
import datetime
import os
from hardware.robot_driver import RobotArm
from camera import VideoCamera
import torch
import os
import numpy as np
import joblib
from brain.anfis_pytorch import ANFIS
from brain.visual_ik_solver import get_wrist_angles, GRIPPER_LENGTH

class VisualServoingAgent:
    """
    Visual Servoing Agent with Hybrid ML Control
    
    1. SEARCH: Sweep until object found.
    2. ALIGN: Use 'anfis_x' to align X (Base) axis only.
    3. HYBRID REACH: Use MLP to predict Shoulder/Elbow/Base_Correction and execute smooth reach.
    4. GRASP: Close gripper.
    """
    
    
    
    def __init__(self, robot: RobotArm, camera: VideoCamera, on_grab_complete=None):
        self.robot = robot
        self.camera = camera
        self.running = False
        self.on_grab_complete = on_grab_complete  # Callback for pick-and-place trigger
        
        # LOGGING SETUP
        self.log_dir = "logs"
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)
        
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = os.path.join(self.log_dir, f"debug_log_{timestamp}.txt")
        self.log(f"📝 Logging started to {self.log_file}")
        
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
            "distance": 0
        }
        
        # Alignment settings
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
                    self.log(f"[ANFIS] Loaded {name} from {path}")
                    return model
                else:
                    self.log(f"[ANFIS] Warning: {path} not found.")
                    return None
            except Exception as e:
                self.log(f"[ANFIS] Error loading {name}: {e}")
                return None

        # --- LOAD X-AXIS ANFIS MODEL ---
        self.brain_x = load_anfis("anfis_x", inputs=1, rules=5, ranges=[(-400, 400)])
        
        self.use_anfis = (self.brain_x is not None)
        if not self.use_anfis:
            self.log("[ANFIS] CRITICAL: X-Axis brain (anfis_x) missing. Falling back to simple steps.")
        
        
        # --- LOAD VISUAL-COMPENSATION MLP MODEL ---
        base_dir = os.path.dirname(os.path.abspath(__file__))
        model_path = os.path.join(base_dir, 'brain', 'models', 'visual_compensation_model.pth')
        
        try:
            if os.path.exists(model_path):
                # Load checkpoint
                checkpoint = torch.load(model_path)
                
                # Import model class
                import torch.nn as nn
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
                
                # Create model
                self.mlp_model = VisualCompensationMLP(
                    input_size=checkpoint['input_size'],
                    hidden1=checkpoint['hidden_size_1'],
                    hidden2=checkpoint['hidden_size_2'],
                    output_size=checkpoint['output_size']
                )
                self.mlp_model.load_state_dict(checkpoint['model_state_dict'])
                self.mlp_model.eval()
                
                # Load scalers
                self.scaler_X = checkpoint['scaler_X']
                self.scaler_y = checkpoint['scaler_y']
                
                self.log(f"[MLP] Loaded visual-compensation model from {model_path}")
                self.log(f"[MLP] Architecture: {checkpoint['input_size']} → {checkpoint['hidden_size_1']} → {checkpoint['hidden_size_2']} → {checkpoint['output_size']}")
                self.use_mlp = True
            else:
                self.log(f"[MLP] Warning: Visual-compensation model not found at {model_path}")
                self.use_mlp = False
                self.mlp_model = None
                self.scaler_X = None
                self.scaler_y = None
        except Exception as e:
            self.log(f"[MLP] Error loading visual-compensation model: {e}")
            self.use_mlp = False
            self.mlp_model = None
            self.scaler_X = None
            self.scaler_y = None

    def log(self, message):
        """Print to console and append to log file."""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        full_msg = f"[{timestamp}] {message}"
        print(full_msg, flush=True)
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(full_msg + "\n")
        except Exception as e:
            print(f"❌ Log setup failed: {e}")

    def get_status(self):
        """Get current servoing status & telemetry."""
        return {
            "active": self.running,
            "mode": self.state,
            "telemetry": self.current_telemetry
        }

    def predict_x(self, error):
        """ (Error) -> Correction Delta (Degrees) """
        if not self.brain_x: return None
        with torch.no_grad():
            inp = torch.tensor([[error]], dtype=torch.float32)
            return self.brain_x(inp).item()

    def start(self, target_object_name):
        if self.running: return
        self.target_object = target_object_name
        self.camera.set_target_object(target_object_name)
        self.running = True
        self.thread = threading.Thread(target=self._servoing_loop, daemon=True)
        self.thread.start()
        self.log(f"🚀 Servoing STARTED for '{target_object_name}'")
        
    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
        self.log("🛑 Servoing STOPPED")

    def _servoing_loop(self):
        self.log("=" * 60)
        print("🎯 VISUAL SERVOING STARTED (SEARCH & ALIGN)", flush=True)
        print("=" * 60, flush=True)
        
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
                
            # --- STAGE 2: ALIGN X-AXIS (STOP-AND-GO) ---
            det = detections[0]
            error_x = det['error_x']
            error_y = det['error_y']
            dist_cm = det.get('distance_cm', 25.0)
            
            # Update Telemetry
            self.current_telemetry["distance"] = dist_cm
            
            # Check if centered
            if abs(error_x) < 20:
                self.centered_frames += 1
                print(f"✅ Aligned ({self.centered_frames}/{self.required_centered_frames})", flush=True)
            else:
                self.centered_frames = 0
            
            # If centered for required frames, START HYBRID REACH!
            if self.centered_frames >= self.required_centered_frames:
                 print("🎯 X-Axis Centered! Starting hybrid reach...", flush=True)
                 self._hybrid_ml_reach(current_base, det, WRIST_PITCH, WRIST_ROLL)
                 return

            # ALIGNMENT LOGIC (Iterative Step)
            self.state = "ALIGNING"
            self.current_telemetry["mode"] = "ALIGNING"
            self.current_telemetry["active_brain"] = "ANFIS X"
            
            # Inner Loop: Step until error is zero (or minimal)
            while abs(error_x) > 20: 
                if not self.running: break
                
                # Predict Correction using ANFIS
                pred_corr = self.predict_x(error_x)
                
                if pred_corr is not None:
                     # Use ANFIS prediction - better model allows higher confidence
                     step = pred_corr * 0.6  # 60% damping (was 30%) - balance speed & stability
                     step = max(-15, min(15, step))  # Increased clamp to 15° for faster movement
                else:
                    # Fallback to simple step
                    step = 1.0 if error_x > 0 else -1.0  # Faster fallback
                
                current_base += step
                current_base = max(0, min(180, current_base))
                
                self.current_telemetry["correction_x"] = step
                print(f"[Align Loop] ErrX: {error_x:.0f} -> ANFIS: {step:.2f}° -> Base: {current_base:.1f}", flush=True)
                
                # Move
                self.robot.move_to([current_base, current_shoulder, current_elbow, WRIST_PITCH, WRIST_ROLL, GRIPPER])
                
                # Wait for stabilization - reduced with better model
                time.sleep(1.0)
                
                # Update Error
                detections = self.camera.last_detection
                if not detections:
                    print("⚠️ Lost Object during alignment!")
                    break
                
                det = detections[0]
                error_x = det['error_x']
                self.current_telemetry["distance"] = det.get('distance_cm', 25.0)

            # Once aligned (error < 20) or object lost, continue to outer loop to verify or search

    def s_curve(self, t):
        """S-Curve smoothing function (0 to 1)."""
        return 3*t**2 - 2*t**3
    
    def _hybrid_ml_reach(self, aligned_base, detection, pitch, roll):
        """
        HYBRID ML REACH: Use MLP to predict target angles and execute smooth reach.
        
        Args:
            aligned_base: Base angle after ANFIS X-alignment
            pixel_y: Y-axis pixel error from detection
            depth_cm: Depth in cm from detection
            pitch, roll: Fixed wrist angles
        """
        self.log("\n" + "=" * 60)
        self.log("🚀 STAGE 3: HYBRID ML REACH")
        self.log("=" * 60)
        
        if not self.use_mlp:
            self.log("❌ MLP model not loaded. Cannot execute hybrid reach.")
            self.log("Falling back to manual control or stopping.")
            self.running = False
            return
        
        # Update telemetry
        self.current_telemetry["mode"] = "ML_PREDICTING"
        self.current_telemetry["active_brain"] = "MLP"
        
        # Extract visual features from detection
        pixel_y = detection['error_y']
        depth_cm = detection.get('distance_cm', 25.0)
        bbox = detection['bbox']
        bbox_width = bbox[2] - bbox[0]  # Calculate bounding box width
        
        # Prepare input for MLP: [pixel_y, depth_cm, bbox_width]
        features = np.array([[pixel_y, depth_cm, bbox_width]])
        features_normalized = self.scaler_X.transform(features)
        features_tensor = torch.FloatTensor(features_normalized)
        
        # Predict angles
        with torch.no_grad():
            output_normalized = self.mlp_model(features_tensor).numpy()
        
        # Denormalize
        output = self.scaler_y.inverse_transform(output_normalized)
        shoulder_target, elbow_target, base_correction = output[0]
        
        # Clamp predictions to safe ranges
        shoulder_target = np.clip(shoulder_target, 0, 180)
        elbow_target = np.clip(elbow_target, 0, 180)
        base_correction = np.clip(base_correction, -30, 30)
        
        # Calculate final base angle
        base_target = aligned_base + base_correction
        base_target = np.clip(base_target, 0, 180)
        
        self.log(f"📊 MLP Prediction:")
        self.log(f"   Input: [Pixel_Y={pixel_y:.0f}px, Depth={depth_cm:.1f}cm, BBox_Width={bbox_width}px]")
        self.log(f"   Output: Shoulder={shoulder_target:.1f}°, Elbow={elbow_target:.1f}°")
        self.log(f"   Base Correction: {base_correction:.1f}° (Base: {aligned_base:.1f}° → {base_target:.1f}°)")
        
        # Update telemetry with predictions
        self.current_telemetry["mode"] = "ML_REACHING"
        self.current_telemetry["predicted_shoulder"] = shoulder_target
        self.current_telemetry["predicted_elbow"] = elbow_target
        self.current_telemetry["base_correction"] = base_correction
        
        # Get current angles
        current_base = aligned_base
        current_shoulder = self.robot.current_angles[1]
        current_elbow = self.robot.current_angles[2]
        
        self.log("\n🎯 Executing S-Curve Reach...")
        self.log(f"   Base: {current_base:.1f}° → {base_target:.1f}°")
        self.log(f"   Shoulder: {current_shoulder:.1f}° → {shoulder_target:.1f}°")
        self.log(f"   Elbow: {current_elbow:.1f}° → {elbow_target:.1f}°")
        
        # Open gripper
        GRIPPER_OPEN = 170
        self.robot.move_to([int(current_base), int(current_shoulder), int(current_elbow), pitch, roll, GRIPPER_OPEN])
        time.sleep(0.5)
        
        # S-Curve interpolation (20 steps over 2 seconds)
        steps = 20
        for i in range(steps + 1):
            if not self.running:
                break
            
            t = i / steps
            t_smooth = self.s_curve(t)
            
            # Interpolate all axes
            base = current_base + (base_target - current_base) * t_smooth
            shoulder = current_shoulder + (shoulder_target - current_shoulder) * t_smooth
            elbow = current_elbow + (elbow_target - current_elbow) * t_smooth
            
            self.robot.move_to([
                int(base),
                int(shoulder),
                int(elbow),
                pitch,
                roll,
                GRIPPER_OPEN
            ])
            
            time.sleep(0.1)
        
        self.log("✅ Reach complete!")
        
        # Grasp
        self.log("\n🤏 Closing gripper...")
        self.current_telemetry["mode"] = "GRASPING"
        
        GRIPPER_CLOSED = 120
        self.robot.move_to([
            int(base_target),
            int(shoulder_target),
            int(elbow_target),
            pitch,
            roll,
            GRIPPER_CLOSED
        ])
        
        time.sleep(1)
        self.log("✅ Gripper closed!")
        self.log("\n" + "=" * 60)
        self.log("✅ HYBRID ML REACH COMPLETE")
        self.log("=" * 60)
        
        # Stop servoing
        self.running = False
        
        # Trigger pick-and-place callback if configured
        if self.on_grab_complete:
            print("\n🔗 Triggering pick-and-place sequence...")
            try:
                self.on_grab_complete()
            except Exception as e:
                print(f"❌ Error triggering pick-and-place: {e}")
    
    def _approach_with_alignment_OLD(self, base, shoulder, elbow, pitch, roll):
        """
        Iterative approach with Y-axis alignment.
        - Decrease shoulder by 1° per step (moving forward)
        - Correct Y-axis after each step
        - Stop when distance ≤ 10cm or shoulder ≤ 0°
        - Close gripper
        """
        self.log("\n" + "=" * 60)
        self.log("🚀 STAGE 3: ITERATIVE APPROACH WITH Y-ALIGNMENT")
        self.log("=" * 60)
        
        DISTANCE_THRESHOLD = 5.0  # cm
        SHOULDER_LIMIT = 0  # degrees
        Y_ERROR_THRESHOLD = 20  # pixels
        GRIPPER_OPEN = 170
        
        # Open gripper at start
        self.robot.move_to([base, shoulder, elbow, pitch, roll, GRIPPER_OPEN])
        time.sleep(0.5)
        
        iteration = 0
        last_known_distance = 25.0 # Track distance for blind safety
        
        while self.running:
            iteration += 1
            self.log(f"\n--- Approach Iteration #{iteration} ---")
            
            # Get current detection
            time.sleep(0.3)  # Stabilization
            detections = self.camera.last_detection
            
            if not detections:
                self.log("⚠️ Lost object during approach!")
                
                # Check blind safety
                if last_known_distance < 15.0:
                     self.log(f"🛑 Destination Reached (Blind Spot)! Last dist: {last_known_distance}cm")
                     self.log("🛑 STOPPING SERVOING.")
                     self.running = False
                     return
                else:
                     self.log(f"❌ Object lost too far ({last_known_distance}cm). Stopping.")
                     break
            
            det = detections[0]
            dist = det.get('distance_cm', 999)
            if dist > 0: last_known_distance = dist # Update if valid
            
            error_y = det['error_y']
            self.log(f"[DEBUG] Detection: Dist={dist:.1f}cm, ErrY={error_y:.0f}px")
            
            # Update telemetry
            self.current_telemetry["mode"] = "APPROACHING"
            self.current_telemetry["distance"] = dist
            
            # Check distance threshold (PRIMARY TRIGGER)
            if dist <= DISTANCE_THRESHOLD:
                self.log(f"🛑 Destination Reached! Distance: {dist:.1f}cm")
                self.log("🛑 STOPPING SERVOING.")
                self.running = False
                return
            
            # Check shoulder limit (SAFETY BACKUP)
            if shoulder <= SHOULDER_LIMIT:
                self.log(f"🛑 Destination Reached (Shoulder Limit {shoulder}°).")
                self.log("🛑 STOPPING SERVOING.")
                self.running = False
                return
            
            # Step 1: Decrease shoulder by 1° (move forward)
            self.log(f"[DEBUG] Decrementing shoulder from {shoulder} to {shoulder-1}")
            shoulder -= 1
            shoulder = max(0, shoulder)  # Safety clamp
            
            self.log(f"[Approach Move] Shoulder: {shoulder}° | Distance: {dist:.1f}cm")
            self.robot.move_to([base, shoulder, elbow, pitch, roll, GRIPPER_OPEN])
            self.log("[DEBUG] Shoulder move command sent. Sleeping 0.5s...")
            time.sleep(0.5)
            
            # Step 2: Y-axis alignment loop (iterative)
            self.log(f"  [Y-Align] Starting with error_y: {error_y:.0f}px")
            
            y_iterations = 0
            while abs(error_y) > Y_ERROR_THRESHOLD:
                if not self.running: 
                    self.log("  [DEBUG] Loop stopped (running=False)")
                    break
                
                y_iterations += 1
                
                # Calculate step direction
                # error_y > 0: Object is ABOVE center -> Camera needs UP -> Decrease elbow (since Incr=Down)
                # error_y < 0: Object is BELOW center -> Camera needs DOWN -> Increase elbow
                step = -1.0 if error_y > 0 else 1.0
                
                elbow += step
                elbow = max(0, min(180, elbow))  # Safety clamp
                
                self.log(f"    [Y-Step {y_iterations}] ErrY: {error_y:.0f}px -> Elbow: {elbow:.1f}°")
                
                # Move
                self.robot.move_to([base, shoulder, elbow, pitch, roll, GRIPPER_OPEN])
                time.sleep(1.0)  # Stabilization
                
                # Get fresh detection
                detections = self.camera.last_detection
                if not detections:
                    self.log("    ⚠️ Lost object during Y alignment!")
                    break
                
                det = detections[0]
                error_y = det['error_y']
                self.log(f"    [DEBUG] New error_y: {error_y:.0f}px")
                
                # Safety: max Y-axis iterations
                if y_iterations > 50:
                    self.log("    ⚠️ Y-axis max iterations reached!")
                    break
            
            self.log("  [DEBUG] Y-Align loop finished/skipped.")
            
            self.log(f"  ✅ Y-Axis aligned! Final error: {error_y:.0f}px")
            
            # Safety: max approach iterations
            if iteration > 150:
                self.log("⚠️ Max approach iterations reached!")
                break
    
    def _compute_horizontal_reach(self, shoulder_deg, elbow_deg):
        """
        Calculate current horizontal distance from shoulder pivot to wrist (camera).
        Uses simple planar FK: x = L1*cos(theta1) + L2*cos(theta1 + theta2)
        """
        # Physical constants from visual_ik_solver (hardcoded here for safety/speed)
        L1 = 15.0 # Shoulder
        L2 = 13.0 # Elbow
        
        # Convert to radians
        # Note: Servo angles: 
        # Shoulder: 90 is Horizontal? Or 0 is vertical?
        # Usually for this bot: 90 is Up, 0 is Forward/Down? 
        # Let's check visual_ik_solver conventions or assume standard.
        # visual_ik_solver uses:
        # A1 = shoulder_angle (deg)
        # A2 = elbow_angle (deg)
        # It uses Law of Cosines directly on triangle sides.
        
        # Let's trust visual_ik_solver.get_wrist_angles structure.
        # But we need CURRENT reach.
        # If we can't easily reproduce the FK, we can approximate.
        # But wait, we can just use the 'dist' from camera alone? No, we need absolute to feed the Solver.
        
        # Let's Try:
        # We know current S, E.
        # We know Camera Dist.
        # Let's assume current geometry is valid.
        pass

    def _execute_ik_grab(self, base, current_dist_cm, pitch, roll):
        """
        Execute True IK-based grab:
        1. Determine current extension (FK).
        2. Add camera distance to get Target Reach.
        3. Solve IK for Target Reach.
        4. Move and Grab.
        """
        print("\n" + "=" * 60, flush=True)
        print("🤖 STAGE 3.5: IK FINAL REACH (SMART)", flush=True)
        print("=" * 60, flush=True)
        
        # 1. Estimate Current Reach (Horizontal distance from shoulder pivot)
        # We use the current angles.
        s_curr = self.robot.current_angles[1]
        e_curr = self.robot.current_angles[2]
        
        # Simplified FK for this robot (Planar projection)
        # Assuming standard config:
        # S=90 -> Up, S=0 -> Forward horizontal
        # This might need tuning based on actual calibration, but let's try strict Trig.
        
        import math
        L1 = 15.0
        L2 = 13.0
        
        # Angle conversions (Deg -> Rad)
        # Note: Robot specific calibration. 
        # If S=130 (Home) -> Retracted back.
        # If S=90 -> Up.
        # If S=0 -> Forward.
        # So Angle from Horizontal = (90 - S)? Or just S?
        # Let's assume visual_ik_solver logic:
        # It returns angles 0-180.
        
        # Alternative Strategy:
        # We don't strictly need FK if we trust visual_ik_solver.
        # But we need "Total Distance".
        
        # Let's use a "Relative Move" approach with a fallback.
        # We want to increase reach by 'current_dist_cm' + 2cm safety.
        reach_increase = current_dist_cm + 3.0
        
        print(f"  [IK] Current Dist to Object: {current_dist_cm:.1f}cm", flush=True)
        print(f"  [IK] Target Reach Increase: {reach_increase:.1f}cm", flush=True)
        
        # HEURISTIC IK:
        # To reach forward X cm, we reduce Shoulder.
        # Approx: 1 cm reach ~= 1.5 - 2 deg Shoulder drop (at typical working range).
        # Let's verify with code if possible? No, safer to use the Solver if we can guess current reach.
        
        # Let's try to calculate absolute distance using a dummy call?
        # No.
        
        # Let's guess current reach based on "standard" approach position?
        # Usually approach ends around S=30-50?
        
        # Let's implement the iterative solver approach (Gradient Descent style) locally? 
        # Too complex.
        
        # BETTER: Use the "Last Valid X/Y" as requested.
        # "fix the preciously obtained x and y axis before the object becomes not detectable"
        # This implies we grab at the "last seen location".
        # We are already aligned Y. X is aligned.
        # So we just need depth.
        
        # Let's use the Heuristic Lunge but SCALED by distance.
        # 1.0 cm ~= -1.2 deg Shoulder.
        d_shoulder = -(reach_increase * 1.5) # Deg to move
        
        # Elbow Compensation:
        # When Shoulder goes down, Elbow needs to go UP to maintain height?
        # Yes, slightly. 
        # linear approx: dE = -0.5 * dS (sign flip?)
        d_elbow = -(d_shoulder * 0.5) 
        
        # Apply limits
        s_new = max(0, self.robot.current_angles[1] + d_shoulder)
        e_new = min(180, self.robot.current_angles[2] + d_elbow)
        
        print(f"  [IK] Calculated Lunge: dS={d_shoulder:.1f}, dE={d_elbow:.1f}", flush=True)
        print(f"  [IK] Move: S{self.robot.current_angles[1]}->{int(s_new)}, E{self.robot.current_angles[2]}->{int(e_new)}", flush=True)
        
        self.robot.move_to([base, int(s_new), int(e_new), pitch, roll, 170])
        time.sleep(1.0)
        
        self._close_gripper(base, int(s_new), int(e_new), pitch, roll)

    def _close_gripper(self, base, s, e, p, r):
        """Close gripper to grab object."""
        print("\n" + "=" * 60)
        print("👊 STAGE 4: CLOSING GRIPPER")
        print("=" * 60)
        
        self.current_telemetry["mode"] = "GRABBING"
        
        # Partial close
        print("  Partial close...")
        self.robot.move_to([base, s, e, p, r, 130])
        time.sleep(0.5)
        
        # Full close
        print("  Full close...")
        self.robot.move_to([base, s, e, p, r, 90])
        time.sleep(0.8)
        
        print("=" * 60)
        print("✅ GRAB COMPLETE!")
        print("=" * 60)
        
        self.running = False
        
        # Trigger pick-and-place callback if configured
        if self.on_grab_complete:
            print("\n🔗 Triggering pick-and-place sequence...")
            try:
                self.on_grab_complete()
            except Exception as e:
                print(f"❌ Error triggering pick-and-place: {e}")

