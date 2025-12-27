import time
import torch
import threading
import sys
import os

# Ensure imports work
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from hardware.robot_driver import RobotArm
from camera import VideoCamera
from brain.anfis_pytorch import ANFIS
from brain.kinematics import solve_angles # Corrected import

class DualBrainController:
    def __init__(self, robot, camera):
        self.robot = robot
        self.camera = camera
        self.active = False
        
        # BRAIN 1: Steering (X-Axis)
        # 1 Input (Error X), 5 Rules
        # Ensure 'brain/anfis_center.pth' exists
        self.net_steer = ANFIS(n_inputs=1, n_rules=5)
        path_steer = os.path.join(os.path.dirname(__file__), 'brain/anfis_center.pth')
        if os.path.exists(path_steer):
            self.net_steer.load_state_dict(torch.load(path_steer))
            print(f"Loaded Steering Brain from {path_steer}")
        else:
            print(f"WARNING: Steering Brain not found at {path_steer}")
        self.net_steer.eval()
        
        # BRAIN 2: Approach (Z-Axis)
        # 2 Inputs (Distance, Error), 6 Rules
        self.net_approach = ANFIS(n_inputs=2, n_rules=6)
        path_approach = os.path.join(os.path.dirname(__file__), 'brain/anfis_approach.pth')
        if os.path.exists(path_approach):
            self.net_approach.load_state_dict(torch.load(path_approach))
            print(f"Loaded Approach Brain from {path_approach}")
        else:
             print(f"WARNING: Approach Brain not found at {path_approach}")
        self.net_approach.eval()

    def start(self, target_name):
        self.active = True
        # threading.Thread(target=self._control_loop, args=(target_name,)).start()
        # For simplicity in testing, run in main thread or join
        self._control_loop(target_name)

    def _control_loop(self, target_name):
        print(f"Starting Dual-Brain Control for target: {target_name}")
        # Initial State
        curr_x, curr_y, curr_z = (0, 15, 30)
        
        # Initial Move
        angles = solve_angles(curr_x, curr_y, curr_z)
        self.robot.move_to(angles)
        
        while self.active:
            # 1. Perception
            # We need to find the specific target object
            # User snippet: detection = self.camera.get_object(target_name)
            # Assuming functionality, or we iterate last_detection
            detection_list = getattr(self.camera, 'last_detection', [])
            target = None
            for d in detection_list:
                if d.get('object_name', '') == target_name:
                    target = d
                    break
            
            if not target:
                print(f"Searching for {target_name}...")
                time.sleep(0.5)
                continue

            # Calculate Error (Center is 640 for 1280px)
            error_x = target['x'] - 640
            dist_cm = target.get('distance_cm', 0)
            
            # 2. Inference (The Dual Brain)
            with torch.no_grad():
                # Brain 1: How much to turn? (Input: Error X)
                d_theta = self.net_steer(torch.tensor([[float(error_x)]])).item()
                
                # Brain 2: How fast to move? (Inputs: Distance, Abs Error)
                # If Error is high, speed ~0
                step_z = self.net_approach(torch.tensor([[float(dist_cm), float(abs(error_x))]])).item()

            print(f"Err: {error_x:.1f}px -> Turn: {d_theta:.2f} | Dist: {dist_cm:.1f}cm -> Step: {step_z:.2f}")

            # 3. Fusion & Update
            # Update Angle directly (Steering)
            curr_base_angle = self.robot.current_angles[0]
            new_base_angle = curr_base_angle + d_theta
            
            # Update Z-position (Throttle)
            # step_z is speed in cm per loop (approx). 
            # We subtract because we want to decrease Z (move closer, assuming Z=0 is base)
            # Actually, coordinate system: Z is usually height or depth?
            # User snippet: curr_z -= step_z # Move closer
            # In teach_approach.py: curr_x, curr_y, curr_z = (0, 15, 30)
            # So Z reduces as we get closer.
            curr_z -= step_z 
            
            # 4. Actuation
            # We mix IK for the arm height with direct ANFIS control for the base
            try:
                angles = solve_angles(curr_x, curr_y, curr_z)
                angles[0] = new_base_angle # Override base with ANFIS 1 output
                
                # Safety limits
                curr_z = max(5, curr_z)
                
                self.robot.move_to(angles)
            except ValueError:
                print("Target out of reach!")
                break
            
            # 5. Grab Check
            if dist_cm < 3.0 and dist_cm > 0: # Valid non-zero distance
                self.perform_grab()
                break
                
            time.sleep(0.05) # 20Hz Loop

    def perform_grab(self):
        print("Grabbing...")
        # Close gripper (Servo 5)
        current = list(self.robot.current_angles)
        current[5] = 170 # Close (assuming 170 is closed)
        self.robot.move_to(current)
        time.sleep(1)
        
        # Lift
        # Just update coords
        # We can just increment Y or Z using IK
        # But for simpler lift:
        current[1] += 20 # Raise shoulder
        self.robot.move_to(current)
        print("Lifted.")

if __name__ == "__main__":
    # Standalone Execution
    try:
        robot = RobotArm(simulation_mode=False)
        camera = VideoCamera(detection_mode='yolo')
    except Exception as e:
        print(f"Init Failed: {e}")
        sys.exit(1)
        
    controller = DualBrainController(robot, camera)
    
    target = "cube"
    if len(sys.argv) > 1:
        target = sys.argv[1]
        
    try:
        controller.start(target)
    except KeyboardInterrupt:
        print("Stopping...")
    finally:
        if hasattr(camera, 'release'):
            camera.release()
