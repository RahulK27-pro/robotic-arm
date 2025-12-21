# Pinhole Camera Model & Distance Estimation

## Overview

This document explains how we estimate distance to objects using a **monocular camera** (single camera) without depth sensors like LiDAR. The technique is based on the **pinhole camera model**, a fundamental concept in computer vision.

---

## The Pinhole Camera Model

### What is it?

A pinhole camera is the simplest camera model. Light from an object passes through a tiny hole (aperture) and projects an inverted image on the opposite side.

```
Object          Pinhole         Image Plane
  |                •                |
  |               /|\               |
  |              / | \              |
  |             /  |  \             |
  |            /   |   \            |
  |           /    |    \           |
  |          /     |     \          |
  |         /      |      \         |
  |        /       |       \        |
  |       /        |        \       |
  |------•---------•---------•------|
     D       f          d
```

**Key Components**:
- **Object**: Real-world object at distance `D` from camera
- **Pinhole**: Camera lens/aperture (focal point)
- **Image Plane**: Camera sensor where image is formed
- **Focal Length (f)**: Distance from pinhole to image plane

---

## The Mathematics

### Similar Triangles Principle

The pinhole camera creates **similar triangles**:

```
Real World:  Object Height (H) at Distance (D)
Image Plane: Image Height (h) at Focal Length (f)
```

By the property of similar triangles:

```
H / D = h / f
```

Rearranging to solve for distance:

```
D = (H × f) / h
```

### For Width Instead of Height

We can use the same principle with width:

```
D = (W × f) / w
```

Where:
- `D` = Distance to object (cm)
- `W` = Real-world width of object (cm)
- `f` = Focal length (pixels)
- `w` = Width of object in image (pixels)

---

## Practical Implementation

### Step 1: Know the Object Size

You must know the **real-world dimensions** of the object you're detecting.

**Examples**:
- 3cm cube (test object)
- 6cm bottle diameter
- 8cm cup diameter

### Step 2: Measure Pixel Width

Use YOLO bounding box to get pixel width:

```python
bbox = [x1, y1, x2, y2]  # From YOLO detection
pixel_width = x2 - x1     # Width in pixels
```

### Step 3: Calculate Distance

```python
distance_cm = (known_width_cm × focal_length_px) / pixel_width_px
```

**Example**:
- Object: 3cm cube
- Focal length: 1110 pixels
- Pixel width: 165 pixels

```
Distance = (3 × 1110) / 165 = 20.18 cm
```

---

## Focal Length Calibration

### What is Focal Length?

**Focal length** is the distance from the camera lens to the sensor, measured in **pixels** (not millimeters).

It depends on:
- Camera hardware (lens)
- Image resolution (1280x720 vs 640x480)
- Field of view (FOV)

### Why Calibrate?

The theoretical focal length may not match reality due to:
- Lens distortion
- Manufacturing variations
- Resolution settings

**Result**: Distance estimates can be off by 10-15cm without calibration.

### Calibration Method

**Setup**:
1. Place object at **known distance** (e.g., 20cm)
2. Measure **pixel width** in camera
3. Calculate focal length

**Formula**:
```
f = (w × D) / W
```

**Example**:
- Object width: 3cm
- Actual distance: 20cm
- Measured pixel width: 165px

```
f = (165 × 20) / 3 = 1100 pixels
```

### Theoretical Estimation (Backup)

If you know the camera's **field of view (FOV)**:

```
f = (image_width / 2) / tan(FOV / 2)
```

**Example** (Logitech C270):
- FOV: 60 degrees
- Image width: 1280 pixels

```
f = (1280 / 2) / tan(30°)
f = 640 / 0.577
f ≈ 1108 pixels
```

---

## Accuracy & Limitations

### Accuracy Factors

**Good Accuracy (±2cm)**:
- Correct focal length calibration
- Accurate object dimensions
- Object perpendicular to camera
- Good lighting conditions
- Object fills significant portion of frame

**Poor Accuracy (±10cm+)**:
- Uncalibrated focal length
- Unknown object dimensions
- Object at angle
- Poor lighting
- Object very small in frame

### Distance Range

**Optimal Range**: 15-40cm
- Too close (<10cm): Object too large, may be cut off
- Too far (>50cm): Object too small, pixel width inaccurate

### Limitations

1. **Monocular Ambiguity**: Cannot distinguish between:
   - Small object close to camera
   - Large object far from camera
   - **Solution**: Use known object dimensions

2. **Perspective Distortion**: Objects at angles appear smaller
   - **Solution**: Ensure object faces camera

3. **Lens Distortion**: Wide-angle lenses distort edges
   - **Solution**: Calibrate with object in center

4. **Resolution Dependency**: Lower resolution = less accuracy
   - **Solution**: Use 720p or higher

---

## Implementation in Our System

### Camera Configuration

```python
# Force 720p resolution for accuracy
camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

# Logitech C270 calibrated focal length
FOCAL_LENGTH = 1110  # pixels
```

### Known Object Dimensions

```python
KNOWN_OBJECT_WIDTHS = {
    'cube': 3.0,        # cm
    'bottle': 6.0,      # cm
    'cup': 8.0,         # cm
}
```

### Distance Calculation

```python
def calculate_distance(focal_length, known_width_cm, pixel_width):
    if pixel_width == 0:
        return -1.0
    
    distance_cm = (known_width_cm * focal_length) / pixel_width
    return round(distance_cm, 2)
```

### Integration with YOLO

```python
# 1. YOLO detects object
detections = yolo.detect_objects(frame)

# 2. Get bounding box
bbox = detection['bbox']  # [x1, y1, x2, y2]
pixel_width = bbox[2] - bbox[0]

# 3. Get known width
object_name = detection['object_name']
known_width = KNOWN_OBJECT_WIDTHS.get(object_name)

# 4. Calculate distance
distance = calculate_distance(FOCAL_LENGTH, known_width, pixel_width)
```

---

## Comparison with Other Methods

### Stereo Vision
- **Pros**: More accurate, works with unknown objects
- **Cons**: Requires two cameras, complex calibration
- **Our Choice**: Single camera is simpler and sufficient

### LiDAR/Depth Sensors
- **Pros**: Very accurate, works in any lighting
- **Cons**: Expensive, requires additional hardware
- **Our Choice**: Camera-only solution is cost-effective

### Ultrasonic Sensors
- **Pros**: Cheap, simple
- **Cons**: Limited range, cannot identify objects
- **Our Choice**: Vision provides both detection and distance

---

## Calibration Workflow

### Step-by-Step Process

1. **Prepare Setup**
   ```bash
   cd backend
   python calibrate_camera.py
   ```

2. **Measure Distance**
   - Use ruler to measure exactly 20cm from camera to object
   - Place 3cm cube at this distance

3. **Capture Calibration**
   - Point camera at cube
   - Press 'c' when cube is detected
   - Script calculates focal length

4. **Update System**
   ```python
   # In camera.py or app.py
   global_camera = VideoCamera(
       focal_length_override=1650  # Your calibrated value
   )
   ```

5. **Verify Accuracy**
   - Test at 20cm → Should show ~20cm
   - Test at 30cm → Should show ~30cm
   - Test at 40cm → Should show ~40cm

---

## Real-World Example

### Scenario: Grabbing a Bottle

**Setup**:
- Camera: Logitech C270 (1280x720)
- Object: Water bottle (6cm diameter)
- Focal length: 1110 pixels (calibrated)

**Detection**:
- YOLO detects bottle
- Bounding box: [200, 150, 350, 450]
- Pixel width: 350 - 200 = 150 pixels

**Calculation**:
```
Distance = (6 × 1110) / 150
Distance = 6660 / 150
Distance = 44.4 cm
```

**Result**: Bottle is 44.4cm away

**Action**: 
- Check reachability: 44.4cm > 41cm max reach
- Report: "Object out of reach"

---

## Troubleshooting

### Distance Too Large

**Symptom**: Shows 50cm when object is at 30cm

**Causes**:
- Focal length too high
- Object width incorrect
- Pixel width measurement error

**Fix**:
- Recalibrate focal length
- Verify object dimensions
- Check YOLO bounding box accuracy

### Distance Too Small

**Symptom**: Shows 15cm when object is at 25cm

**Causes**:
- Focal length too low
- Object appears larger (angle/distortion)

**Fix**:
- Recalibrate with object at different distance
- Ensure object is perpendicular to camera

### Inconsistent Readings

**Symptom**: Distance jumps between 20cm and 30cm

**Causes**:
- YOLO bounding box fluctuating
- Object moving
- Poor lighting

**Fix**:
- Increase YOLO confidence threshold
- Stabilize object
- Improve lighting

---

## Mathematical Derivation

### From First Principles

**Given**: Pinhole camera geometry

**Assumptions**:
1. Thin lens approximation
2. Object perpendicular to optical axis
3. No lens distortion

**Derivation**:

By similar triangles:
```
W / D = w / f
```

Multiply both sides by D:
```
W = (w × D) / f
```

Multiply both sides by f:
```
W × f = w × D
```

Divide both sides by w:
```
D = (W × f) / w
```

**Result**: Distance formula

---

## References & Further Reading

### Academic Papers
- "A Flexible New Technique for Camera Calibration" - Zhang (2000)
- "Monocular Distance Estimation" - Saxena et al. (2009)

### Online Resources
- [OpenCV Camera Calibration](https://docs.opencv.org/4.x/dc/dbb/tutorial_py_calibration.html)
- [Pinhole Camera Model](https://en.wikipedia.org/wiki/Pinhole_camera_model)

### Related Concepts
- **Perspective Projection**: How 3D world maps to 2D image
- **Camera Matrix**: Mathematical representation of camera
- **Homogeneous Coordinates**: Used in projective geometry

---

## Summary

**Key Takeaways**:

1. **Pinhole model** allows distance estimation with single camera
2. **Formula**: `D = (W × f) / w`
3. **Calibration** is essential for accuracy (±2cm vs ±10cm)
4. **Known dimensions** required for each object type
5. **Optimal range**: 15-40cm for best accuracy

**Our Implementation**:
- Logitech C270 at 1280x720
- Focal length: 1110 pixels (calibrated)
- Test object: 3cm cube
- Accuracy: ±2cm after calibration

**Practical Use**:
- Real-time distance estimation
- No additional sensors needed
- Integrated with YOLO object detection
- Enables autonomous grabbing
