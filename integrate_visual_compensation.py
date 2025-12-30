"""
Script to integrate visual-compensation model into visual_servoing.py
"""

import re

# Read the file
with open('backend/visual_servoing.py', 'r', encoding='utf-8') as f:
    content = f.read()

print("Starting integration...")

# Change 1: Update method call (line ~244)
old_call = "self._hybrid_ml_reach(current_base, det['error_y'], dist_cm, WRIST_PITCH, WRIST_ROLL)"
new_call = "self._hybrid_ml_reach(current_base, det, WRIST_PITCH, WRIST_ROLL)"

if old_call in content:
    content = content.replace(old_call, new_call)
    print("✅ Change 1: Updated method call")
else:
    print("⚠️  Change 1: Pattern not found - may already be updated")

# Change 2: Update method signature (line ~295)
old_sig = "def _hybrid_ml_reach(self, aligned_base, pixel_y, depth_cm, pitch, roll):"
new_sig = "def _hybrid_ml_reach(self, aligned_base, detection, pitch, roll):"

if old_sig in content:
    content = content.replace(old_sig, new_sig)
    print("✅ Change 2: Updated method signature")
else:
    print("⚠️  Change 2: Pattern not found - may already be updated")

# Change 3: Update prediction code
old_prediction = """        # Prepare input for MLP
        X_input = np.array([[pixel_y, depth_cm]])
        X_scaled = self.reach_scaler.transform(X_input)
        
        # Predict angles
        y_pred = self.reach_model.predict(X_scaled)
        shoulder_target, elbow_target, base_correction = y_pred[0]"""

new_prediction = """        # Extract visual features from detection
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
        shoulder_target, elbow_target, base_correction = output[0]"""

if old_prediction in content:
    content = content.replace(old_prediction, new_prediction)
    print("✅ Change 3: Updated prediction code")
else:
    print("⚠️  Change 3: Pattern not found - may already be updated")

# Change 4: Update log message
old_log = '        self.log(f"   Input: [Pixel_Y={pixel_y:.0f}px, Depth={depth_cm:.1f}cm]")'
new_log = '        self.log(f"   Input: [Pixel_Y={pixel_y:.0f}px, Depth={depth_cm:.1f}cm, BBox_Width={bbox_width}px]")'

if old_log in content:
    content = content.replace(old_log, new_log)
    print("✅ Change 4: Updated log message")
else:
    print("⚠️  Change 4: Pattern not found - may already be updated")

# Write the file back
with open('backend/visual_servoing.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("\n✅ Integration complete! File saved.")
print("The visual-compensation system is now integrated into app.py")
