"""
Hybrid 2-Axis Data Collection Script (VISUAL VERSION)

Displays video feed on localhost:5000 with live data overlay.
Workflow same as terminal version but with visual guidance.
"""

import cv2
import time
import csv
import os
import numpy as np
from flask import Flask, Response, render_template_string
from threading import Thread
from hardware.robot_driver import RobotArm
from camera import VideoCamera
import torch
from brain.anfis_pytorch import ANFIS

# Configuration
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TOOLS_DIR = os.path.join(SCRIPT_DIR, "tools")
OUTPUT_FILE = os.path.join(TOOLS_DIR, "final_data.csv")
FIXED_WRIST_ANGLE = 90
FIXED_ROLL = 12
GRIPPER_OPEN = 170
MAX_ALIGNMENT_ITERATIONS = 50

# Flask app
app = Flask(__name__)

# HTML template
HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Hybrid Data Collection</title>
    <style>
        body { 
            font-family: Arial; 
            background: #1a1a2e; 
            color: #fff; 
            margin: 0; 
            padding: 20px;
        }
        h1 { color: #00ff88; }
        .container {
            display: flex;
            gap: 20px;
            flex-wrap: wrap;
        }
        .video-box {
            flex: 1;
            min-width: 640px;
        }
        .info-box {
            flex: 0 0 300px;
            background: #16213e;
            padding: 20px;
            border-radius: 10px;
        }
        img { 
            width: 100%; 
            border-radius: 10px;
            border: 2px solid #00ff88;
        }
        .status {
            background: #0f3460;
            padding: 10px;
            margin: 10px 0;
            border-radius: 5px;
        }
        .value {
            color: #00ff88;
            font-size: 24px;
            font-weight: bold;
        }
        .instruction {
            background: #e94560;
            padding: 15px;
            margin: 20px 0;
            border-radius: 5px;
        }
        .sample-count {
            font-size: 48px;
            text-align: center;
            color: #00ff88;
        }
    </style>
</head>
<body>
    <h1>🤖 Hybrid Data Collection</h1>
    <div class="container">
        <div class="video-box">
            <img src="{{ url_for('video_feed') }}" />
        </div>
        <div class="info-box">
            <h2>📊 Current Data</h2>
            <div class="status">
                <strong>Mode:</strong><br>
                <span class="value" id="mode">WAITING</span>
            </div>
            <div class="status">
                <strong>Base Correction:</strong><br>
                <span class="value" id="base_corr">0°</span>
            </div>
            <div class="status">
                <strong>Pixel Y:</strong><br>
                <span class="value" id="pixel_y">--</span>
            </div>
            <div class="status">
                <strong>Depth:</strong><br>
                <span class="value" id="depth">--</span>
            </div>
            <div class="status">
                <strong>Shoulder:</strong><br>
                <span class="value" id="shoulder">--</span>
            </div>
            <div class="status">
                <strong>Elbow:</strong><br>
                <span class="value" id="elbow">--</span>
            </div>
            <div class="sample-count" id="count">{{ samples }}</div>
            <p style="text-align:center;">Samples Collected</p>
            
            <div class="instruction">
                <strong>📝 Instructions:</strong><br><br>
                <strong>Terminal Commands:</strong><br>
                - ENTER: Start new sample<br>
                - Q: Quit<br><br>
                <strong>During Manual Reach:</strong><br>
                - W/S: Shoulder Up/Down<br>
                - A/D: Elbow Down/Up<br>
                - LEFT/RIGHT: Adjust Base (X-Drift)<br>
                - SPACE: Save position<br>
                - Q: Cancel
            </div>
        </div>
    </div>
</body>
</html>
"""

class VisualDataCollector:
    def __init__(self):
        self.robot = RobotArm(simulation_mode=False, port='COM4')
        self.camera = VideoCamera(detection_mode='yolo')
        self.brain_x = self._load_anfis()
        
        # Ensure tools directory exists
        os.makedirs(TOOLS_DIR, exist_ok=True)
        
        # Initialize CSV
        if not os.path.exists(OUTPUT_FILE):
            with open(OUTPUT_FILE, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['pixel_y', 'depth_cm', 'shoulder', 'elbow', 'base_correction'])
        
        # State for display
        self.current_mode = "IDLE"
        self.current_data = {
            'pixel_y': 0,
            'depth': 0,
            'shoulder': 0,
            'elbow': 0,
            'base': 90
        }
        self.sample_count = 0
        self.display_frame = None
        
        print("✅ Visual Data Collector initialized")
        print("🌐 Open http://localhost:5000 in your browser")
    
    def _load_anfis(self):
        path = 'brain/models/anfis_x.pth'
        if os.path.exists(path):
            model = ANFIS(n_inputs=1, n_rules=5, input_ranges=[(-400, 400)])
            model.load_state_dict(torch.load(path))
            model.eval()
            return model
        return None
    
    def _predict_x(self, error_x):
        if not self.brain_x:
            return 1.0 if error_x > 0 else -1.0
        with torch.no_grad():
            inp = torch.tensor([[error_x]], dtype=torch.float32)
            return self.brain_x(inp).item()
    
    def get_annotated_frame(self):
        """Get camera frame with annotations."""
        # Get raw frame
        raw_frame = None
        with self.camera.lock:
            if self.camera.raw_frame is not None:
                raw_frame = self.camera.raw_frame.copy()
        
        if raw_frame is None:
            return np.zeros((480, 640, 3), dtype=np.uint8)
        
        frame = raw_frame.copy()
        h, w = frame.shape[:2]
        
        # Draw detections
        detections = self.camera.last_detection
        if detections:
            for det in detections:
                bbox = det['bbox']
                center = det['center']
                
                # Draw box
                cv2.rectangle(frame, (bbox[0], bbox[1]), (bbox[2], bbox[3]), (0, 255, 0), 2)
                cv2.circle(frame, center, 5, (0, 0, 255), -1)
                
                # Draw label
                label = f"{det['object_name']} {det['distance_cm']:.1f}cm"
                cv2.putText(frame, label, (bbox[0], bbox[1]-10), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        
        # Draw crosshair at center
        cv2.line(frame, (w//2-20, h//2), (w//2+20, h//2), (255, 255, 0), 2)
        cv2.line(frame, (w//2, h//2-20), (w//2, h//2+20), (255, 255, 0), 2)
        
        # Draw mode
        cv2.putText(frame, self.current_mode, (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
        
        # Draw current data
        data_text = f"Y:{self.current_data['pixel_y']:.0f}px D:{self.current_data['depth']:.1f}cm"
        cv2.putText(frame, data_text, (10, h-20), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        angle_text = f"S:{self.current_data['shoulder']}deg E:{self.current_data['elbow']}deg"
        cv2.putText(frame, angle_text, (10, h-50), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        base_text = f"Base Corr: {self.current_data.get('base_correction', 0):.1f}deg"
        cv2.putText(frame, base_text, (10, h-80), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 200, 0), 2)
        
        return frame
    
    def auto_center_base(self, target_object="bottle"):
        """
        Auto-center using ANFIS with visual servoing search pattern.
        Uses same angles as visual_servoing.py for consistency.
        """
        self.current_mode = "SEARCHING"
        print(f"\n🎯 Searching for '{target_object}'...")
        self.camera.set_target_object(target_object)
        
        # Visual Servoing Search Angles (from visual_servoing.py)
        BASE_START = 23
        SHOULDER = 100
        ELBOW_START = 140
        WRIST_PITCH = 90
        
        base = BASE_START
        shoulder = SHOULDER
        elbow = ELBOW_START
        
        # Move to search position
        self.robot.move_to([base, shoulder, elbow, FIXED_WRIST_ANGLE, FIXED_ROLL, GRIPPER_OPEN])
        time.sleep(2)
        
        # Search sweep direction
        search_dir = 1
        
        for iteration in range(MAX_ALIGNMENT_ITERATIONS):
            time.sleep(0.5)
            detections = self.camera.last_detection
            
            if not detections:
                # Sweep search (like visual servoing)
                self.current_mode = "SEARCHING"
                step = 1.0
                base += (search_dir * step)
                if base <= 0 or base >= 180:
                    search_dir *= -1
                    base = max(0, min(180, base))
                
                self.robot.move_to([base, shoulder, elbow, FIXED_WRIST_ANGLE, FIXED_ROLL, GRIPPER_OPEN])
                print(f"  [Search {iteration+1}] Sweeping... Base={base:.1f}°")
                continue
            
            # Object found - start alignment
            self.current_mode = "ALIGNING"
            det = detections[0]
            error_x = det['error_x']
            
            # Update display
            self.current_data['pixel_y'] = det['error_y']
            self.current_data['depth'] = det['distance_cm']
            self.current_data['base'] = base
            
            if abs(error_x) < 20:
                self.current_mode = "CENTERED ✓"
                print(f"✅ Centered! Base={base}°")
                print(f"   Input: [Pixel_Y={det['error_y']:.0f}px, Depth={det['distance_cm']:.1f}cm]")
                return (base, det['error_y'], det['distance_cm'])
            
            # ANFIS alignment
            correction = self._predict_x(error_x)
            correction = max(-30, min(30, correction))
            base += correction
            base = max(0, min(180, base))
            
            print(f"  [Align {iteration+1}] ErrX={error_x:.0f}px → Corr={correction:.1f}° → Base={base:.1f}°")
            
            self.robot.move_to([base, shoulder, elbow, FIXED_WRIST_ANGLE, FIXED_ROLL, GRIPPER_OPEN])
        
        self.current_mode = "SEARCH FAILED"
        print("❌ Search/alignment failed")
        return None
    
    def manual_reach_visual(self, locked_base):
        """Visual manual reach mode with Base Correction."""
        import msvcrt
        
        self.current_mode = "MANUAL REACH"
        print("\n🎮 Manual Reach Mode")
        print("Controls: W/S (Shoulder), A/D (Elbow), LEFT/RIGHT (Base), SPACE (Save)")
        
        # Track base correction
        current_base = locked_base
        initial_base = locked_base
        
        # Use visual servoing angles as starting point
        shoulder = 100
        elbow = 140
        
        self.robot.move_to([current_base, shoulder, elbow, FIXED_WRIST_ANGLE, FIXED_ROLL, GRIPPER_OPEN])
        
        while True:
            self.current_data['shoulder'] = shoulder
            self.current_data['elbow'] = elbow
            self.current_data['base_correction'] = current_base - initial_base
            
            if msvcrt.kbhit():
                key_bytes = msvcrt.getch()
                try:
                    key = key_bytes.decode('utf-8').lower()
                except:
                    key = None
                
                # Check for space bar
                if key == ' ' or key_bytes == b' ' or (key_bytes and ord(key_bytes) == 32):
                    self.current_mode = "SAVED ✓"
                    base_correction = current_base - initial_base
                    print(f"\n💾 Saving: S={shoulder}°, E={elbow}°, BaseCorrection={base_correction:.1f}°")
                    return (shoulder, elbow, base_correction)
                    
                # Handle special keys (Arrows)
                elif key_bytes == b'\xe0':  # Arrow prefix
                    arrow = msvcrt.getch()
                    if arrow == b'M':  # Right Arrow
                        current_base = max(0, min(180, current_base - 1)) # Decrement to move RIGHT (Servo logic)
                        self.robot.move_to([current_base, shoulder, elbow, FIXED_WRIST_ANGLE, FIXED_ROLL, GRIPPER_OPEN])
                    elif arrow == b'K':  # Left Arrow
                        current_base = max(0, min(180, current_base + 1)) # Increment to move LEFT
                        self.robot.move_to([current_base, shoulder, elbow, FIXED_WRIST_ANGLE, FIXED_ROLL, GRIPPER_OPEN])
                
                # Standard keys
                elif key == 'w':
                    shoulder = min(180, shoulder + 1)
                    self.robot.move_to([current_base, shoulder, elbow, FIXED_WRIST_ANGLE, FIXED_ROLL, GRIPPER_OPEN])
                elif key == 's':
                    shoulder = max(0, shoulder - 1)
                    self.robot.move_to([current_base, shoulder, elbow, FIXED_WRIST_ANGLE, FIXED_ROLL, GRIPPER_OPEN])
                elif key == 'd':
                    elbow = min(180, elbow + 1)
                    self.robot.move_to([current_base, shoulder, elbow, FIXED_WRIST_ANGLE, FIXED_ROLL, GRIPPER_OPEN])
                elif key == 'a':
                    elbow = max(0, elbow - 1)
                    self.robot.move_to([current_base, shoulder, elbow, FIXED_WRIST_ANGLE, FIXED_ROLL, GRIPPER_OPEN])
                elif key == 'q':
                    self.current_mode = "CANCELLED"
                    print("\n❌ Cancelled")
                    return None
            
            time.sleep(0.05)
    
    def collect_sample(self):
        result = self.auto_center_base("bottle")
        if not result:
            return False
        
        locked_base, pixel_y, depth_cm = result
        self.current_data['pixel_y'] = pixel_y
        self.current_data['depth'] = depth_cm
        
        reach_result = self.manual_reach_visual(locked_base)
        if not reach_result:
            return False
        
        shoulder, elbow, base_correction = reach_result
        
        with open(OUTPUT_FILE, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([pixel_y, depth_cm, shoulder, elbow, base_correction])
        
        self.sample_count += 1
        self.current_mode = "IDLE"
        print(f"✅ Sample #{self.sample_count} saved")
        return True

# Global collector instance
collector = None

@app.route('/')
def index():
    count = collector.sample_count if collector else 0
    return render_template_string(HTML, samples=count)

@app.route('/video_feed')
def video_feed():
    def generate():
        while True:
            if collector:
                frame = collector.get_annotated_frame()
                _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
            time.sleep(0.033)  # 30 FPS
    
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

def run_flask():
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

def main():
    global collector
    
    print("=" * 60)
    print("VISUAL HYBRID DATA COLLECTION")
    print("=" * 60)
    
    collector = VisualDataCollector()
    
    # Start Flask in background
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    print("\n🌐 Video feed: http://localhost:5000")
    print("\nPlace object at different positions and press ENTER to collect\n")
    
    try:
        while True:
            cmd = input(f"[Sample #{collector.sample_count+1}] Press ENTER (or 'q' to quit): ").strip().lower()
            
            if cmd == 'q':
                break
            
            if collector.collect_sample():
                print(f"✅ Total samples: {collector.sample_count}")
            else:
                print("⚠️  Collection failed")
    
    except KeyboardInterrupt:
        print("\n🛑 Interrupted")
    
    finally:
        print(f"\n📁 Data: {OUTPUT_FILE}")
        print(f"📊 Samples: {collector.sample_count}")

if __name__ == "__main__":
    main()
