import cv2
import time
from camera import VideoCamera

def main():
    print("=================================================")
    print("   EYE-IN-HAND ORIENTATION CHECK")
    print("=================================================")
    print("1. Tape the camera to your hand (or hold it).")
    print("2. Point it at a target object (e.g. Red Cube).")
    print("3. Move your hand (the camera) in the directions shown.")
    print("4. Verify if the 'Corrective Action' matches your movement logic.")
    print("   - If screen says 'Move RIGHT' and you move RIGHT -> Correct.")
    print("   - If screen says 'Move RIGHT' and you move LEFT -> INVERT NEEDED.")
    print("=================================================")
    
    # Initialize Camera
    camera = VideoCamera(detection_mode='yolo')
    
    # Set a target (optional, default to whatever YOLO sees, or set a color)
    # camera.set_target_colors(['Red']) # Uncomment for color mode
    
    print("Starting Camera... Press 'q' to quit.")
    
    while True:
        frame = camera.get_frame()
        if frame is None:
            # get_frame returns bytes, we need to decode for local display
            # But camera.video.read() is what we really want for a local script
            ret, frame = camera.video.read()
            if not ret:
                continue
                
            frame = camera.find_objects_yolo(frame)
            
            # Display
            cv2.imshow("Orientation Check", frame)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        else:
            # If get_frame() works (it returns bytes), we can't easily imshow it without decoding.
            # So let's just use the internal logic.
            ret, frame = camera.video.read()
            if ret:
                frame = camera.find_objects_yolo(frame)
                cv2.imshow("Orientation Check", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

    camera.video.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
