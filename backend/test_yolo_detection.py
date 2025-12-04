"""
Quick test script to verify YOLO detection is working and persisting in camera module
"""

import time
from camera import VideoCamera

# Create camera with YOLO detection
camera = VideoCamera(detection_mode='yolo')

print("Testing YOLO detection for 10 seconds...")
print("Place objects (cup, mouse, phone, bottle) in front of the camera")
print()

for i in range(20):  # Test for ~10 seconds (20 frames at 0.5s each)
    # Get a frame (this triggers detection)
    frame = camera.get_frame()
    
    # Check last_detection
    print(f"\n[Test {i+1}] Detection count: {len(camera.last_detection)}")
    if camera.last_detection:
        for det in camera.last_detection:
            if 'object_name' in det:
                print(f"  - {det['object_name']}: confidence={det['confidence']:.2f}, pos=({det['cm_x']:.1f}, {det['cm_y']:.1f}) cm")
    else:
        print(" No objects detected")
    
    time.sleep(0.5)

print("\n\nTest complete!")
print(f"Final detection count: {len(camera.last_detection)}")

del camera
