
import torch
import pandas as pd
import numpy as np
import os
import sys

# Add backend to path to import ANFIS
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from brain.anfis_pytorch import ANFIS

# Configuration
DATA_FILE = os.path.join(os.path.dirname(__file__), '../tools/kinematics_data.csv')
MODEL_DIR = os.path.join(os.path.dirname(__file__), 'models')
EPOCHS = 500
LEARNING_RATE = 0.01

def train_model(X, y, name):
    print(f"\n--- Training {name} Model ---")
    
    # 1. Prepare Data
    X_tensor = torch.tensor(X, dtype=torch.float32)
    y_tensor = torch.tensor(y, dtype=torch.float32).reshape(-1, 1)
    
    # 2. Initialize ANFIS
    # Inputs: 2 (Z, Y_pixel)
    # Rules: 16 (4 membership functions per input is a good start, 4^2=16 rules might be heavy, let's try 3 MF per input -> 9 rules)
    # OR standard 8 rules.
    n_inputs = 2
    n_rules = 12
    
    model = ANFIS(n_inputs=n_inputs, n_rules=n_rules)
    optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE)
    criterion = torch.nn.MSELoss()
    
    # 3. Train Loop
    min_loss = float('inf')
    
    for epoch in range(EPOCHS):
        optimizer.zero_grad()
        output = model(X_tensor)
        loss = criterion(output, y_tensor)
        loss.backward()
        optimizer.step()
        
        current_loss = loss.item()
        if current_loss < min_loss:
            min_loss = current_loss
            
        if epoch % 50 == 0:
            print(f"Epoch {epoch}: Loss = {current_loss:.4f}")
            
    print(f"Final Loss ({name}): {min_loss:.4f}")
    
    # 4. Save
    if not os.path.exists(MODEL_DIR):
        os.makedirs(MODEL_DIR)
        
    save_path = os.path.join(MODEL_DIR, f'anfis_{name.lower()}.pth')
    torch.save(model.state_dict(), save_path)
    print(f"Model saved to: {save_path}")

def main():
    if not os.path.exists(DATA_FILE):
        print(f"Error: Data file not found at {DATA_FILE}")
        return

    print(f"Loading data from {DATA_FILE}...")
    df = pd.read_csv(DATA_FILE)
    
    # Filter valid data
    df = df[df['measured_z_cm'] > 0]
    
    # Inputs: Z (cm), Y (pixels)
    # We should Normalize/Scale inputs for better ANFIS performance
    # For now, we'll feed raw and let ANFIS adjust, but scaling is recommended.
    # Let's simple scale: Z / 100, Y / 480 (approx)
    
    # Actually, let's keep it raw. ANFIS parameters will adapt. 
    # But measured_y_px can be large. Large inputs can cause saturation in Gaussian bells.
    # Recommended: Scale to approx range [-1, 1] or [0, 1].
    
    # Feature Scaling
    # Z: 0-100cm -> Scale by 100
    # Y: -300 to +300 px -> Scale by 300
    
    X = df[['measured_z_cm', 'measured_y_px']].values
    
    # Target 1: Shoulder
    y_shoulder = df['shoulder_angle'].values
    train_model(X, y_shoulder, "Shoulder")
    
    # Target 2: Elbow
    y_elbow = df['elbow_angle'].values
    train_model(X, y_elbow, "Elbow")

if __name__ == "__main__":
    main()
