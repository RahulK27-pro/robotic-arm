import torch
import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from anfis_pytorch import ANFIS

def try_load(path, inputs):
    try:
        model = ANFIS(n_inputs=inputs, n_rules=100) # Rules don't match, but we check if keys match size
        # Actually state_dict load checks shapes.
        # But we don't know n_rules either.
        # So we load state_dict and check the shape of 'consequent_weights'
        sd = torch.load(path)
        cw = sd['consequent_weights']
        # cw shape is (n_rules, n_inputs)
        print(f"File: {os.path.basename(path)} -> Rule/Input Shape: {cw.shape}")
        return cw.shape[1]
    except Exception as e:
        print(f"Error checking {os.path.basename(path)}: {e}")
        return -1

base = r'd:\Projects\Big Projects\robotic-arm\backend\brain\models'
files = ['anfis_shoulder.pth', 'anfis_elbow.pth', 'anfis_center.pth']

print("--- DIMENSION CHECK ---")
for f in files:
    try_load(os.path.join(base, f), 0)
