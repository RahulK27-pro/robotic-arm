# ANFIS Neural Controller V2: Technical Implementation Guide

This document details the **V2 implementation** of the Adaptive Network-based Fuzzy Inference System (ANFIS) for the 3-DOF robotic arm. This system replaces the traditional PID controller with a neuro-fuzzy brain capable of learning non-linear control strategies.

---

## 1. System Architecture

The controller uses a **5-Layer Neuro-Fuzzy Network** implemented in PyTorch.

### 🧠 The Brain (`backend/brain/anfis_pytorch.py`)
-   **Inputs**:
    1.  **Error X** (Pixels): Horizontal offset from center (Range: -600 to +600).
    2.  **Distance** (cm): Depth/Reach estimate (Range: 0 to 120cm).
-   **Output**:
    1.  **Correction Angle** (Degrees): Adjustment for the Base Servo (Range: -1.0 to +1.0).
-   **Rules**: 8 Fuzzy Rules (Gaussian Membership Functions).

### 🚀 Key V2 Improvements
1.  **Zero Initialization**:
    *   *Problem*: Random initialization caused the untrained model to output random noise (e.g., ±50°), causing violent jerks.
    *   *Fix*: The consequent bias weights are now initialized to `torch.zeros`. The model starts by outputting **0.0** (safe) and learns the correct magnitude from data.
2.  **Input Range scaling**:
    *   Membership functions are spread evenly across the actual sensor range `[-600, 600]` instead of the default unit range.
3.  **Scheduler**:
    *   Training now uses `ReduceLROnPlateau` to fine-tune the loss.
    *   **Final Loss Achieved**: ~0.012 MSE (High Precision).

---

## 2. Integration & Usage

The ANFIS brain drives two distinct modes of the robot:

### A. Visual Servoing (Object Tracking)
*   **File**: `backend/visual_servoing.py`
*   **Logic**:
    1.  **Stage 1 (Alignment)**: The robot centers the object using the ANFIS brain.
    2.  **Stabilization Delay**: A **0.5s** "Stop-and-Wait" delay was added after every move. This eliminates motion blur, ensuring the AI never acts on "stale" or blurry data.
    3.  **Stage 2 (Stalking)**: Once aligned, the robot moves forward while maintaining ANFIS-guided centering.

### B. Mimic Mode (Hand Tracking)
*   **File**: `backend/features/mimic_logic.py`
*   **Logic**:
    *   Replaces the legacy P-Controller for the **Base Servo**.
    *   Uses the *same* trained model to map `(Hand_Error, Hand_Reach)` -> `Base_Rotation`.
    *   **Benefit**: Smoother, more organic hand following that adapts to distance (faster movement when hand is close, precise when far).

---

## 3. Training Workflow

To retrain the brain (e.g., after physical modifications):

1.  **Reset**:
    ```powershell
    # Windows Powershell
    Remove-Item "backend/tools/servo_training_data.csv"
    Remove-Item "backend/brain/anfis_model.pth"
    ```
2.  **Collect Data**:
    *   Run `python app.py`.
    *   The system detects the missing model and enters **Data Collection Mode** (using P-Control fallback).
    *   Operate the robot in "Visual Servoing" mode for ~5 minutes.
    *   Aim for ~500-1000 data points.
3.  **Train**:
    ```bash
    python backend/brain/train_anfis.py
    ```
    *   *Expected Result*: Loss starts at 1.0 and drops to <0.02.
4.  **Deploy**:
    *   Restart `app.py`. The system will auto-detect `anfis_model.pth` and switch to Neural Mode.

---

## 4. Troubleshooting

| Issue | Cause | Solution |
| :--- | :--- | :--- |
| **"Serial connection closed"** | Port conflict caused by zombie process. | Close all terminals/VS Code instances and restart. |
| **Loss remains at 1.0** | Model not learning (vanishing gradient). | Delete `.pth`, ensure data has variety (left AND right moves), retrain. |
| **Robot oscillates** | Latency loop. | The "Stop-and-Wait" delay (0.5s) usually fixes this. |

