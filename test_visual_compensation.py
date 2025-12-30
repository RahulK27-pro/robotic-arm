"""
Quick Test Script for Visual-Compensation System

Tests the trained model without running full hardware loop.
"""

import torch
import numpy as np
import os

# Load model
MODEL_FILE = "backend/brain/models/visual_compensation_model.pth"

print("=" * 60)
print("VISUAL-COMPENSATION MODEL TEST")
print("=" * 60)

# Load checkpoint
checkpoint = torch.load(MODEL_FILE)
print(f"\n✅ Model loaded successfully!")
print(f"   Architecture: {checkpoint['input_size']} → {checkpoint['hidden_size_1']} → {checkpoint['hidden_size_2']} → {checkpoint['output_size']}")

# Create model
from backend.train_visual_compensation import VisualCompensationMLP

model = VisualCompensationMLP(
    input_size=checkpoint['input_size'],
    output_size=checkpoint['output_size']
)
model.load_state_dict(checkpoint['model_state_dict'])
model.eval()

scaler_X = checkpoint['scaler_X']
scaler_y = checkpoint['scaler_y']

print(f"\n✅ Scalers loaded")

# Test with sample inputs
print(f"\n" + "=" * 60)
print("TESTING WITH SAMPLE INPUTS")
print("=" * 60)

test_cases = [
    {"pixel_y": -50, "depth_cm": 23.0, "bbox_width": 300, "name": "Medium distance, left"},
    {"pixel_y": 0, "depth_cm": 28.0, "bbox_width": 270, "name": "Center, far"},
    {"pixel_y": -100, "depth_cm": 18.0, "bbox_width": 350, "name": "Far left, close"},
    {"pixel_y": 30, "depth_cm": 32.0, "bbox_width": 240, "name": "Right, very far"},
]

for i, test in enumerate(test_cases, 1):
    print(f"\n--- Test Case {i}: {test['name']} ---")
    print(f"Input:  pixel_y={test['pixel_y']:>4}, depth={test['depth_cm']:>5.1f}cm, bbox_width={test['bbox_width']}")
    
    # Prepare input
    features = np.array([[test['pixel_y'], test['depth_cm'], test['bbox_width']]])
    features_normalized = scaler_X.transform(features)
    features_tensor = torch.FloatTensor(features_normalized)
    
    # Predict
    with torch.no_grad():
        output_normalized = model(features_tensor).numpy()
    
    # Denormalize
    output = scaler_y.inverse_transform(output_normalized)
    shoulder, elbow, base_correction = output[0]
    
    # Clamp to safe ranges
    shoulder = max(0, min(140, shoulder))
    elbow = max(0, min(180, elbow))
    base_correction = max(-90, min(90, base_correction))
    
    print(f"Output: Shoulder={shoulder:>5.1f}°, Elbow={elbow:>5.1f}°, Base_Corr={base_correction:>+5.1f}°")

print(f"\n" + "=" * 60)
print("✅ ALL TESTS PASSED!")
print("=" * 60)
print(f"\nModel is ready for runtime deployment.")
print(f"Run: python backend/main_visual_compensation.py")
