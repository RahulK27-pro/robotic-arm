import time
import threading
from hardware.robot_driver import RobotArm
from camera import VideoCamera
from brain.kinematics import compute_forward_kinematics
import math

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
        BASE_START = 0      
        SHOULDER = 130      # High view
        ELBOW_START = 130   
        WRIST_PITCH = 90    
        WRIST_ROLL = 12     
        GRIPPER = 170       # Open
        
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
                
                # Perform Sweep
                step = 3.0 
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
                
                time.sleep(0.05)
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
            current_elbow = new_elbow
            time.sleep(0.05)
    
    def _approach_and_grab(self, base, shoulder, elbow, wrist_pitch, wrist_roll):
        """
        STAGE 2 & 3: STALKING AND BLIND COMMIT
        
        Move forward (Z-axis) while maintaining alignment (X-axis).
        Stop when close (Blind Zone) and commit to grab.
        """
        from brain.visual_ik_solver import get_wrist_angles, check_reachability
        
        print("\n" + "=" * 60)
        print("� STAGE 2: STALKING (Dynamic Approach)")
        print("=" * 60)
        
        # Tuning Parameters
        GAIN_X_STALK = 0.005 # Extremely low for stalking
        MAX_BASE_STEP = 1.0  # Max 1 degree correction
        BLIND_ZONE = 5.0     
        TIMEOUT = 40.0
        
        current_base = base
        start_time = time.time()
        iteration = 0
        last_target_dist = 30.0 # Default fallback
        last_processed_time = 0
        
        # Ensure gripper is open
        self.robot.move_to([current_base, shoulder, elbow, wrist_pitch, wrist_roll, 170])
        time.sleep(0.2)
        
        while self.running:
            # Safety Timeout
            if time.time() - start_time > TIMEOUT:
                print("❌ Approach timeout")
                return
            
            # Get Visual Data
            detections = self.camera.last_detection
            
            # STALE DATA CHECK
            if detections:
                det_time = detections[0].get('timestamp', 0)
                if det_time <= last_processed_time:
                    time.sleep(0.05)
                    continue
                last_processed_time = det_time
                
            if not detections:
                print(f"[{iteration}] ⚠️ Object lost during stalk")
                time.sleep(0.1)
                iteration += 1 # Keep counting iterations
                continue
            
            det = detections[0]
            error_x = det.get('error_x', 0)
            target_dist = det.get('distance_cm', -1)
            
            if target_dist <= 0:
                time.sleep(0.1); continue
                
            last_target_dist = target_dist
            
            # --- CALCULATE GEOMETRY ---
            # 1. Get current robotic reach (horizontal distance from base)
            curr_pos = compute_forward_kinematics(self.robot.current_angles)
            curr_reach = math.sqrt(curr_pos[0]**2 + curr_pos[1]**2)
            
            # 2. Estimate remaining gap
            # Camera is on the arm/gripper, so target_dist IS the gap.
            gap = target_dist
            
            # --- STAGE 2 EXIT CONDITION: BLIND ZONE ---
            if gap <= BLIND_ZONE:
                print(f"\n🙈 ENTERING BLIND ZONE! Gap: {gap:.1f}cm (< {BLIND_ZONE}cm) | Dist: {target_dist:.1f}cm")
                break
                
            # --- STALKING MOVEMENT ---
            # 1. Calculate new reach (Move forward gently)
            # Step size proportional to gap, but max 1cm for smooth approach
            # We want to INCREASE reach to close the gap.
            step = max(0.5, min(1.0, gap * 0.10))
            next_reach = curr_reach + step
            
            # 2. Solve IK for next reach
            angles = get_wrist_angles(next_reach, object_height_cm=5.0)
            if angles is None:
                # Fallback: If we are close (gap < 10), try to just reach max and grab?
                # For now, just stop to prevent crash
                print(f"❌ Reach limit encountered! ({next_reach:.1f}cm)")
                if gap < 10.0:
                    print("⚠️ Close enough? Attempting Blind Grab from here...")
                    last_target_dist = gap # Update last known
                    break # Force jump to stage 3
                return
            
            sh_target, el_target = angles
            el_target = min(150, el_target) # Safety caps
            
            # 3. Calculate Base Correction (Smoother)
            # We correct X even while moving Z
            base_corr = error_x * GAIN_X_STALK
            base_corr = max(-MAX_BASE_STEP, min(MAX_BASE_STEP, base_corr))
            
            new_base = current_base + base_corr
            new_base = max(0, min(180, new_base))
            
            # Move Robot
            status_icon = "✓" if abs(error_x) < 20 else "drift"
            print(f"STALK: Dist={target_dist:.1f}cm | Gap={gap:.1f}cm | Step={step:.1f} | X-Err={error_x:+3.0f} ({status_icon})")
            
            self.robot.move_to([new_base, sh_target, el_target, wrist_pitch, wrist_roll, 170])
            
            current_base = new_base
            iteration += 1
            time.sleep(0.1) # Stabilization delay
            
            
        # --- STAGE 3: BLIND COMMIT ---
        print("\n" + "=" * 60)
        print("👊 STAGE 3: BLIND COMMIT (Open Loop Grab)")
        print("=" * 60)
        
        # Use last known target distance to finalize the grab
        # We add a small over-reach (1.0cm) to ensure the gripper surrounds the object
        # Since last_target_dist is the GAP, we need to add it to current reach.
        curr_pos = compute_forward_kinematics(self.robot.current_angles)
        curr_reach = math.sqrt(curr_pos[0]**2 + curr_pos[1]**2)
        
        final_reach = curr_reach + last_target_dist + 1.5 
        print(f"Pushing blindly to final reach: {final_reach:.1f}cm (Current: {curr_reach:.1f}cm + Gap: {last_target_dist:.1f}cm + 1.5cm)")
        
        final_angles = get_wrist_angles(final_reach, object_height_cm=5.0)
        if final_angles:
             s, e = final_angles
             e = min(150, e)
             self.robot.move_to([current_base, s, e, wrist_pitch, wrist_roll, 170])
             time.sleep(0.5)
        else:
            print("❌ Could not compute final grab angles.")
            return

        # Close Gripper
        print("🤏 CLOSING GRIPPER (Force)")
        self.robot.move_to([current_base, s, e, wrist_pitch, wrist_roll, 90]) # Tight grip
        time.sleep(1.0)
        
        # Lift
        print("📦 LIFTING OBJECT")
        s_lift = max(0, min(180, s + 20)) # Lift 20 deg
        self.robot.move_to([current_base, s_lift, e, wrist_pitch, wrist_roll, 90])
        time.sleep(0.5)
        
        print("\n✅ GRAB SEQUENCE COMPLETE!")
