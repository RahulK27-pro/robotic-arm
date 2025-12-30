# Integration Instructions for Visual-Compensation System in app.py

## Changes Needed in visual_servoing.py

The model loading has been updated to use the new `visual_compensation_model.pth` successfully. 

However, you need to manually update the `_hybrid_ml_reach` method call and implementation:

### Step 1: Update the method call (line ~244)

**Change FROM:**
```python
self._hybrid_ml_reach(current_base, det['error_y'], dist_cm, WRIST_PITCH, WRIST_ROLL)
```

**Change TO:**
```python
self._hybrid_ml_reach(current_base, det, WRIST_PITCH, WRIST_ROLL)
```

### Step 2: Update the method signature (line ~295)

**Change FROM:**
```python
def _hybrid_ml_reach(self, aligned_base, pixel_y, depth_cm, pitch, roll):
```

**Change TO:**
```python
def _hybrid_ml_reach(self, aligned_base, detection, pitch, roll):
```

### Step 3: Update the method implementation (around lines 315-325)

**Change FROM:**
```python
# Prepare input for MLP
X_input = np.array([[pixel_y, depth_cm]])
X_scaled = self.reach_scaler.transform(X_input)

# Predict angles
y_pred = self.reach_model.predict(X_scaled)
shoulder_target, elbow_target, base_correction = y_pred[0]
```

**Change TO:**
```python
# Extract visual features from detection
pixel_y = detection['error_y']
depth_cm = detection.get('distance_cm', 25.0)
bbox = detection['bbox']
bbox_width = bbox[2] - bbox[0]  # Calculate bounding box width

# Prepare input for MLP: [pixel_y, depth_cm, bbox_width]
features = np.array([[pixel_y, depth_cm, bbox_width]])
features_normalized = self.scaler_X.transform(features)
features_tensor = torch.FloatTensor(features_normalized)

# Predict angles
with torch.no_grad():
    output_normalized = self.mlp_model(features_tensor).numpy()

# Denormalize
output = self.scaler_y.inverse_transform(output_normalized)
shoulder_target, elbow_target, base_correction = output[0]
```

### Step 4: Update the log message (around line 337)

**Change FROM:**
```python
self.log(f"   Input: [Pixel_Y={pixel_y:.0f}px, Depth={depth_cm:.1f}cm]")
```

**Change TO:**
```python
self.log(f"   Input: [Pixel_Y={pixel_y:.0f}px, Depth={depth_cm:.1f}cm, BBox_Width={bbox_width}px]")
```

## Summary

After these changes, the system will:
1. Load the trained visual-compensation model on startup ✅ (already done)
2. Use ANFIS for X-axis alignment ✅ (already working)
3. Use the 3-input MLP (pixel_y, depth_cm, bbox_width) for Y/Z reach prediction + base correction
4. Execute smooth S-curve motion with base compensation
5. Close gripper and complete the grasp

## Testing

After making these changes, run:
```bash
python backend/app.py
```

Then use the frontend to:
1. Start visual servoing
2. Set target object (e.g., "bottle")
3. Watch the hybrid system in action!
