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
    # Data format: error_x, distance_cm, correction_angle
    data_path = os.path.join(current_dir, '../tools/servo_training_data.csv')
    
    if not os.path.exists(data_path):
        print(f"Error: Data file not found at {data_path}")
        print("Please run backend/tools/collect_data.py (via usage in servoing loop) to generate data first.")
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

    # Normalize inputs for better training
    # Ideally we should save scaler parameters too, but for now we assume raw values are okay-ish
    # or the network learns the scale. ANFIS handles raw values reasonably well if initialized properly.
    X = data[['error_x', 'distance_cm']].values
    y = data['correction_angle'].values

    # Convert to PyTorch tensors
    X_tensor = torch.tensor(X, dtype=torch.float32)
    y_tensor = torch.tensor(y, dtype=torch.float32).view(-1, 1)

    # 2. Initialize Model
    # Ranges: Error X (-600 to 600), Distance (0 to 120)
    ranges = [(-600, 600), (0, 120)]
    model = ANFIS(n_inputs=2, n_rules=8, input_ranges=ranges) 
    optimizer = optim.Adam(model.parameters(), lr=0.02) # Slightly higher start
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='min', factor=0.5, patience=200, verbose=True)
    criterion = nn.MSELoss()

    # 3. Training Loop
    print("Starting ANFIS Training...")
    epochs = 4000
    for epoch in range(epochs):
        optimizer.zero_grad()
        
        # Forward pass
        outputs = model(X_tensor)
        loss = criterion(outputs, y_tensor)
        
        # Backward pass
        loss.backward()
        optimizer.step()
        
        # Step Scheduler
        scheduler.step(loss)
        
        if epoch % 100 == 0:
            print(f"Epoch {epoch}: Loss = {loss.item():.5f}")

    # 4. Save Model
    save_path = os.path.join(current_dir, 'anfis_model.pth')
    torch.save(model.state_dict(), save_path)
    print(f"Model trained and saved as '{save_path}'")

if __name__ == "__main__":
    train()
