import cv2
import numpy as np

def get_color_name(h, s, v):
    """
    Maps HSV values to a human-readable string.
    """
    # 1. Filter out Greys/Whites/Blacks first
    if s < 30: return "White/Grey"
    if v < 30: return "Black"

    # 2. Map Hues to Colors (OpenCV Hue range is 0-179)
    if h < 10:  return "Red"
    elif h < 25: return "Orange"
    elif h < 35: return "Yellow"
    elif h < 85: return "Green"
    elif h < 130: return "Blue"
    elif h < 145: return "Violet"
    elif h < 170: return "Pink/Magenta"
    else: return "Red" # Wrap around

class VideoCamera(object):
    def __init__(self):
        # Using OpenCV to capture from device 0.
        self.video = cv2.VideoCapture(0)
    
    def __del__(self):
        self.video.release()
    
    def get_frame(self):
        success, image = self.video.read()
        if not success:
            return None
        
        # --- PROCESS FRAME ---
        # Get frame dimensions
        height, width, _ = image.shape
        cx, cy = width // 2, height // 2

        # 1. Get Raw RGB (BGR in OpenCV) for the terminal
        b, g, r = image[cy, cx]
        
        # 2. Convert frame to HSV to understand the "Color Name"
        hsv_frame = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        h, s, v = hsv_frame[cy, cx]

        # 3. Get the text name of the color
        color_name = get_color_name(h, s, v)

        # --- VISUAL FEEDBACK ON SCREEN ---
        
        # Draw the Crosshair
        cv2.line(image, (cx - 20, cy), (cx + 20, cy), (0, 255, 0), 2)
        cv2.line(image, (cx, cy - 20), (cx, cy + 20), (0, 255, 0), 2)

        # Create a dynamic color swatch (a box showing the color the camera sees)
        # We create a small rectangle filled with the detected color
        cv2.rectangle(image, (cx + 30, cy - 30), (cx + 80, cy + 20), (int(b), int(g), int(r)), -1)
        cv2.rectangle(image, (cx + 30, cy - 30), (cx + 80, cy + 20), (255, 255, 255), 2) # White border

        # Display the Color Name and HSV values on screen
        cv2.putText(image, f"Color: {color_name}", (cx - 100, cy - 50), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        cv2.putText(image, f"H:{h} S:{s} V:{v}", (cx - 100, cy + 60), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)

        # --- TERMINAL OUTPUT ---
        # Prints dynamically to the terminal without scrolling
        print(f"\r[DETECTED] Name: {color_name:<12} | RGB: ({r:3},{g:3},{b:3}) | HSV: ({h:3},{s:3},{v:3})", end="")

        ret, jpeg = cv2.imencode('.jpg', image)
        return jpeg.tobytes()
