import time
import threading
from hardware.robot_driver import RobotArm
from camera import VideoCamera

class VisualServoingAgent:
    """
    X-Axis Only Visual Servoing Agent
    
    Purpose: Center a target object horizontally by rotating the base servo.
    Other axes remain fixed.
    """
    
    def __init__(self, robot: RobotArm, camera: VideoCamera):
        self.robot = robot
        self.camera = camera
        self.running = False
        self.thread = None
        self.frame_count = 0
        self.state = "SEARCHING" # Start in searching mode so it moves immediately
        self.search_dir = 1 # Start sweeping UP from 0
        self.missed_frames = 0
        
        # Continuous grab settings
        self.enable_grab = True  # Enable automatic grab after centering
        self.centered_frames = 0  # Count consecutive centered frames
        self.required_centered_frames = 5  # Frames needed before approach
        self.grab_distance = 2.0  # cm - close gripper when this close
        
    def start(self, target_object_name):
        """Start X-axis servoing loop."""
        if self.running:
            return
            
        self.target_object = target_object_name
        self.camera.set_target_object(target_object_name)
        self.running = True
        
        self.thread = threading.Thread(target=self._servoing_loop, daemon=True)
        self.thread.start()
        print(f"🚀 X-Axis Servoing STARTED for '{target_object_name}'")
        
    def stop(self):
        """Stop servoing loop."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
        print("🛑 X-Axis Servoing STOPPED")
        
    def get_status(self):
        """Get current servoing status."""
        return {
            "active": self.running,
            "mode": "x_axis_only"
        }

    def _servoing_loop(self):
        """
        X/Y AXIS VISUAL SERVOING
        
        Controls base (X-axis) and elbow (Y-axis) to center target.
        """
        print("=" * 60)
        print("🎯 X/Y AXIS VISUAL SERVOING - STARTING")
        print("=" * 60)
        
        # Configuration (TUNED FOR STABILITY)
        GAIN_X = 0.02       # Reduced from 0.05 to reduce oscillation
        GAIN_Y = 0.02       # Reduced from 0.05 to reduce oscillation
        DEADZONE = 20       # Centered if error < 20px
        MAX_STEP = 2.0      # Limit max movement per frame to 2 degrees (Safety)
        
        # Servo Limits (Safety)
        SERVO_MIN = 0       # Updated to 0 to match requested start
        SERVO_MAX = 180     # Updated to 180 to match requested range
        
        # Fixed servo positions
        BASE_START = 0      # Requested: 0
        SHOULDER = 130      # Requested: 130
        ELBOW_START = 130   # Requested: 115
        WRIST_PITCH = 90    # Requested: 90
        WRIST_ROLL = 12     # Requested: 12
        GRIPPER = 170       # Requested: 170
        
        # Initialize
        print(f"Moving to starting position...")
        print(f"  Base: {BASE_START}° (will track X)")
        print(f"  Shoulder: {SHOULDER}° (fixed)")
        print(f"  Elbow: {ELBOW_START}° (will track Y)")
        print(f"  Wrist Pitch: {WRIST_PITCH}° (fixed)")
        print(f"  Wrist Roll: {WRIST_ROLL}° (fixed)")
        print(f"  Gripper: {GRIPPER}° (fixed)")
        
        # Smooth Startup: Interpolate from current position to start position
        # to prevent sudden jumps if the robot was in a different pose.
        start_angles = self.robot.current_angles
        target_angles = [BASE_START, SHOULDER, ELBOW_START, WRIST_PITCH, WRIST_ROLL, GRIPPER]
        
        steps = 40  # 2 seconds (at 0.05s per step)
        print(f"Moving to starting position (Smoothly over {steps} steps)...")
        
        for i in range(1, steps + 1):
            t = i / steps
            interp = []
            for j in range(6):
                val = start_angles[j] + (target_angles[j] - start_angles[j]) * t
                interp.append(val)
            
            self.robot.move_to(interp)
            time.sleep(0.05)
            
        # Ensure we are exactly at target
        self.robot.move_to(target_angles)
        time.sleep(1.5)
        
        current_base = BASE_START
        current_elbow = ELBOW_START
        print("\n✅ Ready! Tracking X/Y...\n")
        
        # Main loop
        while self.running:
            self.frame_count += 1
            
            # detections are now updated in the background thread!
            # We just poll the latest results.
            detections = self.camera.last_detection
            
            # If no detection, wait a bit for the background thread to catch up
            if not detections:
                time.sleep(0.1)
                detections = self.camera.last_detection

            
            # -----------------------------------------------------------------
            # STATE: SEARCHING (No Object Detected)
            # -----------------------------------------------------------------
            if not detections:
                self.missed_frames += 1
                
                # Only switch to SEARCHING if we've lost target for 5+ frames
                if self.state == "TRACKING":
                    if self.missed_frames < 5:
                        print(f"[Frame {self.frame_count}] ⚠️ Target lost ({self.missed_frames}/5)... Holding position.")
                        time.sleep(0.05)
                        continue
                    else:
                        print(f"[Frame {self.frame_count}] ❌ Target confirmed lost! Switching to SEARCHING...")
                        self.state = "SEARCHING"
                
                # Perform Sweep Step (Only if genuinely searching)
                step = 3.0 
                new_base = current_base + (self.search_dir * step)
                
                # Check bounds and flip direction
                if new_base <= SERVO_MIN:
                    new_base = SERVO_MIN
                    self.search_dir = 1 
                    print(f"[Frame {self.frame_count}] 🔄 Reached Min. Sweeping UP...")
                elif new_base >= SERVO_MAX:
                    new_base = SERVO_MAX
                    self.search_dir = -1 
                    print(f"[Frame {self.frame_count}] 🔄 Reached Max. Sweeping DOWN...")
                
                # Move only Base
                print(f"[Frame {self.frame_count}] 🔍 SEARCHING... Base: {current_base:.1f}° → {new_base:.1f}°")
                self.robot.move_to([new_base, SHOULDER, ELBOW_START, WRIST_PITCH, WRIST_ROLL, GRIPPER])
                current_base = new_base
                
                time.sleep(0.05)
                continue

            # -----------------------------------------------------------------
            # STATE: TRACKING (Object Detected)
            # -----------------------------------------------------------------
            # Reset missed frames count on any valid detection
            self.missed_frames = 0
            
            if self.state == "SEARCHING":
                print(f"[Frame {self.frame_count}] 🎯 Target FOUND! Switching to TRACKING...")
                self.state = "TRACKING"
                # FIX: Sync current_elbow to current physical position (ELBOW_START)
                # Otherwise it jumps back to the old 'last known' Y-angle from previous tracking
                current_elbow = ELBOW_START 
            
            # Extract X and Y errors
            error_x = detections[0]['error_x']
            error_y = detections[0]['error_y']
            
            # Check centering status
            x_centered = abs(error_x) < DEADZONE
            y_centered = abs(error_y) < DEADZONE
            
            if x_centered and y_centered:
                # Object is centered!
                self.centered_frames += 1
                print(f"[Frame {self.frame_count}] ✅ FULLY CENTERED! X={error_x}px, Y={error_y}px ({self.centered_frames}/{self.required_centered_frames})")
                
                # Check if we should start approaching
                if self.enable_grab and self.centered_frames >= self.required_centered_frames:
                    print("\n" + "=" * 60)
                    print("🚀 CENTERING COMPLETE! Starting APPROACH mode...")
                    print("=" * 60)
                    self.state = "APPROACHING"
                    self.centered_frames = 0
                    
                    # Open gripper
                    print("Opening gripper...")
                    self.robot.move_to([current_base, SHOULDER, current_elbow, WRIST_PITCH, WRIST_ROLL, 170])
                    time.sleep(0.5)
                    
                    # Start approach loop
                    self._approach_and_grab(current_base, SHOULDER, current_elbow, WRIST_PITCH, WRIST_ROLL)
                    return  # Exit servoing loop
                
                time.sleep(0.1)
                continue
            else:
                # Not centered, reset counter
                self.centered_frames = 0
            
            # SEQUENTIAL LOGIC: X First, Then Y
            if not x_centered:
                # ---------------------------------------------------------
                # PHASE 1: X-Axis Correction (Base)
                # ---------------------------------------------------------
                # error_x > 0: object LEFT → rotate RIGHT → INCREASE angle
                raw_correction = (error_x * GAIN_X)
                
                # Clamp step size to prevent jumping
                correction_x = max(-MAX_STEP, min(MAX_STEP, raw_correction))
                
                new_base = current_base + correction_x
                new_base = max(SERVO_MIN, min(SERVO_MAX, new_base)) # Safety limits
                
                # Y stays fixed
                new_elbow = current_elbow
                
                dir_x = "RIGHT" if correction_x > 0 else "LEFT"
                print(f"[Frame {self.frame_count}] X-ALIGN: {error_x:+4.0f}px → {dir_x} {abs(correction_x):.2f}° (Base: {current_base:.1f}°→{new_base:.1f}°)")
                
            else:
                # ---------------------------------------------------------
                # PHASE 2: Y-Axis Correction (Elbow) - Only after X is good
                # ---------------------------------------------------------
                # User Feedback: "increasing angle moves down, decreasing moves up"
                # If Object is UP (error_y > 0), we need to move UP.
                # So we need to DECREASE angle.
                # Formula: correction = -(error * gain)
                
                raw_correction = -(error_y * GAIN_Y)
                
                # Clamp step size
                correction_y = max(-MAX_STEP, min(MAX_STEP, raw_correction))
                
                new_elbow = current_elbow + correction_y
                # SAFETY: Cap elbow at 150° maximum
                new_elbow = max(SERVO_MIN, min(150, new_elbow))  # Changed from SERVO_MAX to 150
                
                # X stays fixed
                new_base = current_base
                
                dir_y = "UP" if correction_y < 0 else "DOWN"
                print(f"[Frame {self.frame_count}] Y-ALIGN: {error_y:+4.0f}px → {dir_y} {abs(correction_y):.2f}° (Elbow: {current_elbow:.1f}°→{new_elbow:.1f}°)")
            
            # Move servos
            angles_to_send = [new_base, SHOULDER, new_elbow, WRIST_PITCH, WRIST_ROLL, GRIPPER]
            self.robot.move_to(angles_to_send)
            
            current_base = new_base
            current_elbow = new_elbow
            
            time.sleep(0.05)
    
    def _approach_and_grab(self, base, shoulder, elbow, wrist_pitch, wrist_roll):
        """
        Approach object while maintaining center alignment.
        Moves shoulder and elbow based on distance, adjusts base for X-centering.
        """
        from brain.visual_ik_solver import get_wrist_angles, check_reachability
        
        print("\n🚀 PHASE: APPROACHING WITH ALIGNMENT")
        print("-" * 60)
        
        GAIN_X = 0.03
        MAX_BASE_STEP = 2.0
        DEADZONE = 20
        MAX_ITERATIONS = 100
        TIMEOUT = 30.0
        
        current_base = base
        start_time = time.time()
        iteration = 0
        
        while self.running and iteration < MAX_ITERATIONS:
            # Check timeout
            if time.time() - start_time > TIMEOUT:
                print("❌ Approach timeout")
                return
            
            # Get detection
            detections = self.camera.last_detection
            if not detections:
                print(f"[{iteration}] ⚠️ Object lost")
                time.sleep(0.1)
                iteration += 1
                continue
            
            det = detections[0]
            error_x = det.get('error_x', 0)
            distance_cm = det.get('distance_cm', -1)
            
            if distance_cm <= 0:
                print(f"[{iteration}] ⚠️ Cannot estimate distance")
                time.sleep(0.1)
                iteration += 1
                continue
            
            # Check if within grab range
            if distance_cm <= self.grab_distance:
                print(f"\n✅ OBJECT WITHIN REACH! Distance: {distance_cm:.1f}cm")
                break
            
            # Check reachability
            reachable, reason, _ = check_reachability(distance_cm, object_height_cm=5.0)
            if not reachable:
                print(f"❌ {reason}")
                return
            
            # Calculate IK for current distance
            angles = get_wrist_angles(distance_cm, object_height_cm=5.0)
            if angles is None:
                print(f"❌ IK failed for distance {distance_cm:.1f}cm")
                return
            
            shoulder_target, elbow_target = angles
            
            # SAFETY: Cap elbow at 150° maximum
            elbow_target = min(150, elbow_target)
            
            # Calculate base adjustment for X-centering
            base_correction = error_x * GAIN_X
            base_correction = max(-MAX_BASE_STEP, min(MAX_BASE_STEP, base_correction))
            
            new_base = current_base + base_correction
            new_base = max(0, min(180, new_base))
            
            # Check if centered
            is_centered = abs(error_x) < DEADZONE
            center_status = "✓" if is_centered else "✗"
            
            print(f"[{iteration:3d}] Dist:{distance_cm:5.1f}cm | ErrX:{error_x:+4.0f}px | Centered:{center_status} | Base:{current_base:.0f}°→{new_base:.0f}° | Sh:{shoulder_target:.0f}° El:{elbow_target:.0f}°")
            
            # Move robot
            self.robot.move_to([new_base, shoulder_target, elbow_target, wrist_pitch, wrist_roll, 170])
            
            current_base = new_base
            iteration += 1
            time.sleep(0.15)
        
        # Close gripper
        print("\n🤏 CLOSING GRIPPER")
        print("-" * 60)
        self.robot.move_to([current_base, shoulder_target, elbow_target, wrist_pitch, wrist_roll, 120])
        time.sleep(0.8)
        
        # Lift
        print("\n📦 LIFTING OBJECT")
        print("-" * 60)
        shoulder_target += 15
        shoulder_target = min(180, shoulder_target)
        self.robot.move_to([current_base, shoulder_target, elbow_target, wrist_pitch, wrist_roll, 120])
        time.sleep(0.5)
        
        print("\n" + "=" * 60)
        print("✅ GRAB COMPLETE!")
        print("=" * 60)

