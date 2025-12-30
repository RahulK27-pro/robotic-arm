"""
Visual-Compensation Data Collection Script

Three-Step Workflow:
1. ANFIS auto-aligns X-axis
2. Capture visual features (SHIFT): pixel_y, depth, bbox_width
3. Manual approach (W/S/A/D/←/→/G) + Save (SPACE): shoulder, elbow, base_correction, gripper_closed

Displays live video feed on localhost:5000 with data overlay.
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
OUTPUT_FILE = os.path.join(TOOLS_DIR, "visual_compensation_data.csv")
FIXED_WRIST_ANGLE = 90
FIXED_ROLL = 12
GRIPPER_OPEN = 170
GRIPPER_CLOSED = 90
MAX_ALIGNMENT_ITERATIONS = 50

# Flask app
app = Flask(__name__)

# HTML template
HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Visual-Compensation Data Collection</title>
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
            flex: 0 0 350px;
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
        .step-indicator {
            background: #00ff88;
            color: #1a1a2e;
            padding: 10px;
            border-radius: 5px;
            text-align: center;
            font-weight: bold;
            margin: 10px 0;
        }
    </style>
</head>
<body>
    <h1>🤖 Visual-Compensation Data Collection</h1>
    <div class="container">
        <div class="video-box">
            <img src="{{ url_for('video_feed') }}" />
        </div>
        <div class="info-box">
            <h2>📊 Current Data</h2>
            <div class="step-indicator" id="step">STEP 0: WAITING</div>
            <div class="status">
                <strong>Mode:</strong><br>
                <span class="value" id="mode">IDLE</span>
            </div>
            
            <h3>Visual Features:</h3>
            <div class="status">
                <strong>Pixel Y:</strong><br>
                <span class="value" id="pixel_y">--</span>
            </div>
            <div class="status">
                <strong>Depth:</strong><br>
                <span class="value" id="depth">--</span>
            </div>
            <div class="status">
                <strong>BBox Width:</strong><br>
                <span class="value" id="bbox">--</span>
            </div>
            
            <h3>Motor Targets:</h3>
            <div class="status">
                <strong>Shoulder:</strong><br>
                <span class="value" id="shoulder">--</span>
            </div>
            <div class="status">
                <strong>Elbow:</strong><br>
                <span class="value" id="elbow">--</span>
            </div>
            <div class="status">
                <strong>Base Correction:</strong><br>
                <span class="value" id="base_corr">0°</span>
            </div>
            <div class="status">
                <strong>Gripper:</strong><br>
                <span class="value" id="gripper">OPEN</span>
            </div>
            
            <div class="sample-count" id="count">{{ samples }}</div>
            <p style="text-align:center;">Samples Collected</p>
            
            <div class="instruction">
                <strong>📝 Controls:</strong><br><br>
                <strong>Terminal:</strong><br>
                - ENTER: Start new sample<br>
                - Q: Quit<br><br>
                <strong>Step 1 (After X-Align):</strong><br>
                - SHIFT: Capture visuals<br><br>
                <strong>Step 2 (Manual Reach):</strong><br>
                - W/S: Shoulder Up/Down<br>
                - A/D: Elbow Close/Open<br>
                - ←/→: Base correction<br>
                - G: Toggle gripper<br>
                - SPACE: Save sample<br>
                - Q: Cancel
            </div>
        </div>
    </div>
</body>
</html>
"""

class VisualCompensationCollector:
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
                writer.writerow(['pixel_y', 'depth_cm', 'bbox_width', 'shoulder_angle', 
                               'elbow_angle', 'base_correction', 'gripper_closed'])
        
        # State for display
        self.current_step = "IDLE"
        self.current_mode = "IDLE"
        self.current_data = {
            'pixel_y': 0,
            'depth': 0,
            'bbox_width': 0,
            'shoulder': 0,
            'elbow': 0,
            'base_correction': 0,
            'gripper_closed': 0
        }
        self.sample_count = 0
        self.visual_capture = None  # Stores (pixel_y, depth_cm, bbox_width)
        
        print("✅ Visual-Compensation Collector initialized")
        print("🌐 Open http://localhost:5000 in your browser")
    
    def _load_anfis(self):
        path = 'brain/models/anfis_x.pth'
        if os.path.exists(path):
            model = ANFIS(n_inputs=1, n_rules=5, input_ranges=[(-400, 400)])
            model.load_state_dict(torch.load(path))
            model.eval()
            print("✅ Loaded ANFIS X-axis model")
            return model
        print("⚠️  ANFIS model not found, using fallback")
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
                
                # Calculate bbox width
                bbox_width = bbox[2] - bbox[0]
                
                # Draw label
                label = f"{det['object_name']} {det['distance_cm']:.1f}cm W:{bbox_width}px"
                cv2.putText(frame, label, (bbox[0], bbox[1]-10), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        
        # Draw crosshair at center
        cv2.line(frame, (w//2-20, h//2), (w//2+20, h//2), (255, 255, 0), 2)
        cv2.line(frame, (w//2, h//2-20), (w//2, h//2+20), (255, 255, 0), 2)
        
        # Draw step and mode
        cv2.putText(frame, self.current_step, (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
        cv2.putText(frame, self.current_mode, (10, 65), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        # Draw current data
        data_text = f"Y:{self.current_data['pixel_y']:.0f}px D:{self.current_data['depth']:.1f}cm W:{self.current_data['bbox_width']}px"
        cv2.putText(frame, data_text, (10, h-20), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        angle_text = f"S:{self.current_data['shoulder']}deg E:{self.current_data['elbow']}deg"
        cv2.putText(frame, angle_text, (10, h-50), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        base_text = f"Base Corr: {self.current_data['base_correction']:.1f}deg"
        cv2.putText(frame, base_text, (10, h-80), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 200, 0), 2)
        
        gripper_text = f"Gripper: {'CLOSED' if self.current_data['gripper_closed'] else 'OPEN'}"
        cv2.putText(frame, gripper_text, (10, h-110), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        
        return frame
    
    def auto_align_x_axis(self, target_object="bottle"):
        """
        Step 0: Auto-align X-axis using ANFIS.
        Returns (base_angle, pixel_y, depth_cm, bbox_width) on success, None on failure.
        """
        self.current_step = "STEP 0: X-ALIGN"
        self.current_mode = "SEARCHING"
        print(f"\n🎯 Step 0: Searching for '{target_object}'...")
        self.camera.set_target_object(target_object)
        
        # Search configuration
        BASE_START = 23
        SHOULDER = 100
        ELBOW_START = 140
        
        base = BASE_START
        shoulder = SHOULDER
        elbow = ELBOW_START
        
        # Move to search position
        self.robot.move_to([base, shoulder, elbow, FIXED_WRIST_ANGLE, FIXED_ROLL, GRIPPER_OPEN])
        time.sleep(2)
        
        search_dir = 1
        
        for iteration in range(MAX_ALIGNMENT_ITERATIONS):
            time.sleep(0.5)
            detections = self.camera.last_detection
            
            if not detections:
                # Sweep search
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
            self.current_mode = "ALIGNING X"
            det = detections[0]
            error_x = det['error_x']
            bbox = det['bbox']
            bbox_width = bbox[2] - bbox[0]
            
            # Update display
            self.current_data['pixel_y'] = det['error_y']
            self.current_data['depth'] = det['distance_cm']
            self.current_data['bbox_width'] = bbox_width
            
            if abs(error_x) < 20:
                self.current_mode = "X-CENTERED ✓"
                print(f"✅ X-Axis Centered! Base={base}°")
                print(f"   Visual State: [Y={det['error_y']:.0f}px, D={det['distance_cm']:.1f}cm, W={bbox_width}px]")
                return (base, det['error_y'], det['distance_cm'], bbox_width)
            
            # ANFIS alignment
            correction = self._predict_x(error_x)
            correction = max(-30, min(30, correction))
            base += correction
            base = max(0, min(180, base))
            
            print(f"  [Align {iteration+1}] ErrX={error_x:.0f}px → Corr={correction:.1f}° → Base={base:.1f}°")
            
            self.robot.move_to([base, shoulder, elbow, FIXED_WRIST_ANGLE, FIXED_ROLL, GRIPPER_OPEN])
        
        self.current_mode = "X-ALIGN FAILED"
        print("❌ X-axis alignment failed")
        return None
    
    def capture_visual_features(self, locked_base):
        """
        Step 1: Wait for SHIFT to capture visual features.
        Returns True if captured, False if cancelled.
        """
        import msvcrt
        
        self.current_step = "STEP 1: CAPTURE"
        self.current_mode = "PRESS SHIFT"
        print("\n📸 Step 1: Press SHIFT to capture visual features (or Q to cancel)")
        
        while True:
            # Update display with current detection
            detections = self.camera.last_detection
            if detections:
                det = detections[0]
                bbox = det['bbox']
                bbox_width = bbox[2] - bbox[0]
                
                self.current_data['pixel_y'] = det['error_y']
                self.current_data['depth'] = det['distance_cm']
                self.current_data['bbox_width'] = bbox_width
            
            if msvcrt.kbhit():
                key_bytes = msvcrt.getch()
                try:
                    key = key_bytes.decode('utf-8').lower()
                except:
                    key = None
                
                # Check for SHIFT key (extended key code)
                if key_bytes == b'\xe0':  # Check for extended key
                    extended_key = msvcrt.getch()
                    # Skip this, it's arrow or other extended key
                    continue
                
                # SHIFT key is detected as a regular character shift
                # We'll use 'c' key as capture since SHIFT alone is hard to detect
                # Actually, let's use right SHIFT which is detectable
                if key == 'c':  # C for Capture (easier than detecting SHIFT alone)
                    if detections:
                        det = detections[0]
                        bbox = det['bbox']
                        bbox_width = bbox[2] - bbox[0]
                        
                        self.visual_capture = (det['error_y'], det['distance_cm'], bbox_width)
                        self.current_mode = "CAPTURED ✓"
                        print(f"✅ Visual features captured: Y={det['error_y']:.0f}px, D={det['distance_cm']:.1f}cm, W={bbox_width}px")
                        time.sleep(0.5)
                        return True
                    else:
                        print("⚠️  No detection found!")
                
                elif key == 'q':
                    self.current_mode = "CANCELLED"
                    print("❌ Cancelled")
                    return False
            
            time.sleep(0.1)
    
    def manual_reach_with_gripper(self, locked_base):
        """
        Step 2: Manual reach with gripper control and base correction.
        Returns (shoulder, elbow, base_correction, gripper_closed) on success, None if cancelled.
        """
        import msvcrt
        
        self.current_step = "STEP 2: MANUAL"
        self.current_mode = "ADJUST & SAVE"
        print("\n🎮 Step 2: Manual Reach with Gripper Control")
        print("Controls: W/S (Shoulder), A/D (Elbow), ←/→ (Base), G (Gripper), SPACE (Save)")
        
        # Track state
        current_base = locked_base
        initial_base = locked_base
        shoulder = 100
        elbow = 140
        gripper_closed = False
        gripper_angle = GRIPPER_OPEN
        
        self.robot.move_to([current_base, shoulder, elbow, FIXED_WRIST_ANGLE, FIXED_ROLL, gripper_angle])
        
        while True:
            # Update display
            self.current_data['shoulder'] = shoulder
            self.current_data['elbow'] = elbow
            self.current_data['base_correction'] = current_base - initial_base
            self.current_data['gripper_closed'] = 1 if gripper_closed else 0
            
            if msvcrt.kbhit():
                key_bytes = msvcrt.getch()
                try:
                    key = key_bytes.decode('utf-8').lower()
                except:
                    key = None
                
                # SPACE to save
                if key == ' ' or (key_bytes and ord(key_bytes) == 32):
                    base_correction = current_base - initial_base
                    gripper_state = 1 if gripper_closed else 0
                    self.current_mode = "SAVED ✓"
                    print(f"\n💾 Saving: S={shoulder}°, E={elbow}°, BaseCorr={base_correction:.1f}°, Gripper={'CLOSED' if gripper_closed else 'OPEN'}")
                    return (shoulder, elbow, base_correction, gripper_state)
                
                # G to toggle gripper
                elif key == 'g':
                    gripper_closed = not gripper_closed
                    gripper_angle = GRIPPER_CLOSED if gripper_closed else GRIPPER_OPEN
                    self.robot.move_to([current_base, shoulder, elbow, FIXED_WRIST_ANGLE, FIXED_ROLL, gripper_angle])
                    print(f"Gripper: {'CLOSED' if gripper_closed else 'OPEN'}")
                
                # Arrow keys for base correction
                elif key_bytes == b'\xe0':  # Arrow prefix
                    arrow = msvcrt.getch()
                    if arrow == b'M':  # Right Arrow
                        current_base = max(0, min(180, current_base - 1))
                        self.robot.move_to([current_base, shoulder, elbow, FIXED_WRIST_ANGLE, FIXED_ROLL, gripper_angle])
                    elif arrow == b'K':  # Left Arrow
                        current_base = max(0, min(180, current_base + 1))
                        self.robot.move_to([current_base, shoulder, elbow, FIXED_WRIST_ANGLE, FIXED_ROLL, gripper_angle])
                
                # W/S/A/D for shoulder/elbow
                elif key == 'w':
                    shoulder = min(140, shoulder + 1)
                    self.robot.move_to([current_base, shoulder, elbow, FIXED_WRIST_ANGLE, FIXED_ROLL, gripper_angle])
                elif key == 's':
                    shoulder = max(0, shoulder - 1)
                    self.robot.move_to([current_base, shoulder, elbow, FIXED_WRIST_ANGLE, FIXED_ROLL, gripper_angle])
                elif key == 'd':
                    elbow = min(160, elbow + 1)
                    self.robot.move_to([current_base, shoulder, elbow, FIXED_WRIST_ANGLE, FIXED_ROLL, gripper_angle])
                elif key == 'a':
                    elbow = max(0, elbow - 1)
                    self.robot.move_to([current_base, shoulder, elbow, FIXED_WRIST_ANGLE, FIXED_ROLL, gripper_angle])
                elif key == 'q':
                    self.current_mode = "CANCELLED"
                    print("\n❌ Cancelled")
                    return None
            
            time.sleep(0.05)
    
    def collect_sample(self):
        """Full three-step collection workflow."""
        # Step 0: X-axis alignment
        result = self.auto_align_x_axis("bottle")
        if not result:
            return False
        
        locked_base, pixel_y, depth_cm, bbox_width = result
        
        # Step 1: Capture visual features
        if not self.capture_visual_features(locked_base):
            return False
        
        # Use captured visuals
        pixel_y, depth_cm, bbox_width = self.visual_capture
        
        # Step 2: Manual reach with gripper
        reach_result = self.manual_reach_with_gripper(locked_base)
        if not reach_result:
            return False
        
        shoulder, elbow, base_correction, gripper_closed = reach_result
        
        # Save to CSV
        with open(OUTPUT_FILE, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([pixel_y, depth_cm, bbox_width, shoulder, elbow, base_correction, gripper_closed])
        
        self.sample_count += 1
        self.current_step = "IDLE"
        self.current_mode = "READY"
        print(f"✅ Sample #{self.sample_count} saved to {OUTPUT_FILE}")
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
    print("VISUAL-COMPENSATION DATA COLLECTION")
    print("=" * 60)
    
    collector = VisualCompensationCollector()
    
    # Start Flask in background
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    print("\n🌐 Video feed: http://localhost:5000")
    print("\n📋 Workflow:")
    print("  Step 0: ANFIS auto-aligns X-axis")
    print("  Step 1: Press ENTER to capture visual features")
    print("  Step 2: Manual approach + SPACE to save")
    print("\nPlace object at different positions and press ENTER to start\n")
    
    try:
        while True:
            cmd = input(f"[Sample #{collector.sample_count+1}] Press ENTER (or 'q' to quit): ").strip().lower()
            
            if cmd == 'q':
                break
            
            if collector.collect_sample():
                print(f"✅ Total samples: {collector.sample_count}")
            else:
                print("⚠️  Collection failed, try again")
    
    except KeyboardInterrupt:
        print("\n🛑 Interrupted")
    
    finally:
        print(f"\n📁 Data saved to: {OUTPUT_FILE}")
        print(f"📊 Total samples collected: {collector.sample_count}")

if __name__ == "__main__":
    main()
