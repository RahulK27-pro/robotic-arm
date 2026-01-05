import time
import threading

class GreetingBehavior:
    def __init__(self, robot_driver):
        self.arm = robot_driver

    def set_servo_angle(self, servo_id, angle):
        """Helper to set a single servo angle."""
        if not self.arm:
            return
            
        # Get current angles
        angles = list(self.arm.current_angles)
        
        # Update specific servo
        if 0 <= servo_id < len(angles):
            angles[servo_id] = angle
            self.arm.move_to(angles)
        else:
            print(f"[Greeting] Invalid servo ID: {servo_id}")

    def perform_wave(self):
        print("👋 Waving at human!")
        
        # Store previous position to return to
        previous_angles = list(self.arm.current_angles)
        
        # 1. Move to "High Five" / Upright position
        # Base: Center(90), Shoulder: Up(110), Elbow: Straight up(160), Wrist: Straight(90)
        # Note: Adjusting based on user snippet and standard servo ranges
        wave_pose = [90, 110, 160, 90, 90, 90]
        self.arm.move_to(wave_pose) 
        time.sleep(0.5)

        # 2. The Waving Loop (Wrist Roll Left/Right)
        # Servo 4 is Wrist Roll (index 4). Wait, user said "Servo 5 (Wrist Roll)".
        # Let's check robot driver. 
        # robot_driver.py: [Base, Shoulder, Elbow, WristV, WristR, Gripper]
        # Indices: 0, 1, 2, 3, 4, 5.
        # User said "Servo 5 (Wrist Roll)". 
        # In robot_driver.py, index 5 is Gripper. Index 4 is WristR.
        # User might be using 1-based indexing or has a different mapping.
        # "Wrist Roll (Servo 5)" -> If 1-based, that's index 4.
        # "We wag Servo 5 (Wrist Roll)" -> Context suggests Wrist Roll.
        # I will assume Index 4 (Wrist Roll) is intended, but if user specifically mapped it...
        # robot_driver.py comment line 104: WristR: {clamped_angles[4]}
        # So I will use index 4 for Wrist Roll.
        
        WRIST_ROLL_IDX = 4
        
        for _ in range(3): # Wave 3 times
            # Tilt Wrist Left
            self.set_servo_angle(WRIST_ROLL_IDX, 45) 
            time.sleep(0.2)
            
            # Tilt Wrist Right
            self.set_servo_angle(WRIST_ROLL_IDX, 135)
            time.sleep(0.2)

        # 3. Return to Neutral / Center for wrist
        self.set_servo_angle(WRIST_ROLL_IDX, 90)
        time.sleep(0.5)
        
        # Optional: Bow slightly (polite robot)
        # move_to_instant([90, 100, 140, 90, 90, 90])
        self.arm.move_to([90, 100, 140, 90, 90, 90])
        time.sleep(1.0)
        
        # Return to previous position or stay in idle?
        # User script didn't say to return capable, but robot_state=IDLE suggests we are done.
        # I'll leave it at the "Bow" position as a finished state or go to default idle.
        # self.arm.move_to(previous_angles) 

class GreetingController:
    def __init__(self, robot_driver, camera):
        self.greeter = GreetingBehavior(robot_driver)
        self.camera = camera
        self.running = False
        self.thread = None
        self.lock = threading.Lock()
        
        # Settings
        self.WAVE_COOLDOWN = 10.0  # Seconds
        self.last_wave_time = 0
        self.active = False # State flag

    def start_background_monitoring(self):
        """Starts the background thread looking for humans."""
        if self.running:
            return
            
        self.running = True
        self.active = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
        print("[Greeting] Background monitoring started.")

    def stop(self):
        self.running = False
        self.active = False
        if self.thread:
            self.thread.join(timeout=1.0)
        print("[Greeting] Monitoring stopped.")

    def _monitor_loop(self):
        print("[Greeting] Loop running...")
        while self.running:
            time.sleep(0.1) # Check rate
            
            # Check cooldown
            current_time = time.time()
            if (current_time - self.last_wave_time) < self.WAVE_COOLDOWN:
                continue

            # Check for person in latest detections
            detections = self.camera.last_detection
            person_found = False
            
            for det in detections:
                if det['object_name'] == 'person' and det['confidence'] > 0.6:
                    person_found = True
                    break
            
            if person_found:
                print("[Greeting] Person detected! Initiating wave...")
                
                # Execute wave
                # Warning: This blocks the monitoring, which is fine (we don't want to double wave)
                self.greeter.perform_wave()
                
                self.last_wave_time = time.time()
                print("[Greeting] Wave complete. Cooldown started.")

    def get_status(self):
        return {
            "active": self.active,
            "last_wave_time": self.last_wave_time,
            "cooldown_remaining": max(0, self.WAVE_COOLDOWN - (time.time() - self.last_wave_time))
        }
