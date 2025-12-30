"""
Visual-Compensation Model Training Script

Trains MLP to predict motor angles and base correction from visual features.
Input: [pixel_y, depth_cm, bbox_width]
Output: [shoulder_angle, elbow_angle, base_correction]
"""

import torch
import torch.nn as nn
import torch.optim as optim
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import MinMaxScaler
import os

# Configuration
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TOOLS_DIR = os.path.join(SCRIPT_DIR, "tools")
DATA_FILE = os.path.join(TOOLS_DIR, "visual_compensation_data.csv")
MODEL_DIR = os.path.join(SCRIPT_DIR, "brain", "models")
MODEL_FILE = os.path.join(MODEL_DIR, "visual_compensation_model.pth")

# Hyperparameters
HIDDEN_SIZE_1 = 16
HIDDEN_SIZE_2 = 8
LEARNING_RATE = 0.001
EPOCHS = 500
BATCH_SIZE = 8
TEST_SPLIT = 0.2

class VisualCompensationMLP(nn.Module):
    """MLP for predicting motor angles and base correction from visual features."""
    
    def __init__(self, input_size=3, output_size=3):
        super(VisualCompensationMLP, self).__init__()
        
        self.network = nn.Sequential(
            nn.Linear(input_size, HIDDEN_SIZE_1),
            nn.ReLU(),
            nn.Linear(HIDDEN_SIZE_1, HIDDEN_SIZE_2),
            nn.ReLU(),
            nn.Linear(HIDDEN_SIZE_2, output_size)
        )
    
    def forward(self, x):
        return self.network(x)


def load_and_preprocess_data():
    """Load CSV and prepare training data."""
    print("=" * 60)
    print("VISUAL-COMPENSATION MODEL TRAINING")
    print("=" * 60)
    
    # Load data
    if not os.path.exists(DATA_FILE):
        raise FileNotFoundError(f"Data file not found: {DATA_FILE}")
    
    df = pd.read_csv(DATA_FILE)
    print(f"\n📊 Loaded {len(df)} samples from {DATA_FILE}")
    print(f"\nColumns: {list(df.columns)}")
    print(f"\nData preview:")
    print(df.head())
    
    # Extract features and targets
    # Features: pixel_y, depth_cm, bbox_width
    # Targets: shoulder_angle, elbow_angle, base_correction
    X = df[['pixel_y', 'depth_cm', 'bbox_width']].values
    y = df[['shoulder_angle', 'elbow_angle', 'base_correction']].values
    
    print(f"\n📐 Feature ranges:")
    print(f"  pixel_y: [{X[:, 0].min():.1f}, {X[:, 0].max():.1f}]")
    print(f"  depth_cm: [{X[:, 1].min():.1f}, {X[:, 1].max():.1f}]")
    print(f"  bbox_width: [{X[:, 2].min():.1f}, {X[:, 2].max():.1f}]")
    
    print(f"\n🎯 Target ranges:")
    print(f"  shoulder_angle: [{y[:, 0].min():.1f}, {y[:, 0].max():.1f}]")
    print(f"  elbow_angle: [{y[:, 1].min():.1f}, {y[:, 1].max():.1f}]")
    print(f"  base_correction: [{y[:, 2].min():.1f}, {y[:, 2].max():.1f}]")
    
    # Normalize features
    scaler_X = MinMaxScaler()
    X_normalized = scaler_X.fit_transform(X)
    
    # Normalize targets for better training (optional, but helps)
    scaler_y = MinMaxScaler()
    y_normalized = scaler_y.fit_transform(y)
    
    # Train-test split
    X_train, X_test, y_train, y_test = train_test_split(
        X_normalized, y_normalized, test_size=TEST_SPLIT, random_state=42
    )
    
    print(f"\n🔀 Split: {len(X_train)} train, {len(X_test)} test")
    
    # Convert to PyTorch tensors
    X_train_tensor = torch.FloatTensor(X_train)
    y_train_tensor = torch.FloatTensor(y_train)
    X_test_tensor = torch.FloatTensor(X_test)
    y_test_tensor = torch.FloatTensor(y_test)
    
    return X_train_tensor, y_train_tensor, X_test_tensor, y_test_tensor, scaler_X, scaler_y


def train_model(X_train, y_train, X_test, y_test):
    """Train the MLP model."""
    model = VisualCompensationMLP(input_size=3, output_size=3)
    criterion = nn.MSELoss()
    optimizer = optim.Adam(model.parameters(), lr=LEARNING_RATE)
    
    train_losses = []
    test_losses = []
    
    print("\n🚀 Starting training...")
    print(f"  Epochs: {EPOCHS}")
    print(f"  Learning Rate: {LEARNING_RATE}")
    print(f"  Architecture: 3 → {HIDDEN_SIZE_1} → {HIDDEN_SIZE_2} → 3")
    
    for epoch in range(EPOCHS):
        # Training
        model.train()
        optimizer.zero_grad()
        outputs = model(X_train)
        loss = criterion(outputs, y_train)
        loss.backward()
        optimizer.step()
        
        train_losses.append(loss.item())
        
        # Validation
        model.eval()
        with torch.no_grad():
            test_outputs = model(X_test)
            test_loss = criterion(test_outputs, y_test)
            test_losses.append(test_loss.item())
        
        # Print progress
        if (epoch + 1) % 50 == 0 or epoch == 0:
            print(f"  Epoch [{epoch+1}/{EPOCHS}] Train Loss: {loss.item():.6f}, Test Loss: {test_loss.item():.6f}")
    
    print(f"\n✅ Training complete!")
    print(f"  Final Train Loss: {train_losses[-1]:.6f}")
    print(f"  Final Test Loss: {test_losses[-1]:.6f}")
    
    return model, train_losses, test_losses


def plot_training_curves(train_losses, test_losses):
    """Plot training and test loss curves."""
    plt.figure(figsize=(10, 6))
    plt.plot(train_losses, label='Train Loss', alpha=0.7)
    plt.plot(test_losses, label='Test Loss', alpha=0.7)
    plt.xlabel('Epoch')
    plt.ylabel('MSE Loss')
    plt.title('Visual-Compensation Model Training')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    
    plot_file = os.path.join(TOOLS_DIR, "training_curve.png")
    plt.savefig(plot_file)
    print(f"\n📈 Training curve saved to: {plot_file}")
    plt.close()


def evaluate_model(model, X_test, y_test, scaler_y):
    """Evaluate model performance with detailed metrics."""
    model.eval()
    
    with torch.no_grad():
        predictions_normalized = model(X_test).numpy()
        targets_normalized = y_test.numpy()
    
    # Denormalize for interpretable metrics
    predictions = scaler_y.inverse_transform(predictions_normalized)
    targets = scaler_y.inverse_transform(targets_normalized)
    
    print("\n📊 Model Performance on Test Set:")
    print("-" * 60)
    
    output_names = ['Shoulder', 'Elbow', 'Base Correction']
    
    for i, name in enumerate(output_names):
        pred = predictions[:, i]
        true = targets[:, i]
        
        mse = np.mean((pred - true) ** 2)
        mae = np.mean(np.abs(pred - true))
        rmse = np.sqrt(mse)
        
        print(f"\n{name}:")
        print(f"  MSE:  {mse:.4f}")
        print(f"  MAE:  {mae:.4f}°")
        print(f"  RMSE: {rmse:.4f}°")
    
    # Sample predictions
    print("\n🎯 Sample Predictions vs Actual:")
    print("-" * 60)
    print(f"{'Predicted':^40} | {'Actual':^40}")
    print(f"{'S':>6} {'E':>6} {'BC':>6} | {'S':>6} {'E':>6} {'BC':>6}")
    print("-" * 60)
    
    for i in range(min(5, len(predictions))):
        pred_s, pred_e, pred_bc = predictions[i]
        true_s, true_e, true_bc = targets[i]
        print(f"{pred_s:6.1f} {pred_e:6.1f} {pred_bc:6.1f} | {true_s:6.1f} {true_e:6.1f} {true_bc:6.1f}")


def save_model(model, scaler_X, scaler_y):
    """Save trained model and scalers."""
    os.makedirs(MODEL_DIR, exist_ok=True)
    
    # Save complete package
    save_dict = {
        'model_state_dict': model.state_dict(),
        'scaler_X': scaler_X,
        'scaler_y': scaler_y,
        'input_size': 3,
        'output_size': 3,
        'hidden_size_1': HIDDEN_SIZE_1,
        'hidden_size_2': HIDDEN_SIZE_2
    }
    
    torch.save(save_dict, MODEL_FILE)
    print(f"\n💾 Model saved to: {MODEL_FILE}")
    print(f"   Includes: model weights, input scaler, output scaler")


def main():
    # Load and preprocess data
    X_train, y_train, X_test, y_test, scaler_X, scaler_y = load_and_preprocess_data()
    
    # Train model
    model, train_losses, test_losses = train_model(X_train, y_train, X_test, y_test)
    
    # Plot training curves
    plot_training_curves(train_losses, test_losses)
    
    # Evaluate model
    evaluate_model(model, X_test, y_test, scaler_y)
    
    # Save model
    save_model(model, scaler_X, scaler_y)
    
    print("\n" + "=" * 60)
    print("✅ TRAINING COMPLETE")
    print("=" * 60)
    print(f"\nNext steps:")
    print(f"  1. Review training curve: {os.path.join(TOOLS_DIR, 'training_curve.png')}")
    print(f"  2. Test runtime inference with: main_visual_compensation.py")


if __name__ == "__main__":
    main()
