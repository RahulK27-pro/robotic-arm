import torch
import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from anfis_pytorch import ANFIS

def inspect_model(name, path):
    print(f"--- Inspecting {name} ---")
    if not os.path.exists(path):
        print(f"File not found: {path}")
        return

    try:
        state_dict = torch.load(path)
        # Check specific keys to deduce dimensions
        # consequent_weights: (n_rules, n_inputs)
        cw = state_dict.get('consequent_weights')
        if cw is not None:
            n_rules, n_inputs = cw.shape
            print(f"  n_rules: {n_rules}")
            print(f"  n_inputs: {n_inputs}")
        else:
            print("  Could not find consequent_weights")
            print(f"  Keys: {state_dict.keys()}")
            
        # Try to infer input ranges/logic from other keys if possible, but shape is most important.
    except Exception as e:
        print(f"  Error loading: {e}")

base_path = r'd:\Projects\Big Projects\robotic-arm\backend\brain\models'
inspect_model("anfis_shoulder.pth", os.path.join(base_path, "anfis_shoulder.pth"))
inspect_model("anfis_elbow.pth", os.path.join(base_path, "anfis_elbow.pth"))
inspect_model("anfis_center.pth", os.path.join(base_path, "anfis_center.pth"))
