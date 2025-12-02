import time
import serial
from serial import SerialException

class RobotArm:
    def __init__(self, simulation_mode=True, port='COM4', baudrate=115200, timeout=2):
        """
        Initialize the Robotic Arm controller.
        
        Args:
            simulation_mode (bool): If True, runs in simulation without hardware
            port (str): Serial port for Arduino (e.g., 'COM4' on Windows)
            baudrate (int): Baud rate for serial communication (default: 115200)
            timeout (int): Serial read timeout in seconds
        """
        self.simulation_mode = simulation_mode
        self.current_angles = [90, 90, 90, 90, 90, 0]  # Default neutral position
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
        
        if self.simulation_mode:
            # Simulation mode output
            packet = f"<{','.join(map(str, clamped_angles))}>"
            print(f"📤 Simulated Command: {packet}")
            print(f"   [Base: {clamped_angles[0]}°, Shoulder: {clamped_angles[1]}°, Elbow: {clamped_angles[2]}°, WristV: {clamped_angles[3]}°, WristR: {clamped_angles[4]}°, Grip: {clamped_angles[5]}°]")
            time.sleep(0.5)  # Simulate movement time
            self.current_angles = clamped_angles
            return True
        
        else:
            # Hardware mode - send via serial
            try:
                # Ensure serial connection is open
                if self.serial is None or not self.serial.is_open:
                    self._connect_serial()
                
                # Format packet: <90,45,120,90,90,10>
                packet = f"<{','.join(map(str, clamped_angles))}>"
                
                # Send packet
                self.serial.write(packet.encode('utf-8'))
                print(f"📤 Sent to Arduino: {packet}")
                
                # Wait for confirmation from Arduino
                try:
                    confirmation = self.serial.readline().decode('utf-8', errors='ignore').strip()
                    if confirmation:
                        print(f"📥 Arduino Reply: {confirmation}")
                    else:
                        print("⚠️  No response from Arduino (timeout)")
                except UnicodeDecodeError:
                    print("⚠️  Received malformed response from Arduino")
                
                self.current_angles = clamped_angles
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
            time.sleep(0.2)
            
        return True

    def get_status(self):
        """Get current robot status."""
        return {
            "angles": self.current_angles,
            "mode": "simulation" if self.simulation_mode else "hardware",
            "port": self.port if not self.simulation_mode else None,
            "connected": self.serial.is_open if self.serial else False
        }
    
    def close(self):
        """Close serial connection gracefully."""
        if self.serial and self.serial.is_open:
            self.serial.close()
            print(f"🔌 Serial connection to {self.port} closed.")

    def __del__(self):
        """Destructor to ensure serial port is closed."""
        self.close()
