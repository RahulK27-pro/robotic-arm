import cv2
import numpy as np

class VideoCamera(object):
    def __init__(self):
        self.video = cv2.VideoCapture(0)
        # Default to detecting all colors so the Brain has full context
        self.target_colors = ["Red", "Blue", "Green", "Yellow"] 
        self.last_detection = [] # Stores list of all detections
        
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
    
    def set_target_colors(self, color_names):
        """
        Set target colors to search for.
        color_names: list of color names or None
        """
        if color_names is None:
            self.target_colors = []
        else:
            # Filter to only valid colors
            self.target_colors = [c for c in color_names if c in self.color_ranges]
        
        self.last_detection = [] # Reset detection on new targets
        print(f"[INFO] Target colors set to: {self.target_colors}")

    def find_objects(self, frame):
        """
        Find all objects for all target colors.
        """
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        height, width, _ = frame.shape
        center_x, center_y = width // 2, height // 2
        
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
                        
                        # Add to detection list
                        self.last_detection.append({
                            "color": color_name,
                            "x": dx,
                            "y": dy
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
        
        if self.target_colors:
            image = self.find_objects(image)
        else:
            cv2.putText(image, "Mode: Idle (No Target)", (10, 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

        ret, jpeg = cv2.imencode('.jpg', image)
        return jpeg.tobytes()
