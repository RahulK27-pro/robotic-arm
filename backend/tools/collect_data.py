import csv
import time
import os

class DataCollector:
    def __init__(self, filename="servo_training_data.csv"):
        # Ensure we write to backend/tools/ or relative to execution
        base_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
        self.filename = os.path.join(base_dir, filename)
        
        # Initialize CSV with headers if it doesn't exist
        # UPDATED: Added 'axis' column (x or y)
        if not os.path.exists(self.filename):
            with open(self.filename, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['error_px', 'distance_cm', 'correction_angle', 'axis'])

    def log(self, error_px, distance_cm, correction_angle, axis='x'):
        """
        Log a single data point.
        - error_px: Pixels off-center (Input 1)
        - distance_cm: Distance to object (Input 2)
        - correction_angle: The move the robot made (Output)
        - axis: 'x' (Base) or 'y' (Elbow)
        """
        try:
            with open(self.filename, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([error_px, distance_cm, correction_angle, axis])
            # print(f"[DATA] Logged ({axis}): Err={error_px:.1f}, Dist={distance_cm:.1f}C, Corr={correction_angle:.2f}")
        except Exception as e:
            print(f"[DATA] Error logging: {e}")
