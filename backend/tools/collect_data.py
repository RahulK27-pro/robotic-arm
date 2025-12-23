import csv
import time
import os

class DataCollector:
    def __init__(self, filename="servo_training_data.csv"):
        # Ensure we write to backend/tools/ or relative to execution
        # The user said "backend/tools/collect_data.py", so outputting to same dir or relative
        # I'll use an absolute path construct to be safe or just standard relative
        base_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
        # If running from backend/tools, filename is fine. If running from backend, it might need adjustment.
        # But let's Stick to the requested simpler implementation.
        self.filename = os.path.join(base_dir, filename)
        
        # Initialize CSV with headers if it doesn't exist
        if not os.path.exists(self.filename):
            with open(self.filename, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['error_x', 'distance_cm', 'correction_angle'])

    def log(self, error_x, distance_cm, correction_angle):
        """
        Log a single data point.
        - error_x: Pixels off-center (Input 1)
        - distance_cm: Distance to object (Input 2)
        - correction_angle: The move the robot made (Output)
        """
        try:
            with open(self.filename, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([error_x, distance_cm, correction_angle])
            print(f"[DATA] Logged: Err={error_x:.1f}, Dist={distance_cm:.1f}, Corr={correction_angle:.2f}")
        except Exception as e:
            print(f"[DATA] Error logging: {e}")
