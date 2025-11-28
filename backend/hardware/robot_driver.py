import time

class RobotArm:
    def __init__(self, simulation_mode=True):
        self.simulation_mode = simulation_mode
        self.current_angles = [0, 0, 0, 0, 0, 0]
        if self.simulation_mode:
            print("RobotArm initialized in SIMULATION MODE.")
        else:
            print("RobotArm initialized in HARDWARE MODE (Serial connection placeholder).")
            # self.serial = serial.Serial(...)

    def move_to(self, angles, speed=1.0):
        """
        Moves the robot to the specified angles.
        angles: List of 6 angles [base, shoulder, elbow, wrist_pitch, wrist_roll, gripper]
        speed: Float, speed multiplier (not used in simple sim)
        """
        if self.simulation_mode:
            print(f"Simulated Serial Command: <Base: {angles[0]}, Shoulder: {angles[1]}, Elbow: {angles[2]}, Pitch: {angles[3]}, Roll: {angles[4]}, Gripper: {angles[5]}>")
            # Simulate travel time
            time.sleep(0.5) 
        else:
            # Placeholder for real serial communication
            # command = f"<{','.join(map(str, angles))}>"
            # self.serial.write(command.encode())
            pass
        
        self.current_angles = angles
        return True

    def get_status(self):
        return {
            "angles": self.current_angles,
            "mode": "simulation" if self.simulation_mode else "hardware"
        }
