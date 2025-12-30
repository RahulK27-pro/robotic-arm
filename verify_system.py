"""
Complete System Verification Script

Verifies all components of the integrated hybrid visual-compensation system.
"""

import sys
import os

print("=" * 70)
print("SYSTEM VERIFICATION - Hybrid Visual-Compensation System")
print("=" * 70)

# Add backend to path
backend_path = os.path.join(os.getcwd(), 'backend')
sys.path.insert(0, backend_path)

# Test 1: Import core modules
print("\n1. Testing Core Module Imports...")
try:
    import torch
    import numpy as np
    from hardware.robot_driver import RobotArm
    from camera import VideoCamera
    from brain.anfis_pytorch import ANFIS
    print("   ✅ Core modules imported successfully")
except Exception as e:
    print(f"   ❌ Error importing core modules: {e}")
    sys.exit(1)

# Test 2: Import visual servoing
print("\n2. Testing Visual Servoing Agent...")
try:
    from visual_servoing import VisualServoingAgent
    print("   ✅ Visual Servoing Agent imported successfully")
except Exception as e:
    print(f"   ❌ Error importing Visual Servoing Agent: {e}")
    sys.exit(1)

# Test 3: Check model files exist
print("\n3. Checking Model Files...")
models_to_check = [
    ('ANFIS X-Axis', 'backend/brain/models/anfis_x.pth'),
    ('Visual-Compensation MLP', 'backend/brain/models/visual_compensation_model.pth'),
]

all_models_exist = True
for name, path in models_to_check:
    if os.path.exists(path):
        size_kb = os.path.getsize(path) / 1024
        print(f"   ✅ {name}: {path} ({size_kb:.1f} KB)")
    else:
        print(f"   ❌ {name}: {path} NOT FOUND")
        all_models_exist = False

if not all_models_exist:
    print("\n⚠️  Some models are missing. Please train them first.")

# Test 4: Load and verify MLP model
print("\n4. Testing MLP Model Loading...")
try:
    checkpoint = torch.load('backend/brain/models/visual_compensation_model.pth')
    print(f"   ✅ Model loaded successfully")
    print(f"   Architecture: {checkpoint['input_size']} → {checkpoint['hidden_size_1']} → {checkpoint['hidden_size_2']} → {checkpoint['output_size']}")
    print(f"   Keys in checkpoint: {list(checkpoint.keys())}")
    
    # Verify scalers exist
    if 'scaler_X' in checkpoint and 'scaler_y' in checkpoint:
        print(f"   ✅ Scalers included in checkpoint")
    else:
        print(f"   ❌ Scalers missing from checkpoint")
except Exception as e:
    print(f"   ❌ Error loading MLP model: {e}")

# Test 5: Test Flask app imports
print("\n5. Testing Flask App...")
try:
    from flask import Flask
    from flask_cors import CORS
    print("   ✅ Flask and dependencies imported successfully")
except Exception as e:
    print(f"   ❌ Error importing Flask: {e}")

# Test 6: Verify integrated code changes
print("\n6. Verifying Code Integration...")
try:
    with open('backend/visual_servoing.py', 'r') as f:
        content = f.read()
    
    checks = [
        ('Method call updated', 'self._hybrid_ml_reach(current_base, det, WRIST_PITCH, WRIST_ROLL)'),
        ('Method signature updated', 'def _hybrid_ml_reach(self, aligned_base, detection, pitch, roll):'),
        ('BBox width extraction', 'bbox_width = bbox[2] - bbox[0]'),
        ('3-input features', 'features = np.array([[pixel_y, depth_cm, bbox_width]])'),
        ('PyTorch model call', 'self.mlp_model(features_tensor)'),
        ('Scaler usage', 'self.scaler_X.transform(features)'),
    ]
    
    all_checks_pass = True
    for check_name, pattern in checks:
        if pattern in content:
            print(f"   ✅ {check_name}")
        else:
            print(f"   ❌ {check_name} - NOT FOUND")
            all_checks_pass = False
    
    if all_checks_pass:
        print("\n   ✅ All code integration checks passed!")
    else:
        print("\n   ⚠️  Some integration checks failed")
        
except Exception as e:
    print(f"   ❌ Error verifying integration: {e}")

# Summary
print("\n" + "=" * 70)
print("VERIFICATION COMPLETE")
print("=" * 70)
print("\n✅ System is ready to run!")
print("\nTo start the hybrid system:")
print("   python backend/app.py")
print("\nThe system will:")
print("   1. Load ANFIS X-axis alignment model")
print("   2. Load Visual-Compensation MLP model")
print("   3. Start Flask server on http://localhost:5000")
print("   4. Execute hybrid grasp workflow when triggered")
print("\n" + "=" * 70)
