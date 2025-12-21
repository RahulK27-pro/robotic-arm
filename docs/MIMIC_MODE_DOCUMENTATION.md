# Mimic Mode - Hand Teleoperation System

## Overview

Mimic Mode is a hand teleoperation system that allows users to control the robotic arm using hand gestures tracked by a webcam. The system uses **visual servoing** principles to continuously track the user's palm center and **pinhole camera theory** to estimate depth from hand size.

## Table of Contents

1. [Architecture](#architecture)
2. [Core Components](#core-components)
3. [Control Logic](#control-logic)
4. [API Endpoints](#api-endpoints)
5. [Frontend Components](#frontend-components)
6. [Data Flow](#data-flow)
7. [Configuration](#configuration)

---

## Architecture

```
┌─────────────────┐
│  User's Hand    │
└────────┬────────┘
         │ Camera captures
         ▼
┌─────────────────┐
│  MediaPipe      │ ◄─── Hand landmark detection (21 points)
│  Hand Tracking  │
└────────┬────────┘
         │ Landmarks
         ▼
┌─────────────────┐
│ MimicController │ ◄─── Calculate errors & depth
│  (Backend)      │
└────────┬────────┘
         │ Commands
         ▼
┌─────────────────┐
│  Robot Driver   │ ◄─── Execute movements
└─────────────────┘

         Parallel:
         
┌─────────────────┐
│  Video Feed     │ ◄─── Overlay hand skeleton
│  Generator      │
└────────┬────────┘
         │ MJPEG Stream
         ▼
┌─────────────────┐
│  Frontend UI    │ ◄─── Display + Telemetry
└─────────────────┘
```

---

## Core Components

### 1. **MimicController** (`backend/features/mimic_logic.py`)

The main controller that handles hand tracking and robot control.

#### **Initialization**

```python
def __init__(self, robot_driver, camera=None)
```

**Purpose:** Initialize the mimic controller with robot driver and camera instances.

**Key Attributes:**
- `robot`: Reference to robot driver for sending commands
- `camera`: Reference to global camera for frame access
- `active`: Boolean flag indicating if mimic mode is running
- `smooth_error_x/y`: Smoothing filters for centering errors
- `smooth_depth`: Smoothing filter for depth/reach
- `telemetry`: Dictionary storing current state for API access
- `hand_landmarks`: Current hand landmark data (thread-safe)

#### **Main Control Loop**

```python
def start(self)
```

**Purpose:** Main control loop that runs in a separate thread.

**Process:**
1. **Initialize MediaPipe** (lazy-loaded to avoid import issues)
2. **Capture frames** from global camera
3. **Detect hand landmarks** using MediaPipe
4. **Calculate control values:**
   - Palm center position
   - Centering errors (Error_X, Error_Y)
   - Depth estimation (pinhole theory)
   - Gripper state (pinch detection)
5. **Apply smoothing** to all values
6. **Update telemetry** for frontend
7. **Send commands** to robot (currently prints to terminal)

**Threading:** Runs in daemon thread to prevent blocking Flask server.

#### **Helper Methods**

```python
def get_hand_landmarks(self)
```
- **Purpose:** Thread-safe getter for hand landmarks
- **Returns:** Tuple of (landmarks, palm_center, is_centered)
- **Used by:** Video feed overlay system

```python
def get_telemetry(self)
```
- **Purpose:** Thread-safe getter for telemetry data
- **Returns:** Dictionary with error_x, error_y, reach, gripper, is_centered
- **Used by:** `/mimic_telemetry` API endpoint

```python
def draw_hand_overlay(self, frame)
```
- **Purpose:** Draw visual indicators on video frame
- **Draws:**
  - Yellow crosshair (frame center)
  - Yellow tolerance circle
  - Green hand skeleton (MediaPipe)
  - Purple palm center dot
  - Purple error line
  - Status text (CENTERED or error values)

```python
def stop(self)
```
- **Purpose:** Gracefully stop the control loop
- **Sets:** `active = False` to exit loop

---

### 2. **SmoothFilter** (`backend/features/mimic_logic.py`)

Exponential Moving Average filter for smooth control.

```python
class SmoothFilter:
    def __init__(self, alpha=0.15)
    def update(self, new_value)
```

**Purpose:** Reduce jitter in hand tracking by smoothing values over time.

**Formula:** `smoothed = (α × new_value) + ((1 - α) × previous_value)`

**Alpha Values:**
- `0.15`: Heavy smoothing (slower response, less jitter)
- `0.5`: Light smoothing (faster response, more jitter)

**Applied to:**
- `error_x`: Horizontal centering error
- `error_y`: Vertical centering error
- `reach`: Depth/distance value

---

## Control Logic

### Visual Servoing (Centering)

**Goal:** Keep the palm center aligned with frame center.

#### **Palm Center Calculation**

```python
cx = (hand_lm.landmark[0].x + hand_lm.landmark[9].x) / 2  # Wrist + Middle MCP
cy = (hand_lm.landmark[0].y + hand_lm.landmark[9].y) / 2
```

**Landmarks Used:**
- `0`: Wrist
- `9`: Middle finger MCP (knuckle)

#### **Centering Error Calculation**

```python
error_x = frame_center_x - palm_x  # Positive = palm is LEFT
error_y = frame_center_y - palm_y  # Positive = palm is ABOVE
```

**Interpretation:**
- `error_x > 0`: Palm is **left** of center → Move robot **RIGHT**
- `error_x < 0`: Palm is **right** of center → Move robot **LEFT**
- `error_y > 0`: Palm is **above** center → Move robot **DOWN**
- `error_y < 0`: Palm is **below** center → Move robot **UP**

#### **Centered Detection**

```python
is_centered = abs(error_x) <= 50 and abs(error_y) <= 50
```

**Tolerance:** 50 pixels in both X and Y directions.

---

### Depth Estimation (Pinhole Camera Theory)

**Goal:** Estimate hand distance from camera to control arm reach.

#### **Palm Width Measurement**

```python
x5 = hand_lm.landmark[5].x * w   # Index finger MCP
y5 = hand_lm.landmark[5].y * h
x17 = hand_lm.landmark[17].x * w  # Pinky MCP
y17 = hand_lm.landmark[17].y * h
palm_width_px = math.hypot(x17 - x5, y17 - y5)
```

**Landmarks Used:**
- `5`: Index finger MCP
- `17`: Pinky finger MCP

#### **Distance Calculation**

```python
distance_cm = (REAL_PALM_WIDTH × FOCAL_LENGTH) / palm_width_px
```

**Constants:**
- `REAL_PALM_WIDTH`: 8.5 cm (average palm width)
- `FOCAL_LENGTH`: 1424 pixels (calibrated for camera)

**Formula Derivation:**
```
Similar triangles:
real_width / distance = pixel_width / focal_length

Solving for distance:
distance = (real_width × focal_length) / pixel_width
```

#### **Reach Mapping**

```python
reach_cm = np.interp(distance_cm, [20, 60], [10, 30])
```

**Mapping:**
- Hand at **20cm** from camera → Reach = **10cm** (retracted)
- Hand at **60cm** from camera → Reach = **30cm** (extended)

**Logic:** Closer hand = smaller reach, farther hand = larger reach.

---

### Gripper Control (Pinch Detection)

**Goal:** Detect thumb-index pinch gesture to control gripper.

#### **Pinch Distance Calculation**

```python
thumb_x = hand_lm.landmark[4].x * w  # Thumb tip
thumb_y = hand_lm.landmark[4].y * h
index_x = hand_lm.landmark[8].x * w  # Index tip
index_y = hand_lm.landmark[8].y * h
pinch_dist = math.hypot(index_x - thumb_x, index_y - thumb_y)
```

**Landmarks Used:**
- `4`: Thumb tip
- `8`: Index finger tip

#### **Gripper State**

```python
gripper = 120° if pinch_dist < 40px else 180°
```

**States:**
- `pinch_dist < 40px`: **CLOSED** (120°)
- `pinch_dist >= 40px`: **OPEN** (180°)

---

## API Endpoints

### **POST `/mimic_start`**

**Purpose:** Start mimic mode hand tracking.

**Actions:**
1. Pauses YOLO detection (`global_camera.pause_yolo = True`)
2. Creates new daemon thread
3. Starts `mimic_ctrl.start()` in background
4. Prints debug info to terminal

**Response:**
```json
{
  "status": "started",
  "message": "Mimic Mode Active"
}
```

---

### **POST `/mimic_stop`**

**Purpose:** Stop mimic mode hand tracking.

**Actions:**
1. Calls `mimic_ctrl.stop()`
2. Resumes YOLO detection (`global_camera.pause_yolo = False`)

**Response:**
```json
{
  "status": "stopped",
  "message": "Mimic Mode Stopping..."
}
```

---

### **GET `/mimic_telemetry`**

**Purpose:** Get current hand tracking state.

**Response:**
```json
{
  "error_x": 45.2,      // Horizontal offset (pixels)
  "error_y": -12.8,     // Vertical offset (pixels)
  "reach": 18.5,        // Target reach (cm)
  "gripper": "OPEN",    // "OPEN" or "CLOSED"
  "is_centered": false, // Boolean
  "active": true        // Is mimic mode running
}
```

**Update Rate:** Polled by frontend at 100ms intervals (10 Hz).

---

### **GET `/mimic_video_feed`**

**Purpose:** MJPEG stream with hand tracking overlay.

**Process:**
1. Get **raw frame** from camera (no YOLO)
2. Add "Mode: HAND TRACKING" text
3. If mimic active, call `draw_hand_overlay()`
4. Encode to JPEG
5. Yield as MJPEG stream

**Content-Type:** `multipart/x-mixed-replace; boundary=frame`

---

## Frontend Components

### **MimicPage.tsx**

Main page component for mimic mode interface.

#### **State Management**

```typescript
const [active, setActive] = useState(false);        // Mode active/inactive
const [loading, setLoading] = useState(false);      // Button loading state
const [telemetry, setTelemetry] = useState({...});  // Live telemetry data
```

#### **Telemetry Polling**

```typescript
useEffect(() => {
  if (!active) return;
  const interval = setInterval(async () => {
    const res = await fetch('http://localhost:5000/mimic_telemetry');
    const data = await res.json();
    setTelemetry(data);
  }, 100); // 10 Hz
  return () => clearInterval(interval);
}, [active]);
```

**Logic:** Only polls when mimic mode is active, cleans up on stop.

#### **UI Components**

**1. Camera Feed Card**
- Video element with `/mimic_video_feed` source
- Shows hand tracking overlay
- Overlay message when inactive

**2. Telemetry Display**
- Grid layout (2x4 on mobile, 4 columns on desktop)
- **X Offset**: Green when within tolerance, orange otherwise
- **Y Offset**: Green when within tolerance, orange otherwise
- **Reach**: Blue color, shows distance in cm
- **Gripper**: 🤏 (closed) or ✋ (open), yellow when closed

**3. Control Panel**
- Status indicator
- Large ACTIVATE/STOP button
- Visual feedback when active

**4. Instructions Card**
- Position: Explains centering logic
- Reach: Explains depth control
- Gripper: Explains pinch gesture

---

## Data Flow

### **Startup Sequence**

```
1. User opens Mimic Page
   └─> Frontend loads MimicPage.tsx

2. User clicks "ACTIVATE"
   └─> POST /mimic_start
       ├─> Pause YOLO detection
       ├─> Start mimic thread
       └─> Return success

3. Mimic thread starts
   └─> Initialize MediaPipe
       └─> Enter control loop
```

### **Control Loop (30 Hz)**

```
Every ~33ms:

1. Get raw frame from camera
   └─> camera.get_raw_frame()

2. Process with MediaPipe
   └─> Detect 21 hand landmarks

3. Calculate values
   ├─> Palm center (landmarks 0, 9)
   ├─> Errors (center - palm)
   ├─> Depth (pinhole theory)
   └─> Gripper (pinch detection)

4. Apply smoothing
   └─> Exponential moving average

5. Update telemetry
   └─> Thread-safe dictionary update

6. Print to terminal
   └─> Status line with current values

7. (Future) Send to robot
   └─> Visual servoing commands
```

### **Video Feed (30 FPS)**

```
Every ~33ms:

1. Get raw frame
   └─> Skip YOLO (paused)

2. Add hand overlay (if active)
   ├─> Draw crosshair
   ├─> Draw hand skeleton
   ├─> Draw palm center
   ├─> Draw error line
   └─> Add status text

3. Encode to JPEG
   └─> Yield to MJPEG stream

4. Frontend displays
   └─> <img> element shows stream
```

### **Telemetry Updates (10 Hz)**

```
Every 100ms (when active):

1. Frontend polls /mimic_telemetry
   └─> GET request

2. Backend returns latest values
   └─> Thread-safe telemetry copy

3. Frontend updates state
   └─> setTelemetry(data)

4. React re-renders
   └─> Telemetry grid updates
```

---

## Configuration

### **Constants** (`mimic_logic.py`)

```python
REAL_PALM_WIDTH = 8.5    # cm - Average palm width
FOCAL_LENGTH = 1424      # pixels - Calibrated for camera
CENTER_TOLERANCE = 50    # pixels - Centering threshold
SMOOTHING_ALPHA = 0.15   # 0-1 - Smoothing factor
```

### **MediaPipe Settings**

```python
mp_hands.Hands(
    min_detection_confidence=0.7,  # Detection threshold
    min_tracking_confidence=0.7,   # Tracking threshold
    max_num_hands=1                # Track only one hand
)
```

### **Mapping Ranges**

```python
# Depth to Reach
distance_cm: [20, 60]  → reach_cm: [10, 30]

# Pinch to Gripper
pinch_dist < 40px → CLOSED (120°)
pinch_dist >= 40px → OPEN (180°)
```

---

## Testing

### **Standalone Test** (`test_hand_tracking.py`)

**Purpose:** Test hand tracking without Flask integration.

**Features:**
- Opens camera in separate window
- Shows real-time hand skeleton
- Displays centering errors and reach
- Prints telemetry to terminal
- Press 'q' to quit

**Usage:**
```bash
cd backend
python test_hand_tracking.py
```

**Output:**
```
🎯 CENTERING ERROR:
   Error_X:     -45.2 px  →  Move LEFT
   Error_Y:      23.8 px  →  Move UP
   Status:      ADJUSTING...

📏 DEPTH (Reach):
   Distance:      38.5 cm (from camera)
   Target Reach:  15.3 cm (robot arm extension)
   Palm Width:   142.7 px

✋ GRIPPER:
   State:        OPEN (180°)
   Pinch Dist:    67.3 px
```

---

## Dependencies

### **Backend**

```
mediapipe==0.10.9      # Hand tracking
protobuf==3.20.3       # MediaPipe compatibility
opencv-python          # Camera and image processing
numpy                  # Mathematical operations
flask                  # Web server
flask-cors             # CORS support
```

### **Frontend**

```
react                  # UI framework
typescript             # Type safety
lucide-react           # Icons
@/components/ui        # Shadcn components
```

---

## Future Enhancements

### **1. Robot Integration**

Currently, the system only prints commands to terminal. Future version will:
- Convert centering errors to robot movements
- Use visual servoing controller
- Send actual servo commands

### **2. Calibration**

- User-adjustable centering tolerance
- Per-user palm width calibration
- Camera focal length calibration wizard

### **3. Advanced Features**

- Two-hand control for more DOF
- Gesture library (thumbs up, peace sign, etc.)
- Recording and playback of mimic sequences
- Adjustable sensitivity sliders

### **4. Performance**

- GPU acceleration for MediaPipe
- Optimized frame processing
- Reduced latency (<50ms)

---

## Troubleshooting

### **Backend crashes on start**

**Symptom:** `AttributeError: module 'mediapipe' has no attribute 'solutions'`

**Solution:**
```bash
pip uninstall mediapipe -y
pip install mediapipe==0.10.9
pip install protobuf==3.20.3
```

### **YOLO interferes with terminal**

**Symptom:** Both YOLO and mimic messages appear

**Solution:** YOLO is automatically paused when mimic starts. Check that `global_camera.pause_yolo` is being set correctly.

### **Hand not detected**

**Symptoms:**
- No green skeleton appears
- "No hand detected" message

**Solutions:**
- Ensure good lighting
- Show palm clearly to camera
- Keep hand within frame
- Check MediaPipe confidence thresholds

### **Jittery movements**

**Symptom:** Values jump around rapidly

**Solution:** Increase `SMOOTHING_ALPHA` (up to 0.3 for heavier smoothing).

### **Reach backwards**

**Symptom:** Moving closer increases reach

**Solution:** Check reach mapping in `mimic_logic.py`:
```python
reach_cm = np.interp(distance_cm, [20, 60], [10, 30])  # Correct
# NOT: [30, 10]  # Reversed
```

---

## Summary

Mimic Mode transforms your webcam into a robot controller using:
- **MediaPipe** for precise hand tracking (21 landmarks)
- **Visual Servoing** to continuously center the palm
- **Pinhole Camera Theory** for depth estimation
- **Exponential Smoothing** for stable control
- **Real-time Telemetry** for visual feedback

The system is designed to be intuitive, responsive, and extensible for future robot control applications.
