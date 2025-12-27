import torch
import torch.nn as nn
import torch.optim as optim
import pandas as pd
import numpy as np
import os
import sys

# Ensure we can import from local directory
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from anfis_pytorch import ANFIS

def train():
    # 1. Load Data
    data_path = os.path.join(current_dir, '../tools/x_axis_anfis_data.csv')
    
    if not os.path.exists(data_path):
        print(f"Error: Data file not found at {data_path}")
        print("Please run backend/tools/collect_x_anfis.py first.")
        return

    print(f"Loading data from {data_path}...")
    try:
        data = pd.read_csv(data_path)
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return

    if len(data) == 0:
        print("Error: Dataset is empty.")
        return

    # Input: Error X
    # Target: Correction Needed (Target Angle - Current Angle)
    X = data[['error_x']].values
    y = data['correction_needed'].values

    # Convert to PyTorch tensors
    X_tensor = torch.tensor(X, dtype=torch.float32)
    y_tensor = torch.tensor(y, dtype=torch.float32).view(-1, 1)

    # 2. Initialize Model
    # Range of Error X typically -320 to 320 for VGA, but let's give it some buffer
    ranges = [(-400, 400)]
    
    # 1 Input, 5 Rules (Simpler than full chaos, enough for a curve)
    model = ANFIS(n_inputs=1, n_rules=5, input_ranges=ranges) 
    
    optimizer = optim.Adam(model.parameters(), lr=0.02)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='min', factor=0.5, patience=100)
    criterion = nn.MSELoss()

    # 3. Training Loop
    print("Starting ANFIS Training for X-Axis...")
    epochs = 2000
    for epoch in range(epochs):
        optimizer.zero_grad()
        
        # Forward pass
        outputs = model(X_tensor)
        loss = criterion(outputs, y_tensor)
        
        # Backward pass
        loss.backward()
        optimizer.step()
        
        scheduler.step(loss)
        
        if epoch % 100 == 0:
            print(f"Epoch {epoch}: Loss = {loss.item():.5f}")

    # 4. Save Model
    save_dir = os.path.join(current_dir, 'models')
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
        
    save_path = os.path.join(save_dir, 'anfis_x.pth')
    torch.save(model.state_dict(), save_path)
    print(f"✅ Model trained and saved as '{save_path}'")

if __name__ == "__main__":
    train()
