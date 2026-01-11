import time
import threading
import math

class LiveModeController:
    def __init__(self, robot_driver):
        self.arm = robot_driver
        self.running = False
        self.thread = None
        
        # Center positions to drift around
        self.center_angles = [90, 90, 90, 90, 90, 90] 
        
        self.update_interval = 0.04 # 25 Hz updates (Slightly faster)

    def start(self):
        """Starts the live mode behavior."""
        if self.running:
            return
            
        print("[LiveMode] Starting with Coupled Motion...")
        
        if self.arm:
            self.center_angles = list(self.arm.current_angles)
            print(f"[LiveMode] Centered at: {self.center_angles}")
        
        self.running = True
        self.thread = threading.Thread(target=self._behavior_loop, daemon=True)
        self.thread.start()

    def stop(self):
        """Stops the live mode behavior."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
        print("[LiveMode] Stopped.")

    def _behavior_loop(self):
        t = 0.0
        while self.running:
            if not self.arm:
                time.sleep(1)
                continue
                
            # --- Coupled Sine Wave Generators ---
            # We use t (time) to drive coordinated functions.
            
            # 1. Base Sway (Servo 0)
            # A slow, wide side-to-side motion.
            # Amp: 30 deg, Freq: 0.8 rad/s (approx 8s period)
            base_offset = 30.0 * math.sin(0.8 * t)
            
            # 2. Breathing (Shoulder Servo 1 & Elbow Servo 2)
            # Coordinated heavy breathing.
            # Shoulder goes UP (negative offset) while Elbow goes DOWN (negative offset)
            # Actually, to keep the hand somewhat steady but "heave" the chest:
            # Shoulder and Elbow should move in opposite phase?
            # Let's try "Heaving": Shoulder Up/Down, Elbow compensates slightly.
            # Freq: 1.5 rad/s (approx 4s period - standard breathe rate)
            
            breathe_wave = math.sin(1.5 * t)
            
            shoulder_offset = 15.0 * breathe_wave       # +/- 15 deg
            elbow_offset = -10.0 * breathe_wave         # +/- 10 deg (Opposite phase to shoulder)
            
            # 3. Gripper Twitch (Servo 5)
            # A faster "nervous" tic or tension check.
            # Freq: 3.0 rad/s
            gripper_offset = 12.0 * math.sin(3.0 * t) + 5.0 * math.sin(7.0 * t) # Interference pattern

            # --- Apply and Clamp ---
            new_angles = list(self.center_angles)
            
            # Base
            new_angles[0] += base_offset
            
            # Shoulder
            new_angles[1] += shoulder_offset
            
            # Elbow
            new_angles[2] += elbow_offset
            
            # Gripper
            new_angles[5] += gripper_offset

            # Clamp and Convert
            final_angles = [max(0, min(180, int(a))) for a in new_angles]
            
            # Keep Wrist Fixed (3 & 4) at center (or current?)
            # User said "dont move the writ roll and pitch".
            # So we enforce them to stay at center_angles[3] and [4]
            final_angles[3] = self.center_angles[3]
            final_angles[4] = self.center_angles[4]

            # Move
            self.arm.move_to(final_angles)
            
            # Increment time
            t += self.update_interval
            time.sleep(self.update_interval)
