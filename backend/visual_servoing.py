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
        self.thread = None
        self.frame_count = 0
        self.state = "SEARCHING" # Start in searching mode so it moves immediately
        self.search_dir = 1 # Start sweeping UP from 0
        self.missed_frames = 0
        
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
            
            # Get detection
            _ = self.camera.get_frame()
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
                print(f"[Frame {self.frame_count}] ✅ FULLY CENTERED! X={error_x}px, Y={error_y}px")
                time.sleep(0.5)
                continue
            
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
                new_elbow = max(SERVO_MIN, min(SERVO_MAX, new_elbow)) # Safety limits
                
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


