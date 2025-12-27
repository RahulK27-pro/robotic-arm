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
    data_path = os.path.join(current_dir, '../tools/servo_training_data.csv')
    
    if not os.path.exists(data_path):
        print(f"Error: Data file not found at {data_path}")
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

    # UPDATED: We now have 'axis' column.
    # User might want to train ONE generic model for "Error -> Correction" regardless of axis,
    # OR train separate models.
    # "Brain 1" typically refers to the Centering logic.
    # Since X (Base) and Y (Elbow) behavior might differ, mixing them might be noisy.
    # However, if we just want "Reduce Error", a single model might suffice if normalized.
    # Let's filter for 'x' by default to match original plan, OR train both?
    # User said: "I want equal data for both x and y axis correction"
    # This implies they care about Y. 
    # Let's train a model that takes (Error) -> Correction.
    # If we mix X and Y data, the model learns the average response.
    # Let's try training on ALL data (ignoring axis column for input) to see if one brain can rule them all.
    # This is often robust enough for visual servoing.
    
    # Check if 'axis' column exists (support backward compatibility)
    if 'axis' not in data.columns:
        print("Warning: 'axis' column not found. Assuming old 'error_x' format.")
        # Fix column names if needed
        if 'error_x' in data.columns:
            data.rename(columns={'error_x': 'error_px'}, inplace=True)
    else:
        # Standardize error column
        if 'error_px' not in data.columns and 'error_x' in data.columns:
             data.rename(columns={'error_x': 'error_px'}, inplace=True)

    X = data[['error_px']].values
    y = data['correction_angle'].values

    print(f"Training on {len(X)} samples (Combined X and Y axis data)...")

    # Convert to PyTorch tensors
    X_tensor = torch.tensor(X, dtype=torch.float32)
    y_tensor = torch.tensor(y, dtype=torch.float32).view(-1, 1)

    # 2. Initialize Model
    # Brain 1: 1 Input (Error), 5 Rules
    # Range: Error (-600 to 600)
    ranges = [(-600, 600)]
    model = ANFIS(n_inputs=1, n_rules=5, input_ranges=ranges) 
    optimizer = optim.Adam(model.parameters(), lr=0.01)
    criterion = nn.MSELoss()

    # 3. Training Loop
    print("Training ANFIS 1 (Centering Brain)...")
    epochs = 2000
    for epoch in range(epochs):
        optimizer.zero_grad()
        
        # Forward pass
        outputs = model(X_tensor)
        loss = criterion(outputs, y_tensor)
        
        # Backward pass
        loss.backward()
        optimizer.step()
        
        if epoch % 100 == 0:
            print(f"Epoch {epoch}: Loss = {loss.item():.5f}")

    # 4. Save Model as 'anfis_center.pth'
    save_path = os.path.join(current_dir, 'anfis_center.pth')
    torch.save(model.state_dict(), save_path)
    print(f"Centering Model trained and saved as '{save_path}'")

if __name__ == "__main__":
    train()
