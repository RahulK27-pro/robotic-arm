import time
import threading
import sys
import os
import random
import cv2
from flask import Flask, Response, jsonify

# Adjust path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from hardware.robot_driver import RobotArm
from camera import VideoCamera
from tools.collect_data import DataCollector

# Global state for Flask
global_frame = None
agent_status = "Initializing"

app = Flask(__name__)

class AutoCollectionAgent:
    """
    Automated Data Collection Agent with Video Feedback.
    """
    
    def __init__(self, robot: RobotArm, camera: VideoCamera):
        self.robot = robot
        self.camera = camera
        self.running = False
        self.thread = None
        self.frame_count = 0
        self.centered_frames = 0
        self.required_centered_frames = 4 # Reduced for faster cycling
        self.collector = DataCollector()
        
        global agent_status
        agent_status = "Ready"
        print("[AUTO] 📝 Automated Data Collection Initialized.")

    def start(self, target_object_name):
        if self.running: return
        self.target_object = target_object_name
        self.camera.set_target_object(target_object_name)
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        print(f"🚀 Auto-Collection STARTED for '{target_object_name}'")
        
    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
        print("🛑 Stopped.")

    def _loop(self):
        global agent_status
        
        # Configuration
        GAIN_HIGH = 0.02
        GAIN_LOW = 0.012
        DEADZONE = 15 
        MAX_STEP = 2.0
        MIN_MOVE = 0.5
        
        # Initial Position
        print("Moving to Home Position...")
        agent_status = "Homing"
        self.robot.move_to([0, 100, 140, 90, 12, 155]) 
        time.sleep(2.0)
        
        current_base = 0
        current_elbow = 140
        self.next_axis = 'x'
        
        agent_status = "Searching"
        
        while self.running:
            self.frame_count += 1
            
            # --- VIDEO FEED UPDATE ---
            frame = self.camera.get_raw_frame()
            if frame is not None:
                # Add Overlay
                cv2.putText(frame, f"Mode: AUTO COLLECT | Target: {self.target_object}", (10, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                cv2.putText(frame, f"Status: {agent_status}", (10, 60),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
                cv2.putText(frame, f"Samples: {self.frame_count}", (10, 90),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
                
                # Update global for Flask to stream
                global global_frame
                global_frame = frame
            
            # --- LOGIC ---
            detections = getattr(self.camera, 'last_detection', [])
            
            if not detections:
                if self.frame_count % 50 == 0:
                    print("Waiting for object...")
                time.sleep(0.05)
                continue
                
            det = detections[0]
            error_x = det['error_x']
            error_y = det['error_y']
            dist_cm = det.get('distance_cm', 20.0)
            if dist_cm <= 0: dist_cm = 20.0
            
            # Check Alignment
            x_centered = abs(error_x) < DEADZONE
            y_centered = abs(error_y) < DEADZONE
            
            if x_centered and y_centered:
                self.centered_frames += 1
                agent_status = f"Centered ({self.centered_frames}/{self.required_centered_frames})"
            else:
                self.centered_frames = 0
                agent_status = "Aligning"
                
            # --- PERTURBATION ---
            if self.centered_frames >= self.required_centered_frames:
                agent_status = "Perturbing..."
                print("\n⚡ STABLE! Perturbing...")
                
                # User Request: Y-Axis ONLY (Elbow)
                axis_choice = 'y' 
                
                # Offset configuration for Y-axis
                # Move elbow 5-10 degrees
                offset = random.uniform(5, 10)
                direction = random.choice([-1, 1])
                move_deg = offset * direction
                
                if False: # locked x axis
                    target_base = current_base + move_deg
                    target_base = max(0, min(180, target_base))
                    self.robot.move_to([target_base, 100, current_elbow, 90, 12, 155])
                    current_base = target_base
                else: 
                    target_elbow = current_elbow + move_deg
                    target_elbow = max(50, min(150, target_elbow))
                    self.robot.move_to([current_base, 100, target_elbow, 90, 12, 155])
                    current_elbow = target_elbow
                
                self.centered_frames = 0
                time.sleep(1.0)
                continue
            
            # --- CORRECTION ---
            # X-Axis
            # X-Axis Correction (DISABLED by User Request)
            # if not x_centered:
            #     # ... (code removed to lock base) ...
            #     pass 
            
            # Y-Axis
            if not y_centered and abs(error_x) < 200: 
                gain = GAIN_HIGH if abs(error_y) > 100 else GAIN_LOW
                raw_corr = -(error_y * gain) 
                
                if abs(raw_corr) < 0.1: corr_y = 0
                elif abs(raw_corr) < MIN_MOVE: corr_y = MIN_MOVE * (1 if raw_corr > 0 else -1)
                else: corr_y = raw_corr
                
                corr_y = max(-MAX_STEP, min(MAX_STEP, corr_y))
                
                if abs(corr_y) > 0:
                    new_elbow = current_elbow + corr_y
                    new_elbow = max(50, min(150, new_elbow))
                    self.collector.log(error_y, dist_cm, corr_y, axis='y')
                    self.robot.move_to([current_base, 100, new_elbow, 90, 12, 155])
                    current_elbow = new_elbow
            
            time.sleep(0.05)

# --- FLASK ROUTES ---
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

@app.route('/')
def index():
    return "Auto-Collection Running. View <a href='/video_feed'>Video Feed</a>."

def main():
    target = "bottle"
    if len(sys.argv) > 1: target = sys.argv[1]
    
    print(f"🎯 Target set to: {target}")
    print("🎥 Video Feed available at: http://localhost:5000/video_feed")
    
    try:
        robot = RobotArm(simulation_mode=False)
        camera = VideoCamera()
    except Exception as e:
        print(f"Hardware init failed: {e}")
        return

    agent = AutoCollectionAgent(robot, camera)
    agent.start(target)
    
    try:
        app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
    except KeyboardInterrupt:
        print("Stopping...")
    finally:
        agent.stop()
        if hasattr(camera, 'release'): camera.release()

if __name__ == "__main__":
    main()
