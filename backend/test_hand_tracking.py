"""
Hand Tracking Test with Visual Servoing Logic
The robot tracks the palm center to keep it centered in frame.
- X/Y: Error-based centering (like visual servoing)
- Z: Depth from pinhole camera theory
- Gripper: Pinch detection
Press 'q' to quit.
"""

import cv2
import mediapipe as mp
import sys
import math
import numpy as np

# Configuration
REAL_PALM_WIDTH = 8.5   # cm (Average palm width)
FOCAL_LENGTH = 1424     # From calibration
CENTER_TOLERANCE = 50   # Pixels within which palm is "centered"
SMOOTHING_ALPHA = 0.15  # Smoothing factor

class SmoothFilter:
    def __init__(self, alpha=0.15):
        self.alpha = alpha
        self.value = None

    def update(self, new_value):
        if self.value is None:
            self.value = new_value
        else:
            self.value = (self.alpha * new_value) + ((1 - self.alpha) * self.value)
        return self.value

# Initialize MediaPipe
print("Initializing MediaPipe Hand Tracking...")
try:
    mp_hands = mp.solutions.hands
    mp_drawing = mp.solutions.drawing_utils
    mp_drawing_styles = mp.solutions.drawing_styles
    print("✓ MediaPipe initialized successfully")
except Exception as e:
    print(f"✗ MediaPipe initialization failed: {e}")
    sys.exit(1)

# Initialize camera
print("\nOpening camera...")
cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("✗ Could not open camera!")
    sys.exit(1)

cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
print(f"✓ Camera opened: {actual_width}x{actual_height}")

# Create MediaPipe Hands detector
print("\nCreating hand detector...")
try:
    hands = mp_hands.Hands(
        min_detection_confidence=0.7,
        min_tracking_confidence=0.7,
        max_num_hands=1
    )
    print("✓ Hand detector created")
except Exception as e:
    print(f"✗ Failed to create detector: {e}")
    cap.release()
    sys.exit(1)

# Create smoothing filters
smooth_error_x = SmoothFilter(SMOOTHING_ALPHA)
smooth_error_y = SmoothFilter(SMOOTHING_ALPHA)
smooth_depth = SmoothFilter(SMOOTHING_ALPHA)

print("\n" + "="*70)
print("HAND TRACKING - VISUAL SERVOING MODE")
print("="*70)
print("Logic:")
print("  ✓ Robot tracks palm center (keeps it centered in frame)")
print("  ✓ Depth calculated from palm size (pinhole camera theory)")
print("  ✓ Gripper controlled by thumb-index pinch")
print("="*70 + "\n")

frame_count = 0
hand_detected_count = 0
centered_count = 0

while True:
    success, frame = cap.read()
    if not success:
        print("✗ Failed to read frame")
        break
    
    frame_count += 1
    
    # Flip frame for mirror effect
    frame = cv2.flip(frame, 1)
    h, w, _ = frame.shape
    frame_center_x = w // 2
    frame_center_y = h // 2
    
    # Draw frame center crosshair
    cv2.line(frame, (frame_center_x - 30, frame_center_y), 
             (frame_center_x + 30, frame_center_y), (0, 255, 255), 2)
    cv2.line(frame, (frame_center_x, frame_center_y - 30), 
             (frame_center_x, frame_center_y + 30), (0, 255, 255), 2)
    cv2.circle(frame, (frame_center_x, frame_center_y), 
              CENTER_TOLERANCE, (0, 255, 255), 2)
    
    # Convert to RGB for MediaPipe
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    
    # Process frame
    results = hands.process(rgb_frame)
    
    # Calculate actions based on hand landmarks
    if results.multi_hand_landmarks:
        hand_detected_count += 1
        for hand_lm in results.multi_hand_landmarks:
            # Draw hand skeleton
            mp_drawing.draw_landmarks(
                frame,
                hand_lm,
                mp_hands.HAND_CONNECTIONS,
                mp_drawing_styles.get_default_hand_landmarks_style(),
                mp_drawing_styles.get_default_hand_connections_style()
            )
            
            # === CALCULATE PALM CENTER ===
            # Average of wrist(0) and middle MCP(9)
            palm_x = ((hand_lm.landmark[0].x + hand_lm.landmark[9].x) / 2) * w
            palm_y = ((hand_lm.landmark[0].y + hand_lm.landmark[9].y) / 2) * h
            
            # Draw palm center
            cv2.circle(frame, (int(palm_x), int(palm_y)), 10, (255, 0, 255), -1)
            cv2.line(frame, (frame_center_x, frame_center_y), 
                    (int(palm_x), int(palm_y)), (255, 0, 255), 2)
            
            # === CENTERING ERROR CALCULATION ===
            # Error_X: How far palm is from center horizontally
            # Error_Y: How far palm is from center vertically
            error_x = frame_center_x - palm_x  # + = palm is LEFT, need to move RIGHT
            error_y = frame_center_y - palm_y  # + = palm is ABOVE, need to move DOWN
            
            # Determine movement directions
            direction_x = "RIGHT" if error_x > 0 else "LEFT" if error_x < 0 else "CENTERED"
            direction_y = "DOWN" if error_y > 0 else "UP" if error_y < 0 else "CENTERED"
            
            # Check if centered
            is_centered = abs(error_x) <= CENTER_TOLERANCE and abs(error_y) <= CENTER_TOLERANCE
            if is_centered:
                centered_count += 1
            
            # Apply smoothing to errors
            s_error_x = smooth_error_x.update(error_x)
            s_error_y = smooth_error_y.update(error_y)
            
            # === DEPTH CALCULATION (Pinhole Camera Theory) ===
            # Index MCP(5) to Pinky MCP(17) distance
            x5 = hand_lm.landmark[5].x * w
            y5 = hand_lm.landmark[5].y * h
            x17 = hand_lm.landmark[17].x * w
            y17 = hand_lm.landmark[17].y * h
            palm_width_px = math.hypot(x17 - x5, y17 - y5)
            
            # Distance calculation
            if palm_width_px > 1:  # Avoid division by zero
                distance_cm = (REAL_PALM_WIDTH * FOCAL_LENGTH) / palm_width_px
            else:
                distance_cm = 999  # Very far
            
            # Map to reach (closer = more reach forward)
            reach_cm = np.interp(distance_cm, [20, 60], [30, 10])
            s_reach = smooth_depth.update(reach_cm)
            
            # === GRIPPER (Thumb-Index Pinch) ===
            thumb_tip_x = hand_lm.landmark[4].x * w
            thumb_tip_y = hand_lm.landmark[4].y * h
            index_tip_x = hand_lm.landmark[8].x * w
            index_tip_y = hand_lm.landmark[8].y * h
            pinch_dist = math.hypot(index_tip_x - thumb_tip_x, index_tip_y - thumb_tip_y)
            
            gripper_state = "CLOSED" if pinch_dist < 40 else "OPEN"
            gripper_angle = 120 if pinch_dist < 40 else 180
            
            # === VISUAL FEEDBACK ON FRAME ===
            # Status
            if is_centered:
                status_text = "✓ CENTERED - Tracking!"
                status_color = (0, 255, 0)
            else:
                status_text = f"Centering... ({abs(int(error_x))}px, {abs(int(error_y))}px)"
                status_color = (0, 165, 255)
            
            cv2.putText(frame, status_text, (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, status_color, 2)
            
            # Centering instructions
            if not is_centered:
                instruction = f"Move {abs(int(s_error_x))}px {direction_x}, {abs(int(s_error_y))}px {direction_y}"
                cv2.putText(frame, instruction, (10, 70),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            
            # Depth & Gripper
            cv2.putText(frame, f"Depth: {s_reach:.1f}cm", (10, h-80),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            
            gripper_color = (0, 255, 255) if gripper_state == "CLOSED" else (255, 255, 255)
            cv2.putText(frame, f"Gripper: {gripper_state}", (10, h-40),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, gripper_color, 2)
            
            # === TERMINAL OUTPUT (every 10 frames) ===
            if frame_count % 10 == 0:
                print("\r" + "="*70)
                print(f"🎯 CENTERING ERROR:")
                print(f"   Error_X:     {s_error_x:7.1f} px  →  Move {direction_x}")
                print(f"   Error_Y:     {s_error_y:7.1f} px  →  Move {direction_y}")
                print(f"   Status:      {'CENTERED ✓' if is_centered else 'ADJUSTING...'}")
                print(f"\n📏 DEPTH (Reach):")
                print(f"   Distance:    {distance_cm:7.1f} cm (from camera)")
                print(f"   Target Reach:{s_reach:7.1f} cm (robot arm extension)")
                print(f"   Palm Width:  {palm_width_px:7.1f} px")
                print(f"\n✋ GRIPPER:")
                print(f"   State:       {gripper_state:7s} ({gripper_angle}°)")
                print(f"   Pinch Dist:  {pinch_dist:7.1f} px")
                print("="*70, end="")
                sys.stdout.flush()
    
    else:
        cv2.putText(frame, "No hand detected", (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        cv2.putText(frame, "Show your palm to camera", (10, 70),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 1)
    
    # Frame info
    cv2.putText(frame, f"Frame: {frame_count}", (w-200, 30),
               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
    
    # Display frame
    cv2.imshow('Hand Tracking - Visual Servoing Mode', frame)
    
    # Check for 'q' key
    if cv2.waitKey(1) & 0xFF == ord('q'):
        print("\n\nQuitting...")
        break

# Cleanup
hands.close()
cap.release()
cv2.destroyAllWindows()

print("\n" + "="*70)
print("TEST RESULTS")
print("="*70)
print(f"Total frames:         {frame_count}")
print(f"Hands detected:       {hand_detected_count}")
print(f"Palm centered:        {centered_count}")
if frame_count > 0:
    print(f"Detection rate:       {(hand_detected_count/frame_count)*100:.1f}%")
if hand_detected_count > 0:
    print(f"Centering accuracy:   {(centered_count/hand_detected_count)*100:.1f}%")
print("="*70)

if hand_detected_count > 0:
    print("\n✓ SUCCESS: Hand tracking with visual servoing logic working!")
    print("\nHow it works:")
    print("  1. Robot continuously adjusts to keep palm centered")
    print("  2. Depth calculated from palm width (pinhole theory)")
    print("  3. Gripper responds to pinch gesture")
    print("\nNext steps:")
    print("  → Integrate into mimic_logic.py with actual robot control")
    print("  → Connect to visual servoing system")
else:
    print("\n⚠ WARNING: No hands detected during test")
