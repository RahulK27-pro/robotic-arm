import time
import serial
from serial import SerialException
from brain.kinematics import solve_angles, compute_forward_kinematics

class RobotArm:
    def __init__(self, simulation_mode=True, port='COM4', baudrate=115200, timeout=0.05):
        """
        Initialize the Robotic Arm controller.
        
        Args:
            simulation_mode (bool): If True, runs in simulation without hardware
            port (str): Serial port for Arduino (e.g., 'COM4' on Windows)
            baudrate (int): Baud rate for serial communication (default: 115200)
            timeout (int): Serial read timeout in seconds
        """
        self.simulation_mode = simulation_mode
        self.current_angles = [0, 130, 130, 90, 12, 170]  # Default neutral position
        self.serial = None
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        
        if self.simulation_mode:
            print("🤖 RobotArm initialized in SIMULATION MODE.")
        else:
            print(f"🔌 RobotArm initialized in HARDWARE MODE on {port} @ {baudrate} baud.")
            try:
                self._connect_serial()
            except SerialException as e:
                print(f"❌ Failed to connect to Arduino: {e}")
                print("⚠️  Falling back to SIMULATION MODE.")
                self.simulation_mode = True

    def _connect_serial(self):
        """Establish serial connection to Arduino."""
        if self.serial is not None and self.serial.is_open:
            return  # Already connected
        
        try:
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout
            )
            time.sleep(2)  # Wait for Arduino to reset after connection
            print(f"✅ Serial connection established on {self.port}")
            
            # Flush any startup messages
            if self.serial.in_waiting:
                startup_msg = self.serial.read_all().decode('utf-8', errors='ignore')
                print(f"📟 Arduino startup: {startup_msg.strip()}")
                
        except SerialException as e:
            raise SerialException(f"Could not open serial port {self.port}: {e}")

    def move_to(self, angles, speed=1.0):
        """
        Moves the robot to the specified angles.
        
        Args:
            angles (list): List of 6 integers [base, shoulder, elbow, wrist_pitch, wrist_roll, gripper]
                          Each value should be 0-180 degrees
            speed (float): Speed multiplier (not used in simple implementation)
        
        Returns:
            bool: True if successful, False otherwise
        """
        # Validate input
        if len(angles) != 6:
            print(f"❌ Error: Expected 6 angles, got {len(angles)}")
            return False
        
        # Clamp angles to 0-180 range
        clamped_angles = [max(0, min(180, int(angle))) for angle in angles]
        
        # -----------------------------------------------------------------
        # SAFETY LIMITS (HARDWARE PROTECTION)
        # -----------------------------------------------------------------
        # Elbow (Index 2): Max 150°
        if clamped_angles[2] > 150:
            print(f"⚠️ SAFETY: Clamping Elbow from {clamped_angles[2]}° to 150°")
            clamped_angles[2] = 150
            
        # Gripper (Index 5): Min 120°, Max 170°
        if clamped_angles[5] < 120:
             print(f"⚠️ SAFETY: Clamping Gripper from {clamped_angles[5]}° to 120°")
             clamped_angles[5] = 120
        elif clamped_angles[5] > 170:
             print(f"⚠️ SAFETY: Clamping Gripper from {clamped_angles[5]}° to 170°")
             clamped_angles[5] = 170
        # -----------------------------------------------------------------
        
        # Prepare angles for hardware (Invert Wrist Roll at index 4)
        # User sees 0-180, Hardware needs 180-0 for this specific servo
        hardware_angles = list(clamped_angles)
        hardware_angles[4] = 180 - hardware_angles[4]
        
        if self.simulation_mode:
            # Simulation mode output
            packet = f"<{','.join(map(str, hardware_angles))}>"
            print(f"📤 Simulated Command: {packet}")
            print(f"   [Base: {clamped_angles[0]}°, Shoulder: {clamped_angles[1]}°, Elbow: {clamped_angles[2]}°, WristV: {clamped_angles[3]}°, WristR: {clamped_angles[4]}°(Inv), Grip: {clamped_angles[5]}°]")
            
            # Interpolate movement for smoothness (1.0 second duration)
            duration = 1.0
            steps = 20
            dt = duration / steps
            start_angles = list(self.current_angles)
            
            for step in range(1, steps + 1):
                t = step / steps
                # Linear interpolation
                interp_angles = []
                for i in range(6):
                    val = start_angles[i] + (clamped_angles[i] - start_angles[i]) * t
                    interp_angles.append(val)
                
                self.current_angles = interp_angles
                time.sleep(dt)
            
            self.current_angles = clamped_angles # Ensure final exact value
            return True
        
        else:
            # Hardware mode - send via serial
            try:
                # Ensure serial connection is open
                if self.serial is None or not self.serial.is_open:
                    self._connect_serial()
                
                # Format packet: <90,45,120,90,90,10>
                # Use hardware_angles for transmission
                int_angles = [int(a) for a in hardware_angles]
                packet = f"<{','.join(map(str, int_angles))}>"
                
                # Send packet WITH newline terminator
                self.serial.write((packet + '\n').encode('utf-8'))
                print(f"📤 Sent to Arduino: {packet} (User WristRoll: {clamped_angles[4]}° -> HW: {hardware_angles[4]}°)")

                
                # Wait for confirmation from Arduino
                # Try to read the "K", but don't crash if we miss it
                try:
                    response = self.serial.readline().decode().strip()
                    if response == 'K':
                        print("✅ Arduino confirmed")
                    elif response:
                        print(f"⚠️  Arduino sent: '{response}' (expected 'K')")
                except:
                    pass # For a slider, it's okay to skip a confirmation occasionally

                
                self.current_angles = clamped_angles # Store USER angles
                return True
                
            except SerialException as e:
                print(f"❌ Serial Communication Error: {e}")
                print("💡 Check if USB cable is connected and Arduino is powered.")
                return False
            except Exception as e:
                print(f"❌ Unexpected error during move_to: {e}")
                return False

    def move_to_sequenced(self, target_angles, speed=1.0):
        """
        Moves the robot to the specified angles one servo at a time (Bottom to Top).
        
        Args:
            target_angles (list): List of 6 integers [base, shoulder, elbow, wrist_pitch, wrist_roll, gripper]
            speed (float): Speed multiplier
        
        Returns:
            bool: True if all steps successful, False otherwise
        """
        # Validate input
        if len(target_angles) != 6:
            print(f"❌ Error: Expected 6 angles, got {len(target_angles)}")
            return False
        
        # Clamp angles
        clamped_target = [max(0, min(180, int(angle))) for angle in target_angles]
        
        print(f"🔄 Starting Sequenced Move: {self.current_angles} -> {clamped_target}")
        
        # Iterate through each servo (0 to 5)
        for i in range(6):
            # Create a temporary target that only changes the current servo
            # We want to keep previous changes, so we start with self.current_angles
            # But wait, self.current_angles is updated after each move_to call
            # So we can just copy self.current_angles and update the i-th element
            
            # Actually, move_to updates self.current_angles.
            # So we just need to construct the next step's full configuration.
            
            next_step_angles = list(self.current_angles)
            next_step_angles[i] = clamped_target[i]
            
            # Skip if angle is already correct (optimization)
            if abs(self.current_angles[i] - clamped_target[i]) < 1:
                continue
                
            print(f"   👉 Moving Servo {i} to {clamped_target[i]}°")
            success = self.move_to(next_step_angles, speed)
            
            if not success:
                print(f"❌ Sequenced move failed at servo {i}")
                return False
                
            # Small delay between servos for visual clarity / stability
            time.sleep(0.1)
            
        return True

    def get_status(self):
        """Get current robot status."""
        return {
            "angles": self.current_angles,
            "mode": "simulation" if self.simulation_mode else "hardware",
            "port": self.port if not self.simulation_mode else None,
            "connected": self.serial.is_open if self.serial else False
        }
    
    def read_sensors(self):
        """
        Request distance data from Arduino (e.g., HC-SR04).
        Returns:
            float: Distance in cm, or -1 if failed.
        """
        if self.simulation_mode:
            return 999.0 # Simulate "far away" if no hardware
        
        try:
            if self.serial is None or not self.serial.is_open:
                return -1.0
                
            # Send request
            self.serial.write(b'<GET_DIST>\n')
            
            # Read response: <12.5>
            response = self.serial.readline().decode().strip()
            
            if response.startswith('<') and response.endswith('>'):
                dist_str = response[1:-1]
                return float(dist_str)
            else:
                return -1.0
                
        except Exception as e:
            print(f"❌ Sensor read error: {e}")
            return -1.0

    def update_target_coordinate(self, dx, dy, dz, pitch=-90, roll=0):
        """
        Apply Cartesian delta to current position and move robot.
        
        Args:
            dx, dy, dz: Changes in mm/cm (depends on kinematics units, assumed cm)
            pitch, roll: Target orientation (default -90 vertical down)
        
        Returns:
            bool: True if move successful (reachable), False otherwise
        """
        try:
            # 1. Get current position using Forward Kinematics
            current_pos = compute_forward_kinematics(self.current_angles)
            curr_x, curr_y, curr_z = current_pos
            
            # 2. Calculate new target
            target_x = curr_x + dx
            target_y = curr_y + dy
            target_z = curr_z + dz
            
            # 3. Solve Inverse Kinematics for new target
            # Note: solve_angles might raise ValueError if out of reach
            new_angles = solve_angles(target_x, target_y, target_z, pitch, roll)
            
            # Preserve gripper angle
            new_angles[5] = self.current_angles[5]
            
            # Print Verbose Feedback for User
            # Format: [Base, Shldr, Elbw, W1, W2, Grip]
            diffs = [round(new_angles[i] - self.current_angles[i], 1) for i in range(6)]
            print(f"🔄 ADJUST: {self.current_angles} -> {new_angles} (Deltas: {diffs})")
            
            # 4. Move robot
            # Use faster Move_To for servoing
            return self.move_to(new_angles)
            
        except ValueError as e:
            print(f"⚠️ Target out of reach: {e}")
            return False
        except Exception as e:
            print(f"❌ update_target_coordinate error: {e}")
            return False



    def close(self):
        """Close serial connection gracefully."""
        if self.serial and self.serial.is_open:
            self.serial.close()
            print(f"🔌 Serial connection to {self.port} closed.")

    def __del__(self):
        """Destructor to ensure serial port is closed."""
        self.close()
