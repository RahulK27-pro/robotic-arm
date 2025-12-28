import cv2
import time
from ultralytics import YOLO
from camera_stream import ThreadedCamera
from hybrid_tracker import HybridTracker

def main():
    print("🚀 Starting Vision Controller...")
    
    # 1. Initialize Threaded Camera
    # Use src=1 for external camera (or 0 for default)
    # The user logs implied they use an external cam (Logitech often 1) or 0? 
    # Let's try 0 default, but easy to change.
    camera = ThreadedCamera(src=1) 
    
    # 2. Initialize Hybrid Tracker
    tracker = HybridTracker()
    
    # 3. Load YOLO Model
    print("🧠 Loading YOLO Model...")
    # Using 'yolov8s-world.pt' as requested or 'yolov8n.pt' if faster needed.
    # Assuming 'yolov8s-world.pt' is available or will auto-download.
    try:
        model = YOLO('yolov8s-world.pt') 
    except:
        print("⚠️ Could not load yolov8s-world.pt, falling back to yolov8n.pt")
        model = YOLO('yolov8n.pt')
        
    # Optional: Set specific classes for World model if needed
    # if "world" in model.names: model.set_classes(["bottle", "cup"])
    
    print("✅ System Ready. Press 'q' to exit.")
    
    prev_time = 0
    target_object = "bottle" # Default target for testing
    
    try:
        while True:
            # A. Get Frame (Non-blocking)
            frame = camera.read()
            
            if frame is None:
                # Camera might be reconnecting or initializing
                time.sleep(0.1)
                continue
                
            # B. Get Target (Hybrid Logic)
            result = tracker.get_target(frame, model, target_class=target_object)
            
            bbox = result['bbox']
            center = result['center']
            source = result['source']
            
            # C. Visualization
            if bbox:
                x, y, w, h = bbox
                
                # Color Coding: Green for AI (YOLO), Blue for Algo (Tracker)
                color = (0, 255, 0) if source == 'YOLO' else (255, 0, 0)
                
                # Draw Box
                cv2.rectangle(frame, (x, y), (x+w, y+h), color, 2)
                
                # Draw Center
                cv2.circle(frame, center, 5, (0, 0, 255), -1)
                
                # Label
                label = f"{source}: {target_object} ({w}x{h})"
                cv2.putText(frame, label, (x, y - 10), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                
                # Coordinates
                coord_text = f"X:{center[0]} Y:{center[1]}"
                cv2.putText(frame, coord_text, (10, frame.shape[0] - 20),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            else:
                cv2.putText(frame, "SEARCHING...", (50, 50),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

            # D. FPS Calculation
            curr_time = time.time()
            fps = 1 / (curr_time - prev_time) if prev_time > 0 else 0
            prev_time = curr_time
            
            cv2.putText(frame, f"FPS: {fps:.1f}", (frame.shape[1] - 120, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            
            # E. Display
            cv2.imshow("Robust Hybrid Vision", frame)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
    except KeyboardInterrupt:
        print("\n🛑 Interrupted by user.")
        
    finally:
        camera.stop()
        cv2.destroyAllWindows()
        print("👋 Vision System Shutdown.")

if __name__ == "__main__":
    main()
