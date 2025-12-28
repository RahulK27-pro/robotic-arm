"""
Hybrid 2-Axis Model Training

Trains MLP to map [Pixel_Y, Depth] → [Shoulder, Elbow]
"""

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.neural_network import MLPRegressor
from sklearn.metrics import mean_squared_error, r2_score
import joblib
import matplotlib.pyplot as plt

# Configuration
import os

# Configuration
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(SCRIPT_DIR, "tools", "final_data.csv")
MODEL_OUTPUT = os.path.join(SCRIPT_DIR, "brain", "models", "reach_model.pkl")
SCALER_OUTPUT = os.path.join(SCRIPT_DIR, "brain", "models", "reach_scaler.pkl")
HIDDEN_LAYERS = (50, 50)
MAX_ITER = 2000

def load_data():
    """Load and prepare training data."""
    print(f"📁 Loading data from {DATA_FILE}...")
    df = pd.read_csv(DATA_FILE)
    
    print(f"✅ Loaded {len(df)} samples")
    print(f"\nData Summary:")
    print(df.describe())
    
    # Inputs: [Pixel_Y, Depth]
    X = df[['pixel_y', 'depth_cm']].values
    
    # Outputs: [Shoulder, Elbow]
    # Outputs: [Shoulder, Elbow, Base_Correction]
    y = df[['shoulder', 'elbow', 'base_correction']].values
    
    return X, y

def train_model(X, y):
    """Train MLP model."""
    print("\n🧠 Training MLP Model...")
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    
    print(f"Training samples: {len(X_train)}")
    print(f"Testing samples: {len(X_test)}")
    
    # Normalize inputs
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # Train MLP
    model = MLPRegressor(
        hidden_layer_sizes=HIDDEN_LAYERS,
        activation='relu',
        solver='adam',
        max_iter=MAX_ITER,
        random_state=42,
        verbose=True,
        early_stopping=True,
        validation_fraction=0.1
    )
    
    model.fit(X_train_scaled, y_train)
    
    # Evaluate
    y_pred = model.predict(X_test_scaled)
    mse = mean_squared_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)
    
    print(f"\n📊 Model Performance:")
    print(f"  MSE: {mse:.2f}")
    print(f"  R²: {r2:.4f}")
    
    # Per-output analysis
    # Per-output analysis
    for i, name in enumerate(['Shoulder', 'Elbow', 'BaseCorr']):
        output_mse = mean_squared_error(y_test[:, i], y_pred[:, i])
        output_r2 = r2_score(y_test[:, i], y_pred[:, i])
        print(f"\n  {name}:")
        print(f"    MSE: {output_mse:.2f}°")
        print(f"    R²: {output_r2:.4f}")
    
    # Visualize predictions
    visualize_predictions(y_test, y_pred)
    
    return model, scaler

def visualize_predictions(y_true, y_pred):
    """Plot actual vs predicted angles."""
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    
    for i, name in enumerate(['Shoulder', 'Elbow', 'BaseCorr']):
        axes[i].scatter(y_true[:, i], y_pred[:, i], alpha=0.6)
        axes[i].plot([y_true[:, i].min(), y_true[:, i].max()], 
                     [y_true[:, i].min(), y_true[:, i].max()], 
                     'r--', lw=2, label='Perfect Prediction')
        axes[i].set_xlabel(f'Actual {name} (°)')
        axes[i].set_ylabel(f'Predicted {name} (°)')
        axes[i].set_title(f'{name} Angle Prediction')
        axes[i].legend()
        axes[i].grid(True, alpha=0.3)
    
    plt.tight_layout()
    plot_path = os.path.join(SCRIPT_DIR, "brain", "models", "reach_model_performance.png")
    plt.savefig(plot_path, dpi=150)
    print(f"\n📈 Performance plot saved to {plot_path}")
    plt.show()

def save_model(model, scaler):
    """Save trained model and scaler."""
    joblib.dump(model, MODEL_OUTPUT)
    joblib.dump(scaler, SCALER_OUTPUT)
    print(f"\n💾 Model saved to {MODEL_OUTPUT}")
    print(f"💾 Scaler saved to {SCALER_OUTPUT}")

def main():
    print("=" * 60)
    print("HYBRID 2-AXIS MODEL TRAINING")
    print("=" * 60)
    
    # Load data
    X, y = load_data()
    
    if len(X) < 10:
        print("\n⚠️  WARNING: Very few samples! Collect more data for better performance.")
        response = input("Continue anyway? (y/n): ").strip().lower()
        if response != 'y':
            return
    
    # Train
    model, scaler = train_model(X, y)
    
    # Save
    save_model(model, scaler)
    
    print("\n✅ Training complete!")

if __name__ == "__main__":
    main()
