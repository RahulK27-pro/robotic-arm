# ANFIS Controller Workflow Guide

This guide explains how to transition your robotic arm from a simple P-Controller to the advanced **ANFIS (Adaptive Network-based Fuzzy Inference System)** controller.

## Overview of the Process

1.  **Phase 1: Bootstrapping (Data Collection)**
    *   Since the Neural Network is "brain-dead" initially, we need to teach it.
    *   We run the robot using the *old* P-Controller.
    *   The system automatically logs "Correction vs Error/Distance" into a CSV file.
    *   **Goal:** Collect ~500-1000 data points of successful movements.

2.  **Phase 2: Training**
    *   We run a Python script to train the ANFIS model on this CSV data.
    *   The script saves a brain file: `anfis_model.pth`.

3.  **Phase 3: Deployment**
    *   Restart the backend.
    *   The system detects `anfis_model.pth` and automatically switches to the ANFIS brain.

---

## Step-by-Step Instructions

### Step 1: Clean Start (Delete old models)
If you have an old `backend/brain/anfis_model.pth`, **delete it**.
*   *Why?* If the file exists, the robot will try to use it. If it's missing, the robot defaults to P-Control and enables **Data Collection Mode**.

### Step 2: Run the Robot (Gather Data)
1.  Start your backend:
    ```bash
    cd backend
    python app.py
    ```
    *You should see a message: `[ANFIS] 📝 Data Collection ENABLED`*

2.  Open the frontend and start the "Object Tracking" or "Visual Servoing" mode.
3.  Place an object in front of the camera.
    *   Move the object around to different distances (close: 10cm, far: 30cm) and different X-positions (left, right).
    *   Let the robot center on it. Every time the robot moves to correct the error, it logs a data point.
4.  Do this for about 2-3 minutes.
    *   **Tip:** Try to get edge cases! Check very close ranges and verify the robot doesn't oscillate.

5.  Stop the backend (Ctrl+C).

### Step 3: Verify Data
Check `backend/tools/servo_training_data.csv`. It should have hundreds of lines like:
```csv
error_x,distance_cm,correction_angle
-50.0, 25.0, -0.5
120.0, 15.0, 2.1
...
```

### Step 4: Train the Brain
Run the training script:
```bash
cd backend/brain
python train_anfis.py
```
*   You will see the Loss decrease (e.g., from 10.0 to 0.05).
*   It will save `anfis_model.pth`.

### Step 5: Run with ANFIS
Start the backend again:
```bash
cd backend
python app.py
```
*   You should now see: `[ANFIS] Model loaded successfully`.
*   The robot is now navigating using the Neural Network!

---

## Troubleshooting

*   **Robot is oscillating?**
    *   Your training data might have included oscillations. Delete the CSV and the `.pth` file, and collect data again. Only record *smooth* movements if possible (tweak the P-controller gains if needed before collecting).
*   **Model not found?**
    *   Ensure you ran `train_anfis.py` and the file sits in `backend/brain/`.
