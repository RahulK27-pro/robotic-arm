"""
YOLO Object Detector Module
Handles object detection using YOLOv8 model
"""

import cv2
import numpy as np
import os
from ultralytics import YOLO
from coordinate_mapper import CoordinateMapper


class YOLODetector:
    def __init__(self, model_name='yolov8n.pt', confidence_threshold=0.5):
        """
        Initialize YOLO detector.
        
        Args:
            model_name: YOLO model to use (default: yolov8n.pt - nano/fastest)
            confidence_threshold: Minimum confidence score for detections (0.0-1.0)
        """
        # Resolve absolute path for model if it's a local file
        if not os.path.isabs(model_name):
            local_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), model_name)
            if os.path.exists(local_path):
                print(f"[YOLO] Found local model file: {local_path}")
                model_name = local_path
        
        print(f"[YOLO] Loading model: {model_name}")
        self.model = YOLO(model_name)
        self.confidence_threshold = confidence_threshold
        self.mapper = None
        print(f"[YOLO] Model loaded successfully! Confidence threshold: {confidence_threshold}")
    
    def detect_objects(self, frame):
        """
        Detect objects in a frame using YOLO.
        
        Args:
            frame: OpenCV image frame (BGR format)
            
        Returns:
            List of detections, each containing:
            - object_name: Class name of detected object
            - confidence: Detection confidence (0.0-1.0)
            - bbox: Bounding box [x1, y1, x2, y2]
            - center: Center point [cx, cy] in pixels
            - cm_coords: Center point [cm_x, cm_y] in real-world cm
        """
        height, width, _ = frame.shape
        
        # Initialize mapper if not already done
        if self.mapper is None:
            self.mapper = CoordinateMapper(width, height)
        
        # Run YOLO inference
        results = self.model(frame, conf=self.confidence_threshold, verbose=False)
        
        detections = []
        
        # Process each detection
        for result in results:
            boxes = result.boxes
            for box in boxes:
                # Get bounding box coordinates
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                
                # Calculate center point
                cx = int((x1 + x2) / 2)
                cy = int((y1 + y2) / 2)
                
                # Get class name and confidence
                class_id = int(box.cls[0])
                confidence = float(box.conf[0])
                object_name = self.model.names[class_id]
                
                # Convert to real-world coordinates (cm)
                cm_x, cm_y = self.mapper.pixel_to_cm(cx, cy)
                
                # Calculate relative position from center
                center_x, center_y = width // 2, height // 2
                dx = cx - center_x
                dy = center_y - cy  # Invert y-axis for robot coordinates
                
                detection = {
                    'object_name': object_name,
                    'confidence': confidence,
                    'bbox': [int(x1), int(y1), int(x2), int(y2)],
                    'center': [cx, cy],
                    'relative_pos': [dx, dy],
                    'cm_x': cm_x,
                    'cm_y': cm_y
                }
                
                detections.append(detection)
        
        return detections
    
    def draw_detections(self, frame, detections):
        """
        Draw bounding boxes and labels on frame.
        
        Args:
            frame: OpenCV image frame
            detections: List of detections from detect_objects()
            
        Returns:
            Annotated frame
        """
        height, width, _ = frame.shape
        center_x, center_y = width // 2, height // 2
        
        for det in detections:
            x1, y1, x2, y2 = det['bbox']
            cx, cy = det['center']
            object_name = det['object_name']
            confidence = det['confidence']
            
            # Draw bounding box
            color = (0, 255, 0)  # Green
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            
            # Draw center point
            cv2.circle(frame, (cx, cy), 5, (0, 0, 255), -1)
            
            # Draw line from image center to object center
            cv2.line(frame, (center_x, center_y), (cx, cy), (255, 0, 0), 1)
            
            # Create label with object name and confidence
            label = f"{object_name}: {confidence:.2f}"
            
            # Add background for text
            (text_width, text_height), _ = cv2.getTextSize(
                label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2
            )
            cv2.rectangle(
                frame, 
                (x1, y1 - text_height - 10), 
                (x1 + text_width, y1), 
                color, 
                -1
            )
            
            # Draw text
            cv2.putText(
                frame, 
                label, 
                (x1, y1 - 5), 
                cv2.FONT_HERSHEY_SIMPLEX, 
                0.5, 
                (0, 0, 0), 
                2
            )
            
            # Add coordinate info below the box
            coord_text = f"({det['cm_x']:.1f}, {det['cm_y']:.1f}) cm"
            cv2.putText(
                frame,
                coord_text,
                (x1, y2 + 15),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.4,
                color,
                1
            )
        
        return frame
