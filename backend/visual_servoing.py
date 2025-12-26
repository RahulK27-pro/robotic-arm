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
    Visual Servoing Agent (3-Stage: Align -> Stalk -> Grab)
    
    Purpose: Center a target object and approach it dynamically using visual feedback.
    """
    
    def __init__(self, robot: RobotArm, camera: VideoCamera):
        self.robot = robot
        self.camera = camera
        self.running = False
        self.thread = None
        self.frame_count = 0
        self.state = "SEARCHING" # Start in searching mode
        self.search_dir = 1 # Start sweeping UP from 0
        self.missed_frames = 0
        
        # Continuous grab settings
        self.enable_grab = True  # Enable automatic grab after centering
        self.centered_frames = 0  # Count consecutive centered frames
        self.required_centered_frames = 5  # Frames needed before approach
        self.grab_distance = 2.0  # cm - close gripper when this close
        
        # Load the Trained ANFIS Model
        print("[ANFIS] Loading neural brain...")
        # IMPORTANT: Must use same ranges as training!
        ranges = [(-600, 600), (0, 120)]
        self.model = ANFIS(n_inputs=2, n_rules=8, input_ranges=ranges)
        self.use_anfis = False
        
        # Robust path finding
        base_dir = os.path.dirname(os.path.abspath(__file__))
        model_path = os.path.join(base_dir, 'brain/anfis_model.pth')
        
        try:
            if os.path.exists(model_path):
                self.model.load_state_dict(torch.load(model_path))
                self.model.eval() # Set to inference mode
                self.use_anfis = True
                print(f"[ANFIS] Model loaded successfully from {model_path}")
            else:
                print(f"[ANFIS] Warning: Model not found at {model_path}. Run train_anfis.py first.")
        except Exception as e:
            print(f"[ANFIS] Error loading model: {e}")
            
        # Data Collection (Bootstrapping Mode)
        # If ANFIS is NOT active, we collect data from the P-controller to train it.
        self.collector = DataCollector()
        self.collect_data = not self.use_anfis 
        if self.collect_data:
            print("[ANFIS] 📝 Data Collection ENABLED (Recording P-Control moves)")

    def predict_correction(self, error, distance):
        """Inference step: (Error, Dist) -> Correction Angle"""
        if not self.use_anfis:
            return 0.0
            
        with torch.no_grad():
            inputs = torch.tensor([[error, distance]], dtype=torch.float32)
            correction = self.model(inputs)
            return correction.item()
        
    def start(self, target_object_name):
        """Start servoing loop."""
        if self.running:
            return
            
        self.target_object = target_object_name
        self.camera.set_target_object(target_object_name)
        self.running = True
        
        self.thread = threading.Thread(target=self._servoing_loop, daemon=True)
        self.thread.start()
        print(f"🚀 Servoing STARTED for '{target_object_name}'")
        
    def stop(self):
        """Stop servoing loop."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
        print("🛑 Servoing STOPPED")
        
    def get_status(self):
        """Get current servoing status."""
        return {
            "active": self.running,
            "mode": "3_stage_stalk"
        }

    def _servoing_loop(self):
        """
        STAGE 1: COARSE ALIGNMENT
        
        Controls base (X-axis) and elbow (Y-axis) to center target.
        Does NOT move forward (Z-axis). This ensures we are looking at the object
        straight-on before we start the approach.
        """
        print("=" * 60)
        print("🎯 VISUAL SERVOING - STAGE 1: COARSE ALIGNMENT")
        print("=" * 60)
        
        # Configuration (TUNED FOR STABILITY)
        # Adaptive Gain Limits - ULTRA STABLE (User Requested)
        GAIN_HIGH = 0.01    # Drastically reduced from 0.04
        GAIN_LOW = 0.005    # Drastically reduced from 0.015
        
        DEADZONE = 30       
        MAX_STEP = 1.0      # Max 1 degree per frame
        MIN_MOVE = 1.0      # Minimum move to overcome stiction
        
        # Servo Limits (Safety)
        SERVO_MIN = 0       
        SERVO_MAX = 180     
        
        # Fixed servo positions for Stage 1
        BASE_START = 23      
        SHOULDER = 100      # Optimized Search View
        ELBOW_START = 140   
        WRIST_PITCH = 90    
        WRIST_ROLL = 12     
        GRIPPER = 155       # Slightly closed
        
        # Initialize: Move to Start Position
        print(f"Moving to starting position...")
        
        # Smooth Startup
        start_angles = self.robot.current_angles
        target_angles = [BASE_START, SHOULDER, ELBOW_START, WRIST_PITCH, WRIST_ROLL, GRIPPER]
        
        steps = 40  
        for i in range(1, steps + 1):
            t = i / steps
            interp = []
            for j in range(6):
                val = start_angles[j] + (target_angles[j] - start_angles[j]) * t
                interp.append(val)
            
            self.robot.move_to(interp)
            time.sleep(0.05)
            
        # Ensure exact
        self.robot.move_to(target_angles)
        time.sleep(1.5)
        
        current_base = BASE_START
        current_elbow = ELBOW_START
        
        print("\n✅ Ready! Aligning X/Y before approach...\n")
        
        # Main monitoring loop
        while self.running:
            self.frame_count += 1
            
            # Get detections
            detections = self.camera.last_detection
            
            if not detections:
                time.sleep(0.1)
                detections = self.camera.last_detection

            # -----------------------------------------------------------------
            # STATE: SEARCHING (No Object Detected)
            # -----------------------------------------------------------------
            if not detections:
                self.missed_frames += 1
                
                if self.state == "TRACKING":
                    if self.missed_frames < 5:
                        # Brief loss, hold position
                        time.sleep(0.05)
                        continue
                    else:
                        print(f"[Frame {self.frame_count}] ❌ Target confirmed lost! Switching to SEARCHING...")
                        self.state = "SEARCHING"
                
                # --- SAFETY CHECK: CAMERA LATENCY ---
                if hasattr(self.camera, 'last_frame_time'):
                    latency = time.time() - self.camera.last_frame_time
                    if latency > 2.0:
                        print(f"⚠️ VISION LAG ({latency:.1f}s) - PAUSING SEARCH TO PROTECT CAMERA...")
                        time.sleep(1.0)
                        continue 
                # ------------------------------------
                
                # Perform Sweep
                # Reduced step size for slower scanning (User Requested)
                step = 1.5 
                new_base = current_base + (self.search_dir * step)
                
                if new_base <= SERVO_MIN:
                    new_base = SERVO_MIN
                    self.search_dir = 1 
                    print(f"[Frame {self.frame_count}] 🔄 Reached Min. Sweeping UP...")
                elif new_base >= SERVO_MAX:
                    new_base = SERVO_MAX
                    self.search_dir = -1 
                    print(f"[Frame {self.frame_count}] 🔄 Reached Max. Sweeping DOWN...")
                
                self.robot.move_to([new_base, SHOULDER, ELBOW_START, WRIST_PITCH, WRIST_ROLL, GRIPPER])
                current_base = new_base
                
                current_base = new_base
                
                # Increased delay for camera exposure/YOLO AND to unblock UI thread
                time.sleep(0.15)
                continue

            # -----------------------------------------------------------------
            # STATE: TRACKING / ALIGNING
            # -----------------------------------------------------------------
            self.missed_frames = 0
            
            if self.state == "SEARCHING":
                print(f"[Frame {self.frame_count}] 🎯 Target FOUND! Switching to TRACKING...")
                self.state = "TRACKING"
                # Sync elbow to avoid jump
                current_elbow = ELBOW_START 
            
            # Extract Errors
            error_x = detections[0]['error_x']
            error_y = detections[0]['error_y']
            
            # Alignment Check
            x_centered = abs(error_x) < DEADZONE
            y_centered = abs(error_y) < DEADZONE
            
            # Success Condition
            if x_centered and y_centered:
                self.centered_frames += 1
                print(f"[Frame {self.frame_count}] ✅ ALIGNED! X={error_x}px, Y={error_y}px ({self.centered_frames}/{self.required_centered_frames})")
                
                # If stable, proceed to Stalking
                if self.enable_grab and self.centered_frames >= self.required_centered_frames:
                    print("\n🚀 ALIGNMENT COMPLETE! Starting STAGE 2: STALKING...")
                    self.state = "APPROACHING"
                    self.centered_frames = 0
                    
                    # Hand over control to Approach Routine
                    self._approach_and_grab(current_base, SHOULDER, current_elbow, WRIST_PITCH, WRIST_ROLL)
                    return  # Exit the loop (job done or failed inside approach)
                
                time.sleep(0.1)
                continue
            else:
                self.centered_frames = 0
            
            # Corrections
            # Priority: X then Y
            if not x_centered:
                if self.use_anfis:
                    # --- ANFIS CONTROL (X-Axis) ---
                    dist_cm = detections[0].get('distance_cm', 20.0)
                    if dist_cm <= 0: dist_cm = 20.0 # Safety default
                    
                    correction_x = self.predict_correction(error_x, dist_cm)
                    
                    # Apply to Robot
                    new_base = current_base + correction_x
                    new_base = max(SERVO_MIN, min(SERVO_MAX, new_base))
                    
                    new_elbow = current_elbow
                    
                    dir_x = "RIGHT" if correction_x > 0 else "LEFT"
                    print(f"[Frame {self.frame_count}] X-ANFIS (Dist={dist_cm:.1f}cm): {error_x:+4.0f}px → {dir_x} {abs(correction_x):.2f}°")
                    
                else:
                    # --- LEGACY P-CONTROL (Fallback) ---
                    # ADAPTIVE GAIN
                    current_gain = GAIN_HIGH if abs(error_x) > 100 else GAIN_LOW
                    
                    raw_correction = (error_x * current_gain)
                    
                    # MIN-MOVE THRESHOLD (Anti-Stiction)
                    if abs(raw_correction) < 0.5:
                        correction_x = 0 # Ignore micro-jitters
                    elif abs(raw_correction) < MIN_MOVE:
                        # Force minimum move if significant enough
                        correction_x = MIN_MOVE * (1 if raw_correction > 0 else -1)
                    else:
                        correction_x = raw_correction
                    
                    correction_x = max(-MAX_STEP, min(MAX_STEP, correction_x))
                    
                    new_base = current_base + correction_x
                    new_base = max(SERVO_MIN, min(SERVO_MAX, new_base))
                    
                    new_elbow = current_elbow
                    
                    dir_x = "RIGHT" if correction_x > 0 else "LEFT"
                    print(f"[Frame {self.frame_count}] X-ALIGN (G={current_gain}): {error_x:+4.0f}px → {dir_x} {abs(correction_x):.2f}°")
                    
                    # LOG DATA for ANFIS Training
                    if self.collect_data and abs(correction_x) > 0:
                        dist_cm = detections[0].get('distance_cm', 20.0)
                        if dist_cm <= 0: dist_cm = 20.0
                        self.collector.log(error_x, dist_cm, correction_x)
                
            else: # X is good, fix Y
                # ADAPTIVE GAIN
                current_gain = GAIN_HIGH if abs(error_y) > 100 else GAIN_LOW
                
                raw_correction = -(error_y * current_gain) # Angle up = move down
                
                # MIN-MOVE THRESHOLD
                if abs(raw_correction) < 0.5:
                    correction_y = 0
                elif abs(raw_correction) < MIN_MOVE:
                    correction_y = MIN_MOVE * (1 if raw_correction > 0 else -1)
                else:
                    correction_y = raw_correction
                
                correction_y = max(-MAX_STEP, min(MAX_STEP, correction_y))
                
                new_elbow = current_elbow + correction_y
                new_elbow = max(SERVO_MIN, min(150, new_elbow))
                
                new_base = current_base
                
                dir_y = "UP" if correction_y < 0 else "DOWN"
                print(f"[Frame {self.frame_count}] Y-ALIGN (G={current_gain}): {error_y:+4.0f}px → {dir_y} {abs(correction_y):.2f}°")
            
            # Execute Move
            self.robot.move_to([new_base, SHOULDER, new_elbow, WRIST_PITCH, WRIST_ROLL, GRIPPER])
            
            current_base = new_base
            current_base = new_base
            current_elbow = new_elbow
            
            # STABILIZATION DELAY (Stop-and-Stare)
            # Wait for robot to settle and camera to capture a clean frame
            time.sleep(0.5)
    
    def _approach_and_grab(self, base, shoulder, elbow, wrist_pitch, wrist_roll):
        """
        STAGE 2 & 3: CLOSED-LOOP STALKING & GRAB
        
        Strategy: Stop-Look-Align-Approach
        1. Stop to stabilize.
        2. Check X/Y alignment.
        3. If aligned, move 1 step closer.
        4. Repeat until Blind Zone (<5cm).
        5. Blind Commit -> Grab -> Lift.
        """
        from brain.visual_ik_solver import get_wrist_angles, check_reachability
        from brain.kinematics import compute_forward_kinematics
        
        print("\n" + "=" * 60)
        print("🕵️ STAGE 2: CLOSED-LOOP STALKING")
        print("=" * 60)
        
        # Tuning
        ALIGN_THRESHOLD = 20  # Pixels (Strict alignment)
        BLIND_ZONE = 6.0      # cm
        TIMEOUT = 60.0        # Seconds
        MAX_STEP = 1.0        # cm per move
        
        current_base = base
        start_time = time.time()
        iteration = 0
        last_target_dist = 25.0
        
        # 1. Initial State
        self.robot.move_to([current_base, shoulder, elbow, wrist_pitch, wrist_roll, 170])
        time.sleep(0.5) 
        
        while self.running:
            # A. Safety
            if time.time() - start_time > TIMEOUT:
                print("❌ Approach timeout")
                return

            # B. LOOK (Wait for fresh data)
            time.sleep(0.1) # Stabilization
            detections = self.camera.last_detection
            
            # --- SAFETY CHECK: CAMERA LATENCY ---
            if hasattr(self.camera, 'last_frame_time'):
                 latency = time.time() - self.camera.last_frame_time
                 if latency > 2.0:
                      print(f"⚠️ VISION LAG ({latency:.1f}s) - PAUSING STALK...")
                      time.sleep(1.0)
                      continue
            # ------------------------------------
            
            if not detections:
                print(f"[{iteration}] ⚠️ Object lost... Waiting...")
                time.sleep(0.2)
                continue
                
            det = detections[0]
            error_x = det.get('error_x', 0)
            target_dist = det.get('distance_cm', -1)
            
            if target_dist <= 0:
                continue
            
            last_target_dist = target_dist
            
            # C. CHECK BLIND ZONE
            # Note: target_dist IS the gap because camera is on gripper
            gap = target_dist 
            print(f"[{iteration}] Gap: {gap:.1f}cm | X-Err: {error_x:.0f}px")
            
            if gap < BLIND_ZONE:
                print(f"\n🎯 ENTERING BLIND ZONE ({gap:.1f}cm)... Committing to GRAB!")
                break
                
            # D. ALIGN OR APPROACH
            # If X error is too high, ONLY fix alignment, don't move forward
            if abs(error_x) > ALIGN_THRESHOLD:
                # Calculate correction
                correction = 0.5 if error_x > 0 else -0.5 # Small nudge
                if abs(error_x) > 50: correction *= 2
                
                new_base = current_base + correction
                new_base = max(0, min(180, new_base))
                
                print(f"   ↪️ Aligning X... ({error_x:.0f}px -> Move {correction})")
                self.robot.move_to([new_base, shoulder, elbow, wrist_pitch, wrist_roll, 170])
                current_base = new_base
                time.sleep(0.2) # Allow settle
                continue # Loop back to Look
            
            # E. APPROACH (If aligned)
            # Calculate next reach
            curr_pos = compute_forward_kinematics(self.robot.current_angles)
            curr_reach = math.sqrt(curr_pos[0]**2 + curr_pos[1]**2)
            
            # Step size: proportional to gap but capped
            step = max(0.5, min(MAX_STEP, gap * 0.2))
            
            # We want to REACH to (Current Reach + Step)
            # This effectively moves the TIP forward by 'step'
            next_reach = curr_reach + step 
            
            # Solve IK
            # Key Fix: visual_ik_solver now interprets input as TIP distance
            # So pass 'next_reach' as the total distance from shoulder to object tip
            angles = get_wrist_angles(next_reach, object_height_cm=5.0)
            
            if angles is None:
                print("❌ Cannot reach further!")
                break
                
            s, e = angles
            e = min(150, e) # Safety
            
            print(f"   ⬆️ Approaching... +{step:.1f}cm (Reach: {next_reach:.1f}cm)")
            self.robot.move_to([current_base, s, e, wrist_pitch, wrist_roll, 170])
            shoulder, elbow = s, e # Update current state
            iteration += 1
            time.sleep(0.1)
            
        # --- STAGE 3: BLIND GRAB ---
        self._blind_grab_sequence(current_base, shoulder, elbow, wrist_pitch, wrist_roll, last_target_dist)

    def _blind_grab_sequence(self, base, shoulder, elbow, pitch, roll, gap):
        """
        Execute the final grab sequence.
        """
        from brain.visual_ik_solver import get_wrist_angles
        from brain.kinematics import compute_forward_kinematics

        print("\n" + "=" * 60)
        print("👊 STAGE 3: BLIND GRAB & LIFT")
        print("=" * 60)
        
        # 1. Calculate Final Lunge
        # We are at 'blind_zone' distance (approx 6cm).
        # We want to surround the object.
        # Target Reach = Current Reach + Gap + Overreach (2cm)
        curr_pos = compute_forward_kinematics(self.robot.current_angles)
        curr_reach = math.sqrt(curr_pos[0]**2 + curr_pos[1]**2)
        
        final_reach = curr_reach + gap + 1.0
        print(f"📍 Final Lunge: {final_reach:.1f}cm (Gap: {gap:.1f}cm)")
        
        angles = get_wrist_angles(final_reach, object_height_cm=3.0) # Aim slightly lower for grip
        
        if angles:
            s, e = angles
            # Move to grip position
            self.robot.move_to([base, s, e, pitch, roll, 170])
            time.sleep(1.0) # Wait for settle
            
            # 2. GRAB
            print("🤏 GRABBING...")
            self.robot.move_to([base, s, e, pitch, roll, 90]) # Close
            time.sleep(1.0)
            
            # 3. LIFT
            print("🛫 LIFTING...")
            # Lift shoulder 30 deg, Drop elbow 10 deg (to pull back slightly)
            s_lift = max(0, min(180, s + 30))
            e_lift = max(0, min(180, e - 10))
            self.robot.move_to([base, s_lift, e_lift, pitch, roll, 90])
            time.sleep(1.0)
            
            print("✅ GRAB COMPLETE!")
            
        else:
            print("❌ Could not compute final grab pose.")
