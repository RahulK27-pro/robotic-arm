"""
Camera Calibration Helper

Use this script to calibrate the focal length for accurate distance estimation.

Instructions:
1. Place your 3cm cube at a known distance (e.g., 20cm from camera)
2. Run this script and point camera at the cube
3. Script will detect the cube and calculate focal length
4. Update FOCAL_LENGTH_DEFAULT in distance_estimator.py
"""

import cv2
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from yolo_detector import YOLODetector
from brain.distance_estimator import calibrate_focal_length, get_object_pixel_width


def main():
    print("=" * 60)
    print("CAMERA FOCAL LENGTH CALIBRATION")
    print("=" * 60)
    
    # Get calibration parameters from user
    print("\nSetup Instructions:")
    print("1. Place your 3cm cube at a KNOWN distance from the camera")
    print("2. Measure the distance from the camera lens to the cube")
    print("3. Enter the measured distance below")
    print()
    
    try:
        known_distance = float(input("Enter measured distance (cm): "))
        known_width = float(input("Enter object width (cm) [default: 3.0]: ") or "3.0")
    except ValueError:
        print("❌ Invalid input")
        return 1
    
    print(f"\n📏 Calibration Setup:")
    print(f"   Object width: {known_width}cm")
    print(f"   Distance: {known_distance}cm")
    print(f"\nStarting camera... Press 'c' to capture, 'q' to quit")
    
    # Initialize camera (using external webcam)
    camera_index = int(os.environ.get("CAMERA_INDEX", 1))
    cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
    
    # Force 720p
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    
    actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"   Camera resolution: {actual_width}x{actual_height}")
    
    # Initialize YOLO
    detector = YOLODetector(confidence_threshold=0.4)
    
    focal_length = None
    
    while True:
        ret, frame = cap.read()
        if not ret:
            print("❌ Failed to read frame")
            break
        
        # Detect objects
        detections = detector.detect_objects(frame)
        
        # Draw detections
        frame = detector.draw_detections(frame, detections)
        
        # Find target object
        target_detection = None
        for det in detections:
            if det['object_name'].lower() in ['cube', 'bottle', 'cup']:
                target_detection = det
                break
        
        # Display info
        if target_detection:
            bbox = target_detection['bbox']
            pixel_width = get_object_pixel_width(bbox)
            
            # Draw measurement info
            cv2.putText(frame, f"Object: {target_detection['object_name']}", (30, 60),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.putText(frame, f"Pixel Width: {pixel_width}px", (30, 90),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.putText(frame, f"Press 'c' to calibrate", (30, 120),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        else:
            cv2.putText(frame, "No object detected", (30, 60),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        
        # Show frame
        cv2.imshow('Calibration', frame)
        
        key = cv2.waitKey(1) & 0xFF
        
        if key == ord('q'):
            print("\n❌ Calibration cancelled")
            break
        elif key == ord('c'):
            if target_detection:
                pixel_width = get_object_pixel_width(target_detection['bbox'])
                
                # Calculate focal length
                focal_length = calibrate_focal_length(known_distance, known_width, pixel_width)
                
                print("\n" + "=" * 60)
                print("✅ CALIBRATION COMPLETE!")
                print("=" * 60)
                print(f"\nCalculated Focal Length: {focal_length:.2f} pixels")
                print(f"\nUpdate distance_estimator.py:")
                print(f"   FOCAL_LENGTH_DEFAULT = {int(focal_length)}")
                print("\nOr set in camera.py:")
                print(f"   self.focal_length = {int(focal_length)}")
                print("=" * 60)
                break
            else:
                print("⚠️ No object detected. Please position object in view.")
    
    cap.release()
    cv2.destroyAllWindows()
    
    return 0 if focal_length else 1


if __name__ == "__main__":
    sys.exit(main())
