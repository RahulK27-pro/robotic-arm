import csv
import os
import math
import sys

# Ensure we can import from local directory
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from kinematics import solve_angles, compute_forward_kinematics

def generate_data():
    """
    Generates synthetic data for Reach ANFIS training.
    We iterate through a range of reach distances (Y-axis primarily, as X is 0).
    We use solve_angles to get the "correct" shoulder and elbow angles.
    """
    output_path = os.path.join(current_dir, 'reach_anfis_data.csv')
    
    print("Generating synthetic reach data...")
    
    # Define range of motion for reach
    # Min reach: ~15cm (very close)
    # Max reach: ~45cm (full extension)
    # We'll generate data in 0.5cm increments
    
    min_dist = 10.0
    max_dist = 45.0
    step = 0.5
    
    # Target height (Z) - let's assume a standard height for "reaching out"
    # Usually around base height or slightly higher.
    # Let's say z = 10 cm (approx gripper height at rest)
    target_z = 10.0 
    
    data = []
    
    dist = min_dist
    while dist <= max_dist:
        try:
            # We want to reach FORWARD (y-axis positive, x=0)
            # x=0, y=dist, z=target_z
            # pitch=0 (gripper horizontal)
            
            # Note: solve_angles takes (x, y, z, pitch, roll)
            angles = solve_angles(0, dist, target_z, pitch=0, roll=0)
            
            # Angles: [base, shoulder, elbow, wrist_pitch, wrist_roll, gripper]
            shoulder = angles[1]
            elbow = angles[2]
            
            # Validate angles are reasonable (not NaN)
            if not math.isnan(shoulder) and not math.isnan(elbow):
                data.append({
                    'reach_cm': round(dist, 2),
                    'shoulder_angle': round(shoulder, 2),
                    'elbow_angle': round(elbow, 2)
                })
                
        except ValueError:
            # Out of reach
            pass
        except Exception as e:
            print(f"Error at dist={dist}: {e}")
            
        dist += step
        
    # Write to CSV
    if data:
        with open(output_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['reach_cm', 'shoulder_angle', 'elbow_angle'])
            writer.writeheader()
            writer.writerows(data)
        print(f"✅ Generated {len(data)} data points. Saved to {output_path}")
    else:
        print("❌ Failed to generate any valid data points.")

if __name__ == "__main__":
    generate_data()
