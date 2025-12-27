import time
import threading
import sys
import os
import random
import cv2
import pandas as pd
from flask import Flask, Response

# Adjust path to import backend modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from hardware.robot_driver import RobotArm
from camera import VideoCamera

# Global state for Flask
global_frame = None
agent_status = "Initializing"
data_log = []

app = Flask(__name__)

class XAxisAnfisCollector:
    def __init__(self, robot: RobotArm, camera: VideoCamera, target_name="bottle"):
        self.robot = robot
        self.camera = camera
        self.target_name = target_name
        self.running = False
        self.thread = None
        self.lock = threading.Lock()
        
        # Collection Params
        self.center_angle = None
        self.state = "SEARCHING" # SEARCHING, CENTERING, COLLECTING
        self.samples_collected = 0
        self.sweep_step = 0
        self.max_sweep_offset = 20 # degrees
        
        # CSV File
        self.csv_file = os.path.join(os.path.dirname(__file__), 'x_axis_anfis_data.csv')
        if not os.path.exists(self.csv_file):
            pd.DataFrame(columns=['error_x', 'current_angle', 'target_angle', 'correction_needed']).to_csv(self.csv_file, index=False)
            
        global agent_status
        agent_status = "Ready"

    def start(self):
        if self.running: return
        self.camera.set_target_object(self.target_name)
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        print(f"🚀 X-Axis Data Collection STARTED for '{self.target_name}'")

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
        print("🛑 Stopped.")

    def save_data(self, error_x, current_angle, target_angle):
        correction = target_angle - current_angle
        # Append to CSV
        df = pd.DataFrame([[error_x, current_angle, target_angle, correction]], 
                          columns=['error_x', 'current_angle', 'target_angle', 'correction_needed'])
        df.to_csv(self.csv_file, mode='a', header=False, index=False)
        self.samples_collected += 1
        print(f"💾 Saved: Err={error_x:.1f}, Curr={current_angle}, Tgt={target_angle}, Corr={correction}")

    def _loop(self):
        global agent_status
        
        # Initial Pose
        current_base = 90
        # Home position: Base=90, Shoulder=140, Elbow=90, Wrist=90, Grip=12, Rot=155
        self.robot.move_to([current_base, 100, 140, 90, 12, 155]) 
        time.sleep(2.0)
        
        while self.running:
            # Update video feed overlay
            self._update_feed()
            
            # Get Detection
            detections = getattr(self.camera, 'last_detection', [])
            if not detections:
                agent_status = "No Object"
                time.sleep(0.1)
                continue
                
            det = detections[0]
            error_x = det['error_x']
            
            # --- STATE MACHINE ---
            
            if self.state == "SEARCHING":
                # Manual or basic sweep could go here, but detailed instructions say "takes in x axis alone"
                # We assume object is visible to start, or user places it.
                if abs(error_x) < 300: # Clearly visible
                    self.state = "CENTERING"
                else:
                    agent_status = "Object lost/far"

            elif self.state == "CENTERING":
                # "Slow and smooth" centering to find Ground Truth
                if abs(error_x) < 10: # Very tight tolerance for ground truth
                    self.center_angle = current_base
                    self.state = "COLLECTING"
                    # Create a sweep list
                    self.sweep_offset_list = list(range(-self.max_sweep_offset, self.max_sweep_offset + 1, 2))
                    random.shuffle(self.sweep_offset_list)
                    agent_status = f"Locked Center: {self.center_angle}"
                    print(f"✅ Center Found at {self.center_angle}. Starting Sweep...")
                    time.sleep(2.0)
                else:
                    agent_status = f"Centering... Err: {error_x}"
                    # Simple step correction
                    step = 0
                    if error_x > 0: step = 1
                    else: step = -1
                    
                    current_base += step
                    current_base = max(0, min(180, current_base))
                    self.robot.move_to([current_base, 100, 140, 90, 12, 155])
                    # Wait for move to complete + visual update
                    time.sleep(0.5) 

            elif self.state == "COLLECTING":
                if not self.sweep_offset_list:
                    # Sweep done, re-verify center
                    self.state = "CENTERING"
                    continue
                
                offset = self.sweep_offset_list.pop()
                test_angle = self.center_angle + offset
                test_angle = max(0, min(180, test_angle))
                
                # Move to test angle
                self.robot.move_to([test_angle, 100, 140, 90, 12, 155])
                current_base = test_angle
                agent_status = f"Collecting... Offset: {offset}"
                
                # --- CRITICAL: Wait for Stability ---
                # 1. Wait for robot to physically stop
                time.sleep(1.0)
                
                # 2. Wait for camera lag/blur to settle
                time.sleep(1.0)
                
                # Get fresh detection
                fresh_det = getattr(self.camera, 'last_detection', [])
                if fresh_det:
                    e_x = fresh_det[0]['error_x']
                    # Log Data
                    self.save_data(e_x, current_base, self.center_angle)
                else:
                    print("❌ Lost object during sweep. Skipping.")
                    
            time.sleep(0.05)

    def _update_feed(self):
        global global_frame, agent_status
        frame = self.camera.get_raw_frame()
        if frame is not None:
            cv2.putText(frame, f"Mode: ANFIS DATA X | Status: {agent_status}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.putText(frame, f"Samples: {self.samples_collected}", (10, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
            global_frame = frame

# --- FLASK ---
def gen_frames():
    while True:
        if global_frame is not None:
             _, buffer = cv2.imencode('.jpg', global_frame)
             frame = buffer.tobytes()
             yield (b'--frame\r\n'
                    b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        else:
             time.sleep(0.01)
        time.sleep(0.04)

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

def main():
    target = "bottle"
    if len(sys.argv) > 1: target = sys.argv[1]
    
    print(f"🎯 Target set to: {target}")
    
    try:
        robot = RobotArm(simulation_mode=False)
        camera = VideoCamera()
    except Exception as e:
        print(f"Hardware init failed: {e}")
        return

    collector = XAxisAnfisCollector(robot, camera, target)
    collector.start()
    
    print("🎥 Video Feed: http://localhost:5000/video_feed")
    try:
        app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
    except KeyboardInterrupt:
        pass
    finally:
        collector.stop()
        if hasattr(camera, 'release'): camera.release()

if __name__ == "__main__":
    main()
