# Phase 3: Vision System Integration

This phase explains how the robotic arm "sees" and identifies objects in its environment.

## Object Detection (YOLOv8)
The system uses Ultralytics **YOLOv8n** (nano) for real-time object detection.
- **Model**: `yolov8n.pt`
- **Implementation**: `yolo_detector.py`
- **Logic**: The detector identifies objects and returns their bounding boxes (`x1, y1, x2, y2`), confidence scores, and class names.

## Camera Calibration
To accurately interact with the world, the camera must be calibrated to understand its focal length.

### Pinhole Camera Model
The distance estimation relies on the pinhole camera formula:
`Distance = (Known Width × Focal Length) / Pixel Width`

### Focal Length Calibration (`calibrate_camera.py`)
1. Place a known object (e.g., a 4cm cube) at a known distance (e.g., 27cm).
2. Measure the object's width in pixels from the YOLO detection.
3. Calculate the focal length: `Focal Length = (Pixel Width × Measured Distance) / Known Object Width`.
4. The calibrated value for this setup is recorded as **1424 pixels** (for the Logitech C270 at 1280x720).

## Distance Estimation (`distance_estimator.py`)
Automatically calculates the depth (Z-axis) of detected objects using:
- **Calibrated Focal Length**: 1424 px.
- **Known Object Database**: A dictionary of real-world widths for common objects (e.g., 'bottle': 4.0cm, 'cup': 8.0cm).
- **Pixel Width**: Extracted from the YOLO bounding box in real-time.

## Pixel-to-Metric Mapping
Beyond just distance (Z), the system maps the object's pixel location (X, Y in the frame) to angular errors for the robotic arm's base and elbow servos.
