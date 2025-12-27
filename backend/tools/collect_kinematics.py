import sys
import os
import csv
import time
import threading
import cv2
from flask import Flask, Response

# Adjust path to import from backend
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from hardware.robot_driver import RobotArm
from camera import VideoCamera

# --- CONFIG ---
DATA_FILE = os.path.join(os.path.dirname(__file__), "kinematics_data.csv")
TARGET_NAME = "bottle"

# Global State for Flask
global_frame = None
status_text = "Initializing..."
app = Flask(__name__)

class KinematicsCollector:
    def __init__(self, robot, camera):
        self.robot = robot
        self.camera = camera
        self.running = False
        self.count = 0
        
        # Initialize CSV
        if not os.path.exists(DATA_FILE):
             with open(DATA_FILE, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['shoulder_angle', 'elbow_angle', 'measured_z_cm', 'measured_y_px'])

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._collection_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)

    def _align_x_axis(self, s_angle, e_angle):
        """Active X-Alignment Loop. Returns (Success, FinalError)"""
        global status_text
        current_base = self.robot.current_angles[0]
        
        DEADZONE = 30
        MAX_RETRIES = 30 
        
        for i in range(MAX_RETRIES):
            if not self.running: return False, 0
            
            time.sleep(0.2) 
            
            detections = getattr(self.camera, 'last_detection', [])
            target = None
            for d in detections:
                 if d.get('object_name') == TARGET_NAME:
                     target = d
                     break
            
            if not target:
                status_text = "Aligning: Target Lost"
                return False, 999
                
            error_x = target['error_x']
            
            if abs(error_x) < DEADZONE:
                return True, error_x
                
            correction = error_x * 0.015
            correction = max(-3.0, min(3.0, correction))
            
            if abs(correction) < 0.5: correction = 0.5 * (1 if correction > 0 else -1)
            
            new_base = current_base + correction
            new_base = max(0, min(180, new_base))
            
            status_text = f"Aligning X ({i}/{MAX_RETRIES}): Err={error_x:.0f}"
            self.robot.move_to([new_base, s_angle, e_angle, 90, 12, 170])
            current_base = new_base
            
        print(f"Alignment Timeout. Final Error: {error_x}")
        return False, error_x

    def _collection_loop(self):
        global status_text, global_frame
        
        print("=== KINEMATICS DATA COLLECTION STARTED ===")
        print(f"Target: {TARGET_NAME}")
        
        # 1-Degree Steps as requested previously
        # Updated Range based on user request "full extent"
        shoulder_range = range(140, 50, -1) 
        elbow_range = range(70, 160, 1)
        
        total_steps = len(shoulder_range) * len(elbow_range)
        
        status_text = "Moving to Home..."
        self.robot.move_to([90, 140, 140, 90, 12, 170]) 
        time.sleep(2)
        
        for s_angle in shoulder_range:
            for e_angle in elbow_range:
                if not self.running: break
                
                # Safety check (prevent hitting self or table)
                if s_angle < 70 and e_angle < 80:
                    continue
                    
                status_text = f"Grid: S={s_angle} E={e_angle}"
                
                current_base = self.robot.current_angles[0] 
                self.robot.move_to([current_base, s_angle, e_angle, 90, 12, 170])
                time.sleep(0.2)
                
                aligned, final_err = self._align_x_axis(s_angle, e_angle)
                
                if not aligned and abs(final_err) > 60:
                     print(f"Skipped: S={s_angle} E={e_angle} (Alignment Failed, Err={final_err:.0f})")
                     continue
                elif not aligned:
                     print(f"Proceeding with imperfect alignment (Err={final_err:.0f})...")

                time.sleep(0.3)
                detections = getattr(self.camera, 'last_detection', [])
                target = None
                for d in detections:
                    if d.get('object_name') == TARGET_NAME:
                        target = d
                        break
                
                if target:
                    meas_z = target.get('distance_cm', -1)
                    meas_y = target.get('y', -1)
                    
                    if meas_z > 0:
                        self.log_data(s_angle, e_angle, meas_z, meas_y)
                        status_text = f"LOGGED: Z={meas_z:.1f}cm"
                        print(f"[{self.count}/{total_steps}] LOGGED: S={s_angle} E={e_angle} -> Z={meas_z:.1f}cm Y={meas_y}px")
                    else:
                        print(f"Invalid Z ({meas_z}) for S={s_angle} E={e_angle}")
                        status_text = "Invalid Z"
                else:
                    print(f"Target Lost at Measure Step: S={s_angle} E={e_angle}")
                    status_text = "Target Lost"
                
                self.count += 1
                
        print("Collection Complete.")
        status_text = "Done."
        self.running = False

    def log_data(self, s, e, z, y):
        with open(DATA_FILE, 'a', newline='') as f:
            csv.writer(f).writerow([s, e, z, y])

# --- FLASK ---
def start_flask():
    try:
        app.run(host='0.0.0.0', port=5001, debug=False, use_reloader=False)
    except: pass

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

def gen_frames():
    while True:
        if global_frame is not None:
             _, buffer = cv2.imencode('.jpg', global_frame)
             frame = buffer.tobytes()
             yield (b'--frame\r\n'
                    b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        time.sleep(0.04)

def main():
    try:
        robot = RobotArm(simulation_mode=False) 
        camera = VideoCamera(detection_mode='yolo')
        camera.set_target_object(TARGET_NAME)
    except Exception as e:
        print(f"Init Failed: {e}")
        return

    collector = KinematicsCollector(robot, camera)
    collector.start()
    
    def overlay_loop():
        global global_frame
        while collector.running:
             frame = camera.get_raw_frame() # Get raw frame from camera
             if frame is not None:
                 # Add overlay text
                 frame_copy = frame.copy()
                 cv2.putText(frame_copy, status_text, (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                 global_frame = frame_copy
             time.sleep(0.04)
    
    t_overlay = threading.Thread(target=overlay_loop, daemon=True)
    t_overlay.start()

    print(f"🎥 Video Feed running at: http://localhost:5001/video_feed")
    start_flask()
    
    collector.stop()
    if hasattr(camera, 'release'): camera.release()

if __name__ == "__main__":
    main()
