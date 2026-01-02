import cv2
import threading
import time
import numpy as np
from coordinate_mapper import CoordinateMapper
from yolo_detector import YOLODetector
from brain.distance_estimator import (
    estimate_distance_from_detection,
    get_object_pixel_width,
    FOCAL_LENGTH_DEFAULT,
    KNOWN_OBJECT_WIDTHS
)
from brain.visual_ik_solver import GRIPPER_LENGTH
from hybrid_tracker import HybridTracker
import os

class VideoCamera(object):
    def __init__(self, detection_mode='yolo', center_tolerance=25, focal_length_override=None):
        """
        Initialize VideoCamera.
        
        Args:
            detection_mode: 'yolo' for object detection or 'color' for color-based detection
            center_tolerance: Pixel tolerance for "centered" alignment (default: 25)
            focal_length_override: Override focal length (pixels) for calibration (default: None uses 1424)
        """
        # Default objects to detect (General Workplace Items)
        self.DEFAULT_CLASSES = [
            "person", "bottle", "cup", "cell phone", "mouse", "keyboard", 
            "laptop", "scissors", "stapler", "pen", "glasses", "sunglasses",
             "red cube", "blue cube", "green cube", "yellow cube"
        ]
        
        # Try to find a working camera index
        target_index = int(os.environ.get("CAMERA_INDEX", 1))
        
        # Backends to try for Windows compatibility
        backends = [
            ("DSHOW", cv2.CAP_DSHOW),
            ("MSMF", cv2.CAP_MSMF),
            ("DEFAULT", cv2.CAP_ANY)
        ]
        
        self.video = None
        self._open_camera()
            
        
        # Detection mode: 'yolo' or 'color'
        self.detection_mode = detection_mode
        
        # For color detection mode
        self.target_colors = ["Red", "Blue", "Green", "Yellow"] 
        
        # For YOLO detection mode
        self.yolo_detector = None
        if detection_mode == 'yolo':
            self.yolo_detector = YOLODetector(confidence_threshold=0.3)
            # Set default classes for YOLO-World
            if hasattr(self.yolo_detector, 'set_classes'):
                self.yolo_detector.set_classes(self.DEFAULT_CLASSES)
        
        # Center-seeking state
        self.target_object = None  # Target object name for filtering (e.g., "bottle")
        self.center_tolerance = center_tolerance  # Pixels within which object is "centered"
        
        self.last_detection = [] # Stores list of all detections
        self.mapper = None # Initialize mapper lazily when we have frame dimensions
        
        # Distance Estimation (Logitech C270 at 1280x720)
        # Allow override for calibration
        if focal_length_override is not None:
            self.focal_length = focal_length_override
            print(f"[INFO] Distance estimation enabled (Focal Length: {self.focal_length}px - OVERRIDE)")
        else:
            self.focal_length = FOCAL_LENGTH_DEFAULT  # 1110 pixels
            print(f"[INFO] Distance estimation enabled (Focal Length: {self.focal_length}px)")
        
        self.known_object_widths = KNOWN_OBJECT_WIDTHS
        
        self.color_ranges = {
            "Red": [
                (np.array([0, 120, 70]), np.array([10, 255, 255])),
                (np.array([170, 120, 70]), np.array([180, 255, 255]))
            ],
            "Blue": [
                (np.array([94, 80, 2]), np.array([126, 255, 255]))
            ],
            "Green": [
                (np.array([25, 52, 72]), np.array([102, 255, 255]))
            ],
            "Yellow": [
                (np.array([20, 100, 100]), np.array([30, 255, 255]))
            ]
        }
        
        # Threading support
        self.lock = threading.Lock()
        self.raw_frame = None
        self.processed_jpeg = None
        self.stopped = False
        self.pause_yolo = False  # Flag to pause YOLO processing
        
        # Frame containers for async inference
        self.latest_frame_for_inference = None
        self.inference_lock = threading.Lock()
        
        # Hybrid Tracker for Blind Spot handling (<15cm)
        self.hybrid_tracker = HybridTracker()
        self.last_detection_distance = 999.0  # Track distance for handover
        self.hybrid_mode_active = False
        print("[INFO] Hybrid Tracker initialized for <15cm blind spot handling.")
        
        # Start background capture thread
        print("[INFO] Starting background capture thread...")
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()

        # Start background INFERENCE thread (Decoupled to prevent video freeze)
        print("[INFO] Starting background inference thread...")
        self.inference_thread = threading.Thread(target=self._inference_loop, daemon=True)
        self.inference_thread.start()

    def _inference_loop(self):
        """
        Dedicated thread for YOLO inference.
        Runs as fast as possible but doesn't block the video feed.
        """
        print("[INFO] Inference thread started.")
        inference_counter = 0
        while not self.stopped:
            try:
                # Check if paused (e.g. mimic mode)
                if self.pause_yolo:
                    time.sleep(0.1)
                    continue

                # Get latest available frame
                frame_to_process = None
                with self.inference_lock:
                    if self.latest_frame_for_inference is not None:
                         frame_to_process = self.latest_frame_for_inference.copy()
                
                if frame_to_process is None:
                    time.sleep(0.01)
                    continue
                
                # Heartbeat every 50 frames
                inference_counter += 1
                if inference_counter % 50 == 0:
                    print(f"[INFERENCE-HEARTBEAT] Running... (frame {inference_counter})")
                
                # Run Inference logic
                if self.detection_mode == 'yolo':
                        self.find_objects_yolo(frame_to_process) # Updates self.last_detection internal state
                elif self.target_colors:
                        self.find_objects(frame_to_process) # Updates self.last_detection internal state
                
                # Yield to CPU
                time.sleep(0.01)

            except Exception as e:
                print(f"[ERROR] CRITICAL INFERENCE LOOP ERROR: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(1) # Prevent spamming on repeated error

    def _capture_loop(self):
        """
        Background thread to continuously read and process frames.
        Ensures thread-safety and consistent FPS for all consumers.
        """
        consecutive_failures = 0
        self.last_frame_time = time.time()
        
        # Start Watchdog Timer
        self.watchdog = threading.Thread(target=self._watchdog_loop, daemon=True)
        self.watchdog.start()
        
        print("[INFO] Capture thread started.")
        while not self.stopped:
            # Update heartbeat
            self.last_frame_time = time.time()
            
            # Check if camera needs opening
            if self.video is None or not self.video.isOpened():
                print("[CAMERA] Camera disconnected or released. Attempting to reconnect...")
                if self._open_camera():
                     consecutive_failures = 0
                else:
                     time.sleep(2.0) # Wait before retry
                     continue
            try:
                if not self.video.isOpened():
                    print("[WARN] Camera not opened, retrying...")
                    time.sleep(0.5)
                    continue
                    
                success, image = self.video.read()
                if not success:
                    consecutive_failures += 1
                    if consecutive_failures > 10:
                        print("[CAMERA] Too many read errors. Re-initializing...")
                        self.video.release() # Force close to trigger full reopen
                        consecutive_failures = 0
                    time.sleep(0.01)
                    continue
                
                consecutive_failures = 0 # Reset on success
                    
                # Store raw frame
                self.raw_frame = image.copy()
                
                # Update frame for inference thread
                with self.inference_lock:
                    self.latest_frame_for_inference = image.copy()
                
                # Skip YOLO processing if paused (e.g., during mimic mode)
                if self.pause_yolo:
                    # Just show raw frame with "YOLO PAUSED" text
                    display_frame = image.copy()
                    cv2.putText(display_frame, "YOLO PAUSED", (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                    ret, jpeg = cv2.imencode('.jpg', display_frame)
                    if ret:
                        self.processed_jpeg = jpeg.tobytes()
                    time.sleep(0.01)
                    continue
                
                # Prepare display frame
                display_frame = image.copy()
                height, width, _ = display_frame.shape
                cx, cy = width // 2, height // 2
                
                # Simple visual guides (always present)
                cv2.line(display_frame, (cx - 20, cy), (cx + 20, cy), (200, 200, 200), 1)
                cv2.line(display_frame, (cx, cy - 20), (cx, cy + 20), (200, 200, 200), 1)
                
                # DRAW LATEST DETECTIONS (Non-blocking)
                # Use self.last_detection which is updated by the inference thread
                if self.detection_mode == 'yolo' and self.yolo_detector:
                    cv2.putText(display_frame, "Mode: YOLO-World", (10, 30), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                    
                    if self.last_detection:
                        self.yolo_detector.draw_detections(display_frame, self.last_detection)
                        
                    # Add Center-seeking visuals
                    if self.target_object and self.last_detection:
                        self._draw_overlay(display_frame)

                elif self.target_colors:
                    cv2.putText(display_frame, "Mode: Color", (10, 30), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
                    if self.last_detection:
                        for det in self.last_detection:
                            if 'cm_x' in det: 
                                obj_x = int(cx + det['x'])
                                obj_y = int(cy - det['y']) 
                                
                                cv2.circle(display_frame, (obj_x, obj_y), 30, (0, 255, 0), 2)
                                cv2.putText(display_frame, det.get('color', 'Target'), (obj_x, obj_y - 40), 
                                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,0), 2)

                else:
                    cv2.putText(display_frame, "Mode: Idle", (10, 30), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                
                # Encode result to JPEG
                ret, jpeg = cv2.imencode('.jpg', display_frame)
                if ret:
                    self.processed_jpeg = jpeg.tobytes()
                    
                # Small yield to prevent CPU hogging if capture is uncapped
                time.sleep(0.01)

            except Exception as e:
                print(f"[ERROR] CRITICAL CAPTURE LOOP ERROR: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(1)

    def _draw_overlay(self, frame):
        """Helper to draw overlay graphics on the display frame"""
        height, width, _ = frame.shape
        frame_center_x = width // 2
        frame_center_y = height // 2
        
        if self.last_detection:
            det = self.last_detection[0]
            
            # Draw frame center crosshair (larger)
            cv2.line(frame, (frame_center_x - 30, frame_center_y), 
                        (frame_center_x + 30, frame_center_y), (0, 255, 255), 2)
            cv2.line(frame, (frame_center_x, frame_center_y - 30), 
                        (frame_center_x, frame_center_y + 30), (0, 255, 255), 2)
            cv2.circle(frame, (frame_center_x, frame_center_y), 
                        self.center_tolerance, (0, 255, 255), 2)
            
            # Navigation text
            abs_error_x = abs(det['error_x'])
            abs_error_y = abs(det['error_y'])
            
            direction_x_text = "RIGHT" if det['error_x'] > 0 else "LEFT"
            direction_y_text = "DOWN" if det['error_y'] > 0 else "UP"
            
            # Display X/Y Offsets and Distance in top-left area
            cv2.putText(frame, f"X Offset: {abs_error_x}px", (30, 120), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            cv2.putText(frame, f"Y Offset: {abs_error_y}px", (30, 150), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            
            # Display distance (always shown, updates in real-time)
            if det.get('distance_cm', -1) >= 0:
                distance_color = (0, 255, 0) if det['is_centered'] else (0, 255, 255)
                cv2.putText(frame, f"Distance: {det['distance_cm']:.1f} cm", (30, 180), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, distance_color, 2)
            else:
                cv2.putText(frame, "Distance: UNKNOWN", (30, 180),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (128, 128, 128), 2)

            if det['is_centered']:
                status_color = (0, 255, 0)
                status_text = "✓ CENTERED"
                cv2.putText(frame, status_text, (50, height - 60),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, status_color, 2)
            else:
                status_color = (0, 165, 255)
                nav_line1 = f"Move {abs_error_x}px {direction_x_text}"
                nav_line2 = f"Move {abs_error_y}px {direction_y_text}"
                cv2.putText(frame, nav_line1, (50, height - 110),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, status_color, 2)
                cv2.putText(frame, nav_line2, (50, height - 70),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, status_color, 2)

            cv2.putText(frame, f"Target: {self.target_object}", (50, height - 150),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)


    def __del__(self):
        self.stop()

    def _watchdog_loop(self):
        """
        Monitors the capture loop. If no new frames are processed for 5 seconds,
        it assumes the camera driver is hung and forces a restart.
        """
        print("[WATCHDOG] Camera watchdog started.")
        while not self.stopped:
            time.sleep(2.0)
            if time.time() - self.last_frame_time > 5.0 and self.video is not None:
                print(f"[WATCHDOG] CRITICAL: Camera freeze detected! Last frame was {time.time() - self.last_frame_time:.1f}s ago.")
                print("[WATCHDOG] Force-releasing camera to trigger restart...")
                
                # Force release the video object to break the blocking read() if possible
                try:
                     if self.video: self.video.release()
                except:
                     pass
                self.video = None # This will trigger _capture_loop to reconnect

    def stop(self):
        """Stop the camera and capture thread."""
        self.stopped = True
        if hasattr(self, 'thread'):
            self.thread.join(timeout=1.0)
        self.video.release()
    
    def set_detection_mode(self, mode):
        """
        Set detection mode: 'yolo' or 'color'.
        """
        if mode not in ['yolo', 'color']:
            print(f"[ERROR] Invalid detection mode: {mode}. Use 'yolo' or 'color'.")
            return
        
        self.detection_mode = mode
        self.last_detection = []
        
        # Initialize YOLO detector if switching to YOLO mode
        if mode == 'yolo' and self.yolo_detector is None:
            self.yolo_detector = YOLODetector(confidence_threshold=0.3)
            # Apply default classes
            if hasattr(self.yolo_detector, 'set_classes'):
                self.yolo_detector.set_classes(self.DEFAULT_CLASSES)
        
        print(f"[INFO] Detection mode set to: {mode}")
    
    def set_target_object(self, object_name):
        """
        Set target object for center-seeking.
        Only this object will be shown in detections.
        
        Args:
            object_name: Name of object to track (e.g., "bottle", "cup")
        """
        self.target_object = object_name.lower() if object_name else None
        self.last_detection = []  # Clear detections when target changes
        
        # NOTE: We do NOT call set_classes dynamically because it breaks detection
        # Instead, we filter in software in find_objects_yolo
        print(f"[INFO] Target object set to: {self.target_object} (filtering detections)")
    
    def clear_target_object(self):
        """
        Clear target object filter. Returns to detecting all objects.
        """
        self.target_object = None
        self.last_detection = []
        
        # NOTE: Not resetting classes - detection always runs with full class set
        print(f"[INFO] Target object cleared - showing all objects")
    
    def set_target_colors(self, color_names):
        """
        Set target colors to search for (for color detection mode).
        color_names: list of color names or None
        """
        if color_names is None:
            self.target_colors = []
        else:
            # Filter to only valid colors
            self.target_colors = [c for c in color_names if c in self.color_ranges]
        
        self.last_detection = [] # Reset detection on new targets
        print(f"[INFO] Target colors set to: {self.target_colors}")
    
    def find_objects_yolo(self, frame):
        """
        Find objects using YOLO detection with Hybrid Tracker handover at <15cm.
        Filters to target_object if set, and calculates center alignment errors.
        """
        if self.yolo_detector is None:
            self.yolo_detector = YOLODetector(confidence_threshold=0.3)
        
        # Get frame dimensions
        height, width, _ = frame.shape
        frame_center_x = width // 2
        frame_center_y = height // 2
        
        # --- HYBRID TRACKING LOGIC ---
        # If last detection was <15cm, activate hybrid mode
        use_hybrid = self.last_detection_distance < 15.0
        
        if use_hybrid:
            if not self.hybrid_mode_active:
                print(f"[HYBRID] Activating tracker at {self.last_detection_distance:.1f}cm")
                self.hybrid_mode_active = True
            
            # Use hybrid tracker (YOLO + CSRT fallback)
            result = self.hybrid_tracker.get_target(frame, self.yolo_detector.model, target_class=self.target_object)
            
            if result['source'] != 'NONE':
                # Convert hybrid result to standard detection format
                bbox = result['bbox']  # (x, y, w, h)
                center = result['center']  # (cx, cy)
                
                # Convert to YOLO format [x1, y1, x2, y2] for consistency
                x, y, w, h = bbox
                yolo_bbox = [x, y, x+w, y+h]
                
                # Calculate errors
                error_x = frame_center_x - center[0]
                error_y = frame_center_y - center[1]
                
                direction_x = "RIGHT" if error_x > 0 else "LEFT" if error_x < 0 else "CENTERED"
                direction_y = "DOWN" if error_y > 0 else "UP" if error_y < 0 else "CENTERED"
                is_centered = abs(error_x) <= self.center_tolerance and abs(error_y) <= self.center_tolerance
                
                # Distance estimation from bbox (approximate)
                # Use width-based estimation
                obj_name = self.target_object if self.target_object else "bottle"
                if obj_name in self.known_object_widths:
                    real_width = self.known_object_widths[obj_name]
                    pixel_width = w
                    distance_cm = (real_width * self.focal_length) / pixel_width if pixel_width > 0 else 999
                    distance_cm = max(0.0, distance_cm - GRIPPER_LENGTH)
                    distance_status = f"{distance_cm:.1f}cm [{result['source']}]"
                else:
                    distance_cm = self.last_detection_distance  # Use last known
                    distance_status = f"{distance_cm:.1f}cm [{result['source']}-EST]"
                
                # Update tracking distance
                self.last_detection_distance = distance_cm
                
                # Build detection dict
                new_detections = [{
                    'object_name': obj_name,
                    'confidence': 0.9 if result['source'] == 'YOLO' else 0.7,  # Lower conf for tracker
                    'x': center[0],
                    'y': center[1],
                    'cm_x': 0,  # Not used in servoing
                    'cm_y': 0,
                    'bbox': yolo_bbox,
                    'center': center,
                    'error_x': error_x,
                    'error_y': error_y,
                    'direction_x': direction_x,
                    'direction_y': direction_y,
                    'is_centered': is_centered,
                    'distance_cm': distance_cm,
                    'distance_status': distance_status,
                    'timestamp': time.time(),
                    'source': result['source']  # Track source
                }]
                
                self.last_detection = new_detections
                return
            else:
                # Even hybrid failed
                print("[HYBRID] Tracker lost object too.")
                self.last_detection = []
                return
        
        # --- STANDARD YOLO MODE (distance >= 15cm OR first detection) ---
        if self.hybrid_mode_active:
            print(f"[HYBRID] Deactivating tracker (dist >= 15cm)")
            self.hybrid_mode_active = False
        
        detections = self.yolo_detector.detect_objects(frame)
        
        # Filter by target_object if set
        if self.target_object:
            detections = [d for d in detections if d['object_name'].lower() == self.target_object]
        
        # Update results in a thread-safe way using a local list
        new_detections = []
        for det in detections:
            # Calculate object center from bounding box
            bbox = det['bbox']
            object_center_x = (bbox[0] + bbox[2]) // 2
            
            # Target Point: 1/4th from the TOP of the bounding box (as per user request)
            bbox_height = bbox[3] - bbox[1]
            object_center_y = int(bbox[1] + (bbox_height * 0.25))
            
            # Calculate alignment error
            error_x = frame_center_x - object_center_x
            error_y = frame_center_y - object_center_y
            
            # Determine movement directions
            direction_x = "RIGHT" if error_x > 0 else "LEFT" if error_x < 0 else "CENTERED"
            direction_y = "DOWN" if error_y > 0 else "UP" if error_y < 0 else "CENTERED"
            
            # Check if centered (within tolerance)
            is_centered = abs(error_x) <= self.center_tolerance and abs(error_y) <= self.center_tolerance
            
            # Calculate distance using pinhole camera model
            distance_cm = estimate_distance_from_detection(det, self.focal_length)
            
            # If distance cannot be estimated (unknown object), set to -1
            if distance_cm == -1.0:
                distance_cm = -1.0
                distance_status = "UNKNOWN"
            else:
                # Calculate distance relative to gripper
                distance_cm = max(0.0, distance_cm - GRIPPER_LENGTH)
                distance_status = f"{distance_cm:.1f}cm"
            
            # Track distance for hybrid handover
            if distance_cm > 0:
                self.last_detection_distance = distance_cm
            
            new_detections.append({
                'object_name': det['object_name'],
                'confidence': det['confidence'],
                'x': det['relative_pos'][0],
                'y': det['relative_pos'][1],
                'cm_x': det['cm_x'],
                'cm_y': det['cm_y'],
                'bbox': det['bbox'],
                'center': (object_center_x, object_center_y),
                'error_x': error_x,
                'error_y': error_y,
                'direction_x': direction_x,
                'direction_y': direction_y,
                'is_centered': is_centered,
                'distance_cm': distance_cm,
                'distance_status': distance_status,
                'timestamp': time.time(),
                'source': 'YOLO'  # Track source
            })
        
        # Atomic swap
        self.last_detection = new_detections
        
        # Draw detections on frame (only target object if filter is active)
        frame = self.yolo_detector.draw_detections(frame, detections)
        
        # Display distance and offsets for ALL detections (always visible)
        if self.last_detection:
            det = self.last_detection[0]  # Use first (closest) detection
            
            # Calculate pixel errors
            abs_error_x = abs(det['error_x'])
            abs_error_y = abs(det['error_y'])
            
            # Calculate CM error if mapper is available
            cm_error_x = 0.0
            cm_error_y = 0.0
            if self.yolo_detector and self.yolo_detector.mapper:
                cm_error_x = abs_error_x / self.yolo_detector.mapper.pixels_per_cm_x
                cm_error_y = abs_error_y / self.yolo_detector.mapper.pixels_per_cm_y
            
            # Display X/Y Corrections and Distance in top-left area (near each other)
            cv2.putText(frame, f"X Offset: {abs_error_x}px ({cm_error_x:.1f} cm)", (30, 120), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            cv2.putText(frame, f"Y Offset: {abs_error_y}px ({cm_error_y:.1f} cm)", (30, 150), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            
            # Display distance (always shown, updates in real-time)
            if det['distance_cm'] >= 0:
                distance_color = (0, 255, 0) if det['is_centered'] else (0, 255, 255)
                cv2.putText(frame, f"Distance: {det['distance_cm']:.1f} cm", (30, 180), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, distance_color, 2)
            else:
                cv2.putText(frame, "Distance: UNKNOWN", (30, 180),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (128, 128, 128), 2)
        
        # Add center-seeking visual guides (only when target object is set)
        if self.target_object and self.last_detection:
            det = self.last_detection[0]  # Use first (closest) detection
            
            # Draw frame center crosshair (larger)
            cv2.line(frame, (frame_center_x - 30, frame_center_y), 
                     (frame_center_x + 30, frame_center_y), (0, 255, 255), 2)
            cv2.line(frame, (frame_center_x, frame_center_y - 30), 
                     (frame_center_x, frame_center_y + 30), (0, 255, 255), 2)
            cv2.circle(frame, (frame_center_x, frame_center_y), 
                      self.center_tolerance, (0, 255, 255), 2)
            
            # Determine directions (from robot/camera perspective)
            # error_x > 0: object is left of center → move RIGHT
            # error_x < 0: object is right of center → move LEFT
            direction_x_text = "RIGHT" if det['error_x'] > 0 else "LEFT"
            direction_y_text = "DOWN" if det['error_y'] > 0 else "UP"
            
            abs_error_x = abs(det['error_x'])
            abs_error_y = abs(det['error_y'])
            
            # Draw alignment status
            if det['is_centered']:
                status_color = (0, 255, 0)  # Green
                status_text = "✓ CENTERED - Ready to pick!"
                cv2.putText(frame, status_text, (50, height - 60),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, status_color, 2)
            else:
                status_color = (0, 165, 255)  # Orange
                # Show navigation directions
                nav_line1 = f"Move {abs_error_x}px {direction_x_text}"
                nav_line2 = f"Move {abs_error_y}px {direction_y_text}"
                
                # Adjusted positions to ensure visibility (moved further up)
                cv2.putText(frame, nav_line1, (50, height - 110),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, status_color, 2)
                cv2.putText(frame, nav_line2, (50, height - 70),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, status_color, 2)
            
            # Show target object name at top of bottom section
            cv2.putText(frame, f"Target: {self.target_object}", (50, height - 150),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        
        # Print detection status
        if self.last_detection:
            count = len(self.last_detection)
            if self.target_object:
                det = self.last_detection[0]
                if det['is_centered']:
                    print(f"\r[ALIGNMENT] ✓ Target '{self.target_object}' is CENTERED!      ", end="")
                else:
                    # Calculate absolute offsets
                    abs_error_x = abs(det['error_x'])
                    abs_error_y = abs(det['error_y'])
                    
                    # Determine directions for user-friendly navigation
                    # error_x > 0 means object is LEFT of center → user should move camera/robot RIGHT
                    # error_x < 0 means object is RIGHT of center → user should move camera/robot LEFT
                    direction_x_text = "to the right" if det['error_x'] > 0 else "to the left"
                    direction_y_text = "down" if det['error_y'] > 0 else "up"
                    
                    # Build navigation message
                    nav_message = f"Target is {abs_error_x} pixels {direction_x_text}, {abs_error_y} pixels {direction_y_text}"
                    print(f"\r[ALIGNMENT] {nav_message}      ", end="")
            else:
                objects = ', '.join([f"{d['object_name']}({d['confidence']:.2f})" for d in self.last_detection])
                print(f"\r[YOLO] Found {count} object(s): {objects}      ", end="")
        else:
            if self.target_object:
                print(f"\r[YOLO] Searching for '{self.target_object}'...      ", end="")
            else:
                print(f"\r[YOLO] Searching for objects...      ", end="")
        
        return frame

    def find_objects(self, frame):
        """
        Find all objects for all target colors.
        """
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        height, width, _ = frame.shape
        center_x, center_y = width // 2, height // 2
        
        # Initialize mapper if not already done
        if self.mapper is None:
            self.mapper = CoordinateMapper(width, height)

        # Reset detection list (local for thread-safety)
        new_detections = []
        
        # Process each target color
        for color_name in self.target_colors:
            mask = np.zeros((height, width), dtype=np.uint8)
            ranges = self.color_ranges.get(color_name)
            
            if ranges:
                for (lower, upper) in ranges:
                    mask += cv2.inRange(hsv, lower, upper)
            
            mask = cv2.erode(mask, None, iterations=2)
            mask = cv2.dilate(mask, None, iterations=2)
            
            contours, _ = cv2.findContours(mask.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # Process all contours for this color
            for c in contours:
                if cv2.contourArea(c) > 500:
                    ((x, y), radius) = cv2.minEnclosingCircle(c)
                    M = cv2.moments(c)
                    if M["m00"] > 0:
                        cx = int(M["m10"] / M["m00"])
                        cy = int(M["m01"] / M["m00"])
                        
                        dx = cx - center_x
                        dy = center_y - cy 
                        
                        # Calculate Real-World Coordinates (cm)
                        # Note: We map the absolute pixel coordinates (cx, cy)
                        # But typically for a robot arm, we might want coordinates relative to the center or base.
                        # The user asked for "pixel_to_cm(pixel_x, pixel_y)" which maps 0-width to 0-29.7cm.
                        # So we pass the absolute (cx, cy).
                        cm_x, cm_y = self.mapper.pixel_to_cm(cx, cy)

                        # Add to detection list
                        new_detections.append({
                            "color": color_name,
                            "x": dx,      # Relative pixel x (for UI/Center offset)
                            "y": dy,      # Relative pixel y
                            "cm_x": cm_x, # Real-world x in cm
                            "cm_y": cm_y, # Real-world y in cm
                            "timestamp": time.time()
                        })
                        
                        # Visual feedback - use different colors for different target colors
                        box_color = {
                            "Red": (0, 0, 255),
                            "Blue": (255, 0, 0),
                            "Green": (0, 255, 0),
                            "Yellow": (0, 255, 255)
                        }.get(color_name, (0, 255, 0))
                        
                        cv2.circle(frame, (int(x), int(y)), int(radius), box_color, 2)
                        cv2.circle(frame, (cx, cy), 5, (0, 0, 255), -1)
                        cv2.line(frame, (center_x, center_y), (cx, cy), (255, 0, 0), 1)
                        
                        text = f"{color_name[:1]}({dx},{dy})"
                        cv2.putText(frame, text, (cx - 30, cy - 20), 
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, box_color, 2)
        
        # Atomic swap
        self.last_detection = new_detections
        
        if self.last_detection:
            count = len(self.last_detection)
            colors_str = ", ".join(self.target_colors)
            print(f"\r[SEARCH] Found {count} object(s) for {colors_str}      ", end="")
        else:
            colors_str = ", ".join(self.target_colors)
            print(f"\r[SEARCH] Searching for {colors_str}...      ", end="")
        
        return frame

    def get_frame(self):
        """
        Returns the latest processed frame as JPEG bytes.
        This no longer calls read() directly, making it thread-safe.
        """
        return self.processed_jpeg
    
    def get_raw_frame(self):
        """
        Returns the latest raw frame (numpy array) for processing.
        Used by mimic mode for MediaPipe hand detection.
        """
        return self.raw_frame
    
    def get_frame_with_detections(self):
        """
        Returns the latest frame with YOLO detections as JPEG bytes.
        Same as get_frame() but explicitly named for clarity.
        """
        return self.processed_jpeg


    def _open_camera(self):
        """Attempts to open the camera (Target Index -> Fallback 0)"""
        if self.video and self.video.isOpened():
             self.video.release()
             
        self.video = cv2.VideoCapture()
        backends = [("DSHOW", cv2.CAP_DSHOW), ("MSMF", cv2.CAP_MSMF), ("DEFAULT", cv2.CAP_ANY)]
        
        indices_to_try = [int(os.environ.get("CAMERA_INDEX", 1))]
        if indices_to_try[0] != 0: indices_to_try.append(0)
        
        for idx in indices_to_try:
            print(f"[CAMERA] Attempting to open Camera {idx}...")
            for b_name, b_val in backends:
                self.video.open(idx, b_val)
                if self.video.isOpened():
                    # Check if we can actually read a frame
                    ret, _ = self.video.read()
                    if ret:
                        print(f"[CAMERA] SUCCESS! Connected to Camera {idx} using {b_name}")
                        # Force 720p resolution for accurate focal length calibration
                        self.video.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                        self.video.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                        return True
                    else:
                         print(f"[CAMERA] Opened {idx} but failed to read frame.")
                         self.video.release()
        
        print("[CAMERA] CRITICAL: Could not open any camera.")
        return False
