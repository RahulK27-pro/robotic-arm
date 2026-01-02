import msvcrt
import time
import threading

class KeyboardController:
    def __init__(self, robot_arm):
        """
        Initialize keyboard controller for the robotic arm.
        :param robot_arm: Instance of RobotArm class
        """
        self.robot = robot_arm
        self.running = False
        self.thread = None
        
        # Step sizes
        self.step_angle = 1
        
        # Key mappings help text
        self.help_text = """
==================================================
🎹 MANUAL KEYBOARD CONTROL ACTIVE
--------------------------------------------------
  W / S      : Shoulder Up / Down
  A / D      : Elbow Up / Down
  ← / →      : Base Left / Right
  I / K      : Wrist Pitch Up / Down
  J / L      : Wrist Roll Left / Right
  G          : Toggle Gripper (Open/Close)
  Q          : Quit Manual Control (stops listener)
==================================================
"""
        
    def start(self):
        """Start the keyboard listener in a background thread."""
        if self.running:
            return
            
        self.running = True
        self.thread = threading.Thread(target=self._msg_loop, daemon=True)
        self.thread.start()
        print(self.help_text)

    def stop(self):
        """Stop the keyboard listener."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
            
    def _msg_loop(self):
        """Main loop for checking key presses."""
        print("[KeyboardController] Listener started. Focus terminal to control.")
        
        while self.running:
            if msvcrt.kbhit():
                key_bytes = msvcrt.getch()
                
                try:
                    # Handle special keys (arrows often come as two bytes)
                    if key_bytes == b'\xe0': # Special key prefix
                        special_key = msvcrt.getch()
                        self._handle_special_key(special_key)
                    else:
                        char = key_bytes.decode('utf-8').lower()
                        self._handle_char_key(char)
                        
                except Exception as e:
                    print(f"[KeyboardController] Error processing key: {e}")
            
            # Small sleep to prevent CPU hogging
            time.sleep(0.05)

    def _handle_special_key(self, code):
        """Handle arrow keys and other special keys."""
        updated = False
        current_angles = list(self.robot.current_angles)
        
        # Base is index 0
        
        # Arrow Keys for Base
        if code == b'K': # Left Arrow
            current_angles[0] = min(180, current_angles[0] + self.step_angle)
            updated = True
        elif code == b'M': # Right Arrow
            current_angles[0] = max(0, current_angles[0] - self.step_angle)
            updated = True
            
        if updated:
            self.robot.move_to(current_angles)

    def _handle_char_key(self, char):
        """Handle standard character keys."""
        updated = False
        current_angles = list(self.robot.current_angles)
        
        # Mapping constants based on robot_driver.py usually:
        # 0: Base, 1: Shoulder, 2: Elbow, 3: Wrist Pitch, 4: Wrist Roll, 5: Gripper
        
        if char == 'w': # Shoulder Up
            current_angles[1] = min(180, current_angles[1] + self.step_angle)
            updated = True
        elif char == 's': # Shoulder Down
            current_angles[1] = max(0, current_angles[1] - self.step_angle)
            updated = True
            
        elif char == 'd': # Elbow Up 
            current_angles[2] = min(180, current_angles[2] + self.step_angle)
            updated = True
        elif char == 'a': # Elbow Down
            current_angles[2] = max(0, current_angles[2] - self.step_angle)
            updated = True
            
        elif char == 'i': # Wrist Pitch Up
            current_angles[3] = min(180, current_angles[3] + self.step_angle)
            updated = True
        elif char == 'k': # Wrist Pitch Down
            current_angles[3] = max(0, current_angles[3] - self.step_angle)
            updated = True
            
        elif char == 'j': # Wrist Roll Left
            current_angles[4] = max(0, current_angles[4] - self.step_angle)
            updated = True
        elif char == 'l': # Wrist Roll Right
            current_angles[4] = min(180, current_angles[4] + self.step_angle)
            updated = True
            
        elif char == 'g': # Gripper Toggle
            # Assuming > 90 is OPEN, < 90 is CLOSED, or vice versa.
            # Usually 170 is OPEN, 90 is CLOSED.
            if current_angles[5] > 120:
                current_angles[5] = 90 # Close
                print("\n[Gripper] Closing")
            else:
                current_angles[5] = 170 # Open
                print("\n[Gripper] Opening")
            updated = True
            
        elif char == 'q':
            print("\n[KeyboardController] Quitting manual control...")
            self.running = False
            return

        if updated:
            self.robot.move_to(current_angles)
