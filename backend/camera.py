import os
import cv2
import numpy as np
from coordinate_mapper import CoordinateMapper
from yolo_detector import YOLODetector

class VideoCamera(object):
    def __init__(self, detection_mode='yolo', center_tolerance=25):
        """
        Initialize VideoCamera.
        
        Args:
            detection_mode: 'yolo' for object detection or 'color' for color-based detection
            center_tolerance: Pixel tolerance for "centered" alignment (default: 25)
        """
        camera_index = int(os.environ.get("CAMERA_INDEX", 0))
        
        # Try initializing with CAP_DSHOW first (better for Windows)
        print(f"[INFO] Attempting to open camera {camera_index} with CAP_DSHOW...")
        self.video = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
        
        # Fallback to default backend if failed
        if not self.video.isOpened():
            print(f"[WARN] Failed to open camera with CAP_DSHOW. Retrying with default backend...")
            self.video = cv2.VideoCapture(camera_index)
            
        if not self.video.isOpened():
            print(f"[ERROR] Could not open video device {camera_index}.")
            # We don't raise exception here to allow app to start, but status will be inactive
        else:
            print(f"[INFO] Camera {camera_index} opened successfully.")
        
        # Detection mode: 'yolo' or 'color'
        self.detection_mode = detection_mode
        
        # For color detection mode
        self.target_colors = ["Red", "Blue", "Green", "Yellow"] 
        
        # For YOLO detection mode
        self.yolo_detector = None
        if detection_mode == 'yolo':
            self.yolo_detector = YOLODetector(confidence_threshold=0.5)
        
        # Center-seeking state
        self.target_object = None  # Target object name for filtering (e.g., "bottle")
        self.center_tolerance = center_tolerance  # Pixels within which object is "centered"
        
        self.last_detection = [] # Stores list of all detections
        self.mapper = None # Initialize mapper lazily when we have frame dimensions
        
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

    def __del__(self):
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
            self.yolo_detector = YOLODetector(confidence_threshold=0.5)
        
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
        print(f"[INFO] Target object set to: {self.target_object}")
    
    def clear_target_object(self):
        """
        Clear target object filter. Returns to detecting all objects.
        """
        self.target_object = None
        self.last_detection = []
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
        Find objects using YOLO detection.
        Filters to target_object if set, and calculates center alignment errors.
        """
        if self.yolo_detector is None:
            self.yolo_detector = YOLODetector(confidence_threshold=0.5)
        
        # Get frame dimensions
        height, width, _ = frame.shape
        frame_center_x = width // 2
        frame_center_y = height // 2
        
        # Detect objects
        detections = self.yolo_detector.detect_objects(frame)
        
        # Filter by target_object if set
        if self.target_object:
            detections = [d for d in detections if d['object_name'].lower() == self.target_object]
        
        # Update last_detection with YOLO results + center-seeking data
        self.last_detection = []
        for det in detections:
            # Calculate object center from bounding box
            bbox = det['bbox']
            object_center_x = (bbox[0] + bbox[2]) // 2
            object_center_y = (bbox[1] + bbox[3]) // 2
            
            # Calculate alignment error
            error_x = frame_center_x - object_center_x
            error_y = frame_center_y - object_center_y
            
            # Determine movement directions
            # error_x > 0 means object is LEFT of center → move arm RIGHT
            # error_x < 0 means object is RIGHT of center → move arm LEFT
            direction_x = "RIGHT" if error_x > 0 else "LEFT" if error_x < 0 else "CENTERED"
            direction_y = "DOWN" if error_y > 0 else "UP" if error_y < 0 else "CENTERED"
            
            # Check if centered (within tolerance)
            is_centered = abs(error_x) <= self.center_tolerance and abs(error_y) <= self.center_tolerance
            
            self.last_detection.append({
                'object_name': det['object_name'],
                'confidence': det['confidence'],
                'x': det['relative_pos'][0],  # Relative pixel x
                'y': det['relative_pos'][1],  # Relative pixel y
                'cm_x': det['cm_x'],          # Real-world x in cm
                'cm_y': det['cm_y'],          # Real-world y in cm
                'bbox': det['bbox'],          # Bounding box
                # Center-seeking data
                'error_x': error_x,           # Pixels from center (+ = left, - = right)
                'error_y': error_y,           # Pixels from center (+ = above, - = below)
                'direction_x': direction_x,   # Direction to move arm
                'direction_y': direction_y,   # Direction to move arm
                'is_centered': is_centered    # True if within tolerance
            })
        
        # Draw detections on frame (only target object if filter is active)
        frame = self.yolo_detector.draw_detections(frame, detections)
        
        # Add center-seeking visual guides
        if self.target_object and self.last_detection:
            det = self.last_detection[0]  # Use first (closest) detection
            
            # Draw frame center crosshair (larger)
            cv2.line(frame, (frame_center_x - 30, frame_center_y), 
                     (frame_center_x + 30, frame_center_y), (0, 255, 255), 2)
            cv2.line(frame, (frame_center_x, frame_center_y - 30), 
                     (frame_center_x, frame_center_y + 30), (0, 255, 255), 2)
            cv2.circle(frame, (frame_center_x, frame_center_y), 
                      self.center_tolerance, (0, 255, 255), 2)
            
            # Build navigation message
            abs_error_x = abs(det['error_x'])
            abs_error_y = abs(det['error_y'])
            
            # Calculate CM error if mapper is available
            cm_error_x = 0.0
            cm_error_y = 0.0
            if self.yolo_detector and self.yolo_detector.mapper:
                cm_error_x = abs_error_x / self.yolo_detector.mapper.pixels_per_cm_x
                cm_error_y = abs_error_y / self.yolo_detector.mapper.pixels_per_cm_y
            
            # Display CM error in top-left area (moved down to avoid CAM-01 badge)
            cv2.putText(frame, f"X Correction: {cm_error_x:.1f} cm", (30, 120), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            cv2.putText(frame, f"Y Correction: {cm_error_y:.1f} cm", (30, 150), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

            # Determine directions (from robot/camera perspective)
            # error_x > 0: object is left of center → move RIGHT
            # error_x < 0: object is right of center → move LEFT
            direction_x_text = "RIGHT" if det['error_x'] > 0 else "LEFT"
            direction_y_text = "DOWN" if det['error_y'] > 0 else "UP"
            
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

        # Reset detection list
        self.last_detection = []
        
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
                        self.last_detection.append({
                            "color": color_name,
                            "x": dx,      # Relative pixel x (for UI/Center offset)
                            "y": dy,      # Relative pixel y
                            "cm_x": cm_x, # Real-world x in cm
                            "cm_y": cm_y  # Real-world y in cm
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
        
        if self.last_detection:
            count = len(self.last_detection)
            colors_str = ", ".join(self.target_colors)
            print(f"\r[SEARCH] Found {count} object(s) for {colors_str}      ", end="")
        else:
            colors_str = ", ".join(self.target_colors)
            print(f"\r[SEARCH] Searching for {colors_str}...      ", end="")
        
        return frame

    def get_frame(self):
        success, image = self.video.read()
        if not success:
            return None
            
        height, width, _ = image.shape
        cx, cy = width // 2, height // 2
        cv2.line(image, (cx - 20, cy), (cx + 20, cy), (200, 200, 200), 1)
        cv2.line(image, (cx, cy - 20), (cx, cy + 20), (200, 200, 200), 1)
        
        # Use YOLO or color detection based on mode
        if self.detection_mode == 'yolo':
            image = self.find_objects_yolo(image)
            # Add mode indicator
            cv2.putText(image, "Mode: YOLO Detection", (10, 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        elif self.target_colors:
            image = self.find_objects(image)
            cv2.putText(image, "Mode: Color Detection", (10, 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
        else:
            cv2.putText(image, "Mode: Idle (No Target)", (10, 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

        ret, jpeg = cv2.imencode('.jpg', image)
        return jpeg.tobytes()
