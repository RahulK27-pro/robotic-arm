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

def train_model(X, y, model_name, n_rules=5):
    print(f"\nTraining {model_name}...")
    
    # Convert to PyTorch tensors
    X_tensor = torch.tensor(X, dtype=torch.float32).view(-1, 1)
    y_tensor = torch.tensor(y, dtype=torch.float32).view(-1, 1)

    # Initialize Model
    # Reach range: ~10 to 45
    # We'll set range slightly wider to be safe
    ranges = [(5, 50)]
    
    model = ANFIS(n_inputs=1, n_rules=n_rules, input_ranges=ranges)
    
    optimizer = optim.Adam(model.parameters(), lr=0.01)
    # Reducing patience to speed up convergence if it gets stuck
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='min', factor=0.5, patience=50)
    criterion = nn.MSELoss()

    # Training Loop
    epochs = 1500 # Sufficient for 1D function approximation
    for epoch in range(epochs):
        optimizer.zero_grad()
        
        outputs = model(X_tensor)
        loss = criterion(outputs, y_tensor)
        
        loss.backward()
        optimizer.step()
        
        scheduler.step(loss)
        
        if epoch % 100 == 0:
            print(f"Epoch {epoch}: Loss = {loss.item():.4f}")

    # Save Model
    save_dir = os.path.join(current_dir, 'models')
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
        
    save_path = os.path.join(save_dir, f'{model_name}.pth')
    torch.save(model.state_dict(), save_path)
    print(f"✅ {model_name} trained and saved as '{save_path}'")

def main():
    # 1. Load Data
    data_path = os.path.join(current_dir, 'reach_anfis_data.csv')
    
    if not os.path.exists(data_path):
        print(f"Error: Data file not found at {data_path}")
        return

    print(f"Loading data from {data_path}...")
    data = pd.read_csv(data_path)
    
    if len(data) == 0:
        print("Error: Dataset is empty.")
        return

    # Check for NaN
    if data.isnull().values.any():
        print("Warning: NaNs found in data, dropping...")
        data = data.dropna()

    X = data['reach_cm'].values
    y_shoulder = data['shoulder_angle'].values
    y_elbow = data['elbow_angle'].values

    # Train Shoulder Model
    train_model(X, y_shoulder, 'anfis_shoulder')
    
    # Train Elbow Model
    train_model(X, y_elbow, 'anfis_elbow')

if __name__ == "__main__":
    main()
