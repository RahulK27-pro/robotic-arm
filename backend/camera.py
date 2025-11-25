import cv2
import numpy as np

class VideoCamera(object):
    def __init__(self):
        self.video = cv2.VideoCapture(0)
        self.target_color = None 
        self.last_detection = None # Stores {"color": name, "x": x, "y": y}
        
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
    
    def set_target_color(self, color_name):
        if color_name in self.color_ranges or color_name is None:
            self.target_color = color_name
            self.last_detection = None # Reset detection on new target
            print(f"[INFO] Target color set to: {self.target_color}")
        else:
            print(f"[WARN] Unknown color: {color_name}")

    def find_object(self, frame, color_name):
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        height, width, _ = frame.shape
        center_x, center_y = width // 2, height // 2
        
        mask = np.zeros((height, width), dtype=np.uint8)
        ranges = self.color_ranges.get(color_name)
        
        if ranges:
            for (lower, upper) in ranges:
                mask += cv2.inRange(hsv, lower, upper)
        
        mask = cv2.erode(mask, None, iterations=2)
        mask = cv2.dilate(mask, None, iterations=2)
        
        contours, _ = cv2.findContours(mask.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if contours:
            c = max(contours, key=cv2.contourArea)
            if cv2.contourArea(c) > 500:
                ((x, y), radius) = cv2.minEnclosingCircle(c)
                M = cv2.moments(c)
                if M["m00"] > 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])
                    
                    dx = cx - center_x
                    dy = center_y - cy 
                    
                    # Update last detection
                    self.last_detection = {
                        "color": color_name,
                        "x": dx,
                        "y": dy
                    }
                    
                    cv2.circle(frame, (int(x), int(y)), int(radius), (0, 255, 0), 2)
                    cv2.circle(frame, (cx, cy), 5, (0, 0, 255), -1)
                    cv2.line(frame, (center_x, center_y), (cx, cy), (255, 0, 0), 1)
                    
                    text = f"{color_name}: ({dx}, {dy})"
                    cv2.putText(frame, text, (cx - 20, cy - 20), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                    
                    print(f"\r[SEARCH] Found {color_name} at (x={dx}, y={dy})      ", end="")
                    return frame

        print(f"\r[SEARCH] Searching for {color_name}...      ", end="")
        return frame

    def get_frame(self):
        success, image = self.video.read()
        if not success:
            return None
            
        height, width, _ = image.shape
        cx, cy = width // 2, height // 2
        cv2.line(image, (cx - 20, cy), (cx + 20, cy), (200, 200, 200), 1)
        cv2.line(image, (cx, cy - 20), (cx, cy + 20), (200, 200, 200), 1)
        
        if self.target_color:
            image = self.find_object(image, self.target_color)
        else:
            cv2.putText(image, "Mode: Idle (No Target)", (10, 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

        ret, jpeg = cv2.imencode('.jpg', image)
        return jpeg.tobytes()
