# backend/features/mimic_logic.py
import cv2
import mediapipe as mp
import math
import numpy as np
import time
import threading
import torch
import os
from brain.anfis_pytorch import ANFIS

# --- CONFIGURATION ---
REAL_PALM_WIDTH = 8.5   # cm (Average palm width)
FOCAL_LENGTH = 1424     # From calibration
CENTER_TOLERANCE = 50   # Pixels within which palm is "centered"
SMOOTHING_ALPHA = 0.10  # 0.10 = Very Smooth/Heavy, 0.15 = Smooth, 0.5 = Fast/Jittery

class SmoothFilter:
    def __init__(self, alpha=0.15):
        self.alpha = alpha
        self.value = None

    def update(self, new_value):
        if self.value is None:
            self.value = new_value
        else:
            self.value = (self.alpha * new_value) + ((1 - self.alpha) * self.value)
        return self.value

class MimicController:
    def __init__(self, robot_driver, camera=None):
        self.robot = robot_driver
        self.camera = camera  # Global camera instance
        self.active = False
        
        # Smoothers for centering errors and depth
        self.smooth_error_x = SmoothFilter(SMOOTHING_ALPHA)
        self.smooth_error_y = SmoothFilter(SMOOTHING_ALPHA)
        self.smooth_depth = SmoothFilter(SMOOTHING_ALPHA)
        
        # Hand tracking state (for video overlay)
        self.hand_landmarks = None
        self.palm_center = None
        self.is_centered = False
        self.hand_lock = threading.Lock()
        
        # Telemetry state (for frontend display)
        self.telemetry = {
            "error_x": 0,
            "error_y": 0,
            "reach": 0,
            "gripper": "OPEN",
            "is_centered": False
        }
        self.telemetry_lock = threading.Lock()
        
        # MediaPipe setup - will be initialized in start()
        self.mp_hands = None
        self.mp_drawing = None
        self.mp_drawing_styles = None
        
        # --- ANFIS BRAIN INIT ---
        print("[MIMIC] Loading ANFIS Brain...")
        ranges = [(-400, 400)] # Matching visual_servoing.py for anfis_x
        self.model = ANFIS(n_inputs=1, n_rules=5, input_ranges=ranges)
        self.use_anfis = False
        
        base_dir = os.path.dirname(os.path.abspath(__file__))
        model_path = os.path.join(base_dir, '../brain/models/anfis_x.pth')
        
        try:
            if os.path.exists(model_path):
                self.model.load_state_dict(torch.load(model_path))
                self.model.eval()
                self.use_anfis = True
                print(f"[MIMIC] ANFIS Brain (X-Axis) Loaded! 🧠")
            else:
                print(f"[MIMIC] ⚠️ ANFIS model not found at {model_path}. Using Legacy P-Control.")
        except Exception as e:
            print(f"[MIMIC] Error loading brain: {e}")

    def predict_correction(self, error):
        """Neural inference for correction angle (X-axis)"""
        if not self.use_anfis: return 0.0
        with torch.no_grad():
            inputs = torch.tensor([[error]], dtype=torch.float32)
            return self.model(inputs).item()
        
    def get_hand_landmarks(self):
        """Thread-safe getter for hand landmarks to draw on video feed"""
        with self.hand_lock:
            return self.hand_landmarks, self.palm_center, self.is_centered
    
    def start(self):
        """Starts the mimic loop in the current thread (call from thread wrapper)"""
        try:
            print("[MIMIC] start() method called", flush=True)
            self.active = True
            
            # Lazy initialize MediaPipe components (avoids import issues during Flask init)
            if self.mp_hands is None:
                print("[MIMIC] Initializing MediaPipe...", flush=True)
                self.mp_hands = mp.solutions.hands
                self.mp_drawing = mp.solutions.drawing_utils
                self.mp_drawing_styles = mp.solutions.drawing_styles
                print("[MIMIC] MediaPipe initialized", flush=True)
            
            # Initialize MediaPipe detector
            print("[MIMIC] Creating MediaPipe detector...", flush=True)
            detector = self.mp_hands.Hands(
                min_detection_confidence=0.7,
                min_tracking_confidence=0.7,
                max_num_hands=1
            )
            print("--- MIMIC MODE STARTED (Visual Servoing) ---", flush=True)
            
            # Move to starting position (mid-range reach)
            print("[MIMIC] Moving to starting position...", flush=True)
            # Mid-range: shoulder ~80°, elbow ~75° (between min and max reach)
            STARTING_ANGLES = [90, 80, 75, 90, 12, 170]  # Base, Shoulder, Elbow, Wrist_Pitch, Wrist_Roll, Gripper
            self.robot.move_to(STARTING_ANGLES)
            time.sleep(1.0)
            print("[MIMIC] Ready to track!", flush=True)
            
        except Exception as e:
            print(f"[MIMIC ERROR] Failed to initialize: {e}", flush=True)
            import traceback
            traceback.print_exc()
            self.active = False
            return
        
        while self.active:
            if self.camera is None:
                print("⚠️ No camera available for Mimic Mode", flush=True)
                time.sleep(0.1)
                continue
                
            # Get frame from global camera
            frame = self.camera.get_raw_frame()
            if frame is None:
                time.sleep(0.03)
                continue

            # Process with MediaPipe
            h, w, _ = frame.shape
            frame_center_x = w // 2
            frame_center_y = h // 2
            
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = detector.process(rgb_frame)

            # Store landmarks for video overlay
            with self.hand_lock:
                if results.multi_hand_landmarks:
                    self.hand_landmarks = results.multi_hand_landmarks[0]
                else:
                    self.hand_landmarks = None
                    self.palm_center = None
                    self.is_centered = False

            if results.multi_hand_landmarks:
                for hand_lm in results.multi_hand_landmarks:
                    # === CALCULATE PALM CENTER ===
                    palm_x = ((hand_lm.landmark[0].x + hand_lm.landmark[9].x) / 2) * w
                    palm_y = ((hand_lm.landmark[0].y + hand_lm.landmark[9].y) / 2) * h
                    
                    # Store for visual overlay
                    with self.hand_lock:
                        self.palm_center = (int(palm_x), int(palm_y))
                    
                    # === CENTERING ERROR CALCULATION ===
                    error_x = frame_center_x - palm_x
                    error_y = frame_center_y - palm_y
                    
                    # Check if centered
                    is_centered = abs(error_x) <= CENTER_TOLERANCE and abs(error_y) <= CENTER_TOLERANCE
                    with self.hand_lock:
                        self.is_centered = is_centered
                    
                    # Apply smoothing
                    s_error_x = self.smooth_error_x.update(error_x)
                    s_error_y = self.smooth_error_y.update(error_y)
                    
                    # === DEPTH CALCULATION (Pinhole Camera Theory) ===
                    x5 = hand_lm.landmark[5].x * w
                    y5 = hand_lm.landmark[5].y * h
                    x17 = hand_lm.landmark[17].x * w
                    y17 = hand_lm.landmark[17].y * h
                    palm_width_px = math.hypot(x17 - x5, y17 - y5)
                    
                    if palm_width_px > 1:
                        distance_cm = (REAL_PALM_WIDTH * FOCAL_LENGTH) / palm_width_px
                    else:
                        distance_cm = 999
                    
                    # Use actual distance for reach (no normalization)
                    # This allows full 15-45cm range to be displayed and used
                    s_reach = self.smooth_depth.update(distance_cm)
                    
                    # === GRIPPER (Thumb-Index Pinch) ===
                    thumb_x = hand_lm.landmark[4].x * w
                    thumb_y = hand_lm.landmark[4].y * h
                    index_x = hand_lm.landmark[8].x * w
                    index_y = hand_lm.landmark[8].y * h
                    pinch = math.hypot(index_x - thumb_x, index_y - thumb_y)
                    gripper = 120 if pinch < 40 else 180
                    gripper_state = "CLOSED" if gripper == 120 else "OPEN"
                    
                    # === UPDATE TELEMETRY ===
                    with self.telemetry_lock:
                        self.telemetry = {
                            "error_x": round(s_error_x, 1),
                            "error_y": round(s_error_y, 1),
                            "reach": round(s_reach, 1),
                            "gripper": gripper_state,
                            "is_centered": is_centered
                        }
                    
                    # === SEND COMMANDS TO ROBOT ===
                    # Control Constants (tuned for smooth hand tracking)
                    GAIN_X = 0.005     # Base rotation gain (reduced for stability)
                    GAIN_Y = 0.005     # Elbow tilt gain (reduced for stability)
                    MAX_STEP = 1.0     # Max angle change per frame (limit to 1 deg)
                    MIN_MOVE = 0.2     # Minimum movement threshold (allow fine control)
                    
                    # Fixed servos for mimic mode
                    WRIST_PITCH = 90
                    WRIST_ROLL = 12
                    
                    # Get current angles
                    current_angles = self.robot.current_angles
                    current_base = current_angles[0]
                    
                    # Calculate Base correction (X-axis centering)
                    # Calculate Base correction (X-axis centering)
                    # HYBRID CONTROL: Use ANFIS if available, else P-Control
                    if self.use_anfis:
                         # Neural Network Control
                         base_correction = self.predict_correction(s_error_x)
                         # Note: ANFIS output is already clamped/scaled by training data (-1 to 1 mostly)
                         # But let's respect the MAX_STEP speed limit
                         base_correction = max(-MAX_STEP, min(MAX_STEP, base_correction))
                    else:
                        # Legacy P-Control
                        base_correction = s_error_x * GAIN_X
                        if abs(base_correction) < MIN_MOVE and abs(base_correction) > 0.1:
                            base_correction = MIN_MOVE * (1 if base_correction > 0 else -1)
                        base_correction = max(-MAX_STEP, min(MAX_STEP, base_correction))
                    new_base = max(0, min(180, current_base + base_correction))
                    
                    # Map reach to shoulder and elbow (FULL RANGE)
                    # Close palm (20cm) -> shoulder=155°, elbow=150° (minimum reach)
                    # Far palm (65cm) -> shoulder=0°, elbow=0° (maximum reach)
                    base_shoulder = np.interp(s_reach, [20, 65], [155, 0])
                    base_elbow = np.interp(s_reach, [20, 65], [150, 0])
                    
                    # Apply Y-axis centering correction on top of reach-based elbow
                    elbow_correction = -(s_error_y * GAIN_Y)  # Negative because up = lower angle
                    if abs(elbow_correction) < MIN_MOVE and abs(elbow_correction) > 0.1:
                        elbow_correction = MIN_MOVE * (1 if elbow_correction > 0 else -1)
                    elbow_correction = max(-MAX_STEP, min(MAX_STEP, elbow_correction))
                    
                    new_shoulder = max(0, min(180, base_shoulder))
                    new_elbow = max(0, min(150, base_elbow + elbow_correction))
                    
                    # Send to robot
                    try:
                        self.robot.move_to([new_base, new_shoulder, new_elbow, WRIST_PITCH, WRIST_ROLL, gripper])
                        
                        if not is_centered:
                            print(f"\r[MIMIC] Tracking: X={s_error_x:+.0f}px Y={s_error_y:+.0f}px | Base={new_base:.0f}° Elbow={new_elbow:.0f}° | Reach={s_reach:.1f}cm | {gripper_state}    ", end="", flush=True)
                        else:
                            print(f"\r[MIMIC] ✓ CENTERED | Base={new_base:.0f}° Shoulder={new_shoulder:.0f}° Elbow={new_elbow:.0f}° | Reach={s_reach:.1f}cm | {gripper_state}    ", end="", flush=True)
                            
                    except Exception as e:
                        print(f"\n[MIMIC ERROR] Failed to move robot: {e}", flush=True)
                        import traceback
                        traceback.print_exc()
            
            time.sleep(0.03)

        # Cleanup
        detector.close()
        with self.hand_lock:
            self.hand_landmarks = None
            self.palm_center = None
            self.is_centered = False
        print("\n--- MIMIC MODE STOPPED ---", flush=True)

    def stop(self):
        self.active = False
    
    def get_telemetry(self):
        """Thread-safe getter for telemetry data"""
        with self.telemetry_lock:
            return self.telemetry.copy()
        
    def draw_hand_overlay(self, frame):
        """Draw hand landmarks and centering visualization on frame for video feed"""
        landmarks, palm_center, is_centered = self.get_hand_landmarks()
        
        h, w, _ = frame.shape
        frame_center_x = w // 2
        frame_center_y = h // 2
        
        # Draw frame center crosshair
        cv2.line(frame, (frame_center_x - 30, frame_center_y), 
                (frame_center_x + 30, frame_center_y), (0, 255, 255), 2)
        cv2.line(frame, (frame_center_x, frame_center_y - 30), 
                (frame_center_x, frame_center_y + 30), (0, 255, 255), 2)
        cv2.circle(frame, (frame_center_x, frame_center_y), 
                  CENTER_TOLERANCE, (0, 255, 255), 2)
        
        # Draw hand skeleton
        if landmarks:
            self.mp_drawing.draw_landmarks(
                frame,
                landmarks,
                self.mp_hands.HAND_CONNECTIONS,
                self.mp_drawing_styles.get_default_hand_landmarks_style(),
                self.mp_drawing_styles.get_default_hand_connections_style()
            )
            
            # Draw palm center and error line
            if palm_center:
                cv2.circle(frame, palm_center, 10, (255, 0, 255), -1)
                cv2.line(frame, (frame_center_x, frame_center_y), 
                        palm_center, (255, 0, 255), 2)
                
                # Status text
                if is_centered:
                    status_text = "CENTERED"
                    status_color = (0, 255, 0)
                else:
                    error_x = frame_center_x - palm_center[0]
                    error_y = frame_center_y - palm_center[1]
                    status_text = f"Centering... ({abs(int(error_x))}px, {abs(int(error_y))}px)"
                    status_color = (0, 165, 255)
                
                cv2.putText(frame, status_text, (10, h - 20),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2)
        
        return frame
