"""
YOLO Object Detection Test Script
Tests YOLOv8 model with webcam feed for object detection
"""

import cv2
from ultralytics import YOLO

def main():
    # Load YOLOv8 model (will download on first run)
    print("Loading YOLOv8 model...")
    model = YOLO('yolov8n.pt')  # 'n' = nano (fastest), alternatives: 's', 'm', 'l', 'x'
    print("Model loaded successfully!")
    
    # Open webcam (0 = default camera, try 1 or 2 for external cameras)
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("Error: Could not open webcam")
        return
    
    print("Starting object detection... Press 'q' to quit")
    
    while True:
        # Read frame from webcam
        ret, frame = cap.read()
        
        if not ret:
            print("Error: Could not read frame")
            break
        
        # Run YOLOv8 inference on the frame
        results = model(frame, conf=0.5)  # conf = confidence threshold
        
        # Visualize the results on the frame
        annotated_frame = results[0].plot()
        
        # Display the annotated frame
        cv2.imshow('YOLOv8 Object Detection', annotated_frame)
        
        # Print detected objects to console
        for result in results:
            boxes = result.boxes
            for box in boxes:
                # Get class name and confidence
                class_id = int(box.cls[0])
                confidence = float(box.conf[0])
                class_name = model.names[class_id]
                
                # Print detection info
                print(f"Detected: {class_name} - Confidence: {confidence:.2f}")
        
        # Break loop on 'q' key press
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    # Release resources
    cap.release()
    cv2.destroyAllWindows()
    print("Test completed!")

if __name__ == "__main__":
    main()
