import cv2
import time

class HybridTracker:
    """
    Hybrid Tracker: Combines YOLO detection with CSRT Tracking.
    
    Logic:
    1. Runs YOLO detection first.
    2. If YOLO detects an object -> RESET tracker to that object (Ground Truth).
    3. If YOLO fails (Blind Spot/Blur) -> FALLBACK to CSRT Tracker.
    
    This ensures we have "AI Intelligence" when available, but "Temporal Persistence"
    during close-range approaches or momentary occlusions.
    """
    def __init__(self):
        # Tracker CSRT is robust to scale changes and rotation suitable for robot arm approach
        self.tracker = cv2.TrackerCSRT_create()
        self.tracking_active = False
        self.last_bbox = None # (x, y, w, h)
        
    def _clamp_bbox(self, bbox, img_shape):
        """
        Ensures bounding box stays within image dimensions.
        bbox: (x, y, w, h)
        img_shape: (height, width, ch)
        """
        h_img, w_img = img_shape[:2]
        x, y, w, h = bbox
        
        # Clamp Top-Left
        x = max(0, min(x, w_img - 1))
        y = max(0, min(y, h_img - 1))
        
        # Clamp Width/Height
        w = max(1, min(w, w_img - x))
        h = max(1, min(h, h_img - y))
        
        return (int(x), int(y), int(w), int(h))

    def get_target(self, frame, model, target_class=None):
        """
        Main pipeline method.
        
        Args:
            frame: Current video frame (cv2 image).
            model: Loaded YOLO model (Ultralytics).
            target_class: (Optional) Specific class name to filter for (e.g., 'bottle').
            
        Returns:
            dict: {
                'center': (cx, cy),
                'bbox': (x, y, w, h),
                'source': 'YOLO' | 'TRACKER' | 'NONE'
            }
        """
        height, width = frame.shape[:2]
        
        # --- 1. YOLO DETECTION ---
        # Run inference with low confidence threshold to catch partials if possible,
        # but the request implies we expect it to fail at close range.
        results = model(frame, verbose=False, conf=0.3) 
        
        best_det = None
        max_conf = 0.0
        
        # Parse detections
        for r in results:
            boxes = r.boxes
            for box in boxes:
                # Class Filtering
                cls_id = int(box.cls[0])
                cls_name = model.names[cls_id]
                
                if target_class and cls_name.lower() != target_class.lower():
                    continue
                
                # Format: [x1, y1, x2, y2]
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                conf = float(box.conf[0])
                
                # Pick best confidence
                if conf > max_conf:
                    max_conf = conf
                    w = x2 - x1
                    h = y2 - y1
                    best_det = (x1, y1, w, h)

        # --- 2. HANDOVER LOGIC ---
        
        # CASE A: YOLO FOUND OBJECT -> Re-initialize Tracker
        if best_det:
            # Standardize
            bbox = self._clamp_bbox(best_det, frame.shape)
            x, y, w, h = bbox
            cx = x + w // 2
            cy = y + h // 2
            
            # Reset Tracker with new ground truth
            self.tracker = cv2.TrackerCSRT_create()
            self.tracker.init(frame, bbox)
            self.tracking_active = True
            self.last_bbox = bbox
            
            return {
                'center': (cx, cy),
                'bbox': bbox,
                'source': 'YOLO'
            }
            
        # CASE B: YOLO FAILED -> Try Tracker (Blind Spot handling)
        elif self.tracking_active:
            success, bbox = self.tracker.update(frame)
            
            if success:
                bbox = self._clamp_bbox(bbox, frame.shape)
                x, y, w, h = bbox
                cx = x + w // 2
                cy = y + h // 2
                self.last_bbox = bbox
                
                return {
                    'center': (cx, cy),
                    'bbox': bbox,
                    'source': 'TRACKER'
                }
            else:
                self.tracking_active = False # Tracker lost it too
                
        # CASE C: NOTHING FOUND
        return {
            'center': None,
            'bbox': None,
            'source': 'NONE'
        }
