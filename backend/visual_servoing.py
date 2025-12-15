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
        self.state = "TRACKING"
        self.search_dir = -1 # -1 for down, 1 for up
        
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
        SERVO_MIN = 10
        SERVO_MAX = 170
        
        # Fixed servo positions
        BASE_START = 90
        SHOULDER = 90
        ELBOW_START = 112
        WRIST_PITCH = 90
        WRIST_ROLL = 12
        GRIPPER = 0
        
        # Initialize
        print(f"Moving to starting position...")
        print(f"  Base: {BASE_START}° (will track X)")
        print(f"  Shoulder: {SHOULDER}° (fixed)")
        print(f"  Elbow: {ELBOW_START}° (will track Y)")
        print(f"  Wrist Pitch: {WRIST_PITCH}° (fixed)")
        print(f"  Wrist Roll: {WRIST_ROLL}° (fixed)")
        print(f"  Gripper: {GRIPPER}° (fixed)")
        
        self.robot.move_to([BASE_START, SHOULDER, ELBOW_START, WRIST_PITCH, WRIST_ROLL, GRIPPER])
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
                if self.state == "TRACKING":
                    print(f"[Frame {self.frame_count}] ⚠️ Target lost! Switching to SEARCHING...")
                    self.state = "SEARCHING"
                    # Default search direction: Downwards (towards 0) first, as requested
                    self.search_dir = -1 
                
                # Perform Sweep Step
                step = 1.0 # Slow search speed (1 degree per frame)
                new_base = current_base + (self.search_dir * step)
                
                # Check bounds and flip direction
                if new_base <= SERVO_MIN:
                    new_base = SERVO_MIN
                    self.search_dir = 1 # Switch to Upwards
                    print(f"[Frame {self.frame_count}] 🔄 Reached Min. Sweeping UP...")
                elif new_base >= SERVO_MAX:
                    new_base = SERVO_MAX
                    self.search_dir = -1 # Switch to Downwards
                    print(f"[Frame {self.frame_count}] 🔄 Reached Max. Sweeping DOWN...")
                
                # Move only Base
                print(f"[Frame {self.frame_count}] 🔍 SEARCHING... Base: {current_base:.1f}° → {new_base:.1f}°")
                self.robot.move_to([new_base, SHOULDER, ELBOW_START, WRIST_PITCH, WRIST_ROLL, GRIPPER])
                current_base = new_base
                
                # Don't sleep too long to keep search smooth
                time.sleep(0.05)
                continue

            # -----------------------------------------------------------------
            # STATE: TRACKING (Object Detected)
            # -----------------------------------------------------------------
            if self.state == "SEARCHING":
                print(f"[Frame {self.frame_count}] 🎯 Target FOUND! Switching to TRACKING...")
                self.state = "TRACKING"
            
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


