import math

# Arm Specifications for X/Y Phase
BASE_HEIGHT = 10.0  # L0: Base to Shoulder Pivot (Approx)
UPPER_ARM = 15.0    # L1: Shoulder to Elbow (User Specified)
FOREARM = 13.0      # L2: Elbow to End Effector (User Specified - treats Wrist as EE for now)

def solve_ik(x, y, z):
    """
    Inverse Kinematics for a 3-DOF Arm (Base, Shoulder, Elbow).
    
    Args:
        x, y, z: Target coordinates in cm.
    
    Returns:
        [base_angle, shoulder_angle, elbow_angle, wrist_pitch, wrist_roll, gripper]
        Returns None if target is out of reach.
    """
    # 1. Base Angle (Azimuth)
    # atan2(y, x) gives angle in radians from X-axis
    # Robot definition: 0 degrees might be X-axis, or 90 might be X-axis.
    # Standard servo: 90 is usually center (Forward).
    # If Forward is +Y, then atan2(y, x) for x=0, y=10 is 90 deg. Correct.
    base_angle = math.degrees(math.atan2(y, x))
    if base_angle < 0:
        base_angle += 360 # Normalize negative angles
        
    # 2. Geometric Planar IK (Shoulder & Elbow)
    # Project target onto the plane of the arm
    # r is distance from base axis to target on ground
    r = math.sqrt(x**2 + y**2)
    
    # Height relative to shoulder pivot
    z_prime = z - BASE_HEIGHT
    
    # Distance from shoulder pivot to target
    D = math.sqrt(r**2 + z_prime**2)
    
    # Check Reachability
    if D > (UPPER_ARM + FOREARM) or D == 0:
        return None
        
    # Law of Cosines for Elbow Angle (Internal Angle Gamma)
    # D^2 = L1^2 + L2^2 - 2*L1*L2*cos(gamma)
    # cos(gamma) = (L1^2 + L2^2 - D^2) / (2*L1*L2)
    cos_elbow = (UPPER_ARM**2 + FOREARM**2 - D**2) / (2 * UPPER_ARM * FOREARM)
    # Clamp for floating point errors
    cos_elbow = max(-1.0, min(1.0, cos_elbow))
    elbow_internal = math.degrees(math.acos(cos_elbow))
    
    # Elbow Servo Angle usually needs mapping
    # If 180 is straight arm, Servo = 180 - internal? 
    # Or if 0 is folded back. Let's assume standard: 
    # Servo 0 = Folded, 180 = Straight. 
    # So Servo Angle = internal angle? 
    # Wait, existing code used `theta3_rad = math.acos(...)`.
    # Let's return the geometric angle and tuning can happen in driver if needed.
    elbow_angle = elbow_internal
    
    # Shoulder Angle (Alpha + Beta)
    # Alpha = Angle of D line from horizon
    alpha = math.degrees(math.atan2(z_prime, r))
    
    # Beta = Angle between L1 and D
    # L2^2 = L1^2 + D^2 - 2*L1*D*cos(beta)
    cos_beta = (UPPER_ARM**2 + D**2 - FOREARM**2) / (2 * UPPER_ARM * D)
    cos_beta = max(-1.0, min(1.0, cos_beta))
    beta = math.degrees(math.acos(cos_beta))
    
    shoulder_angle = alpha + beta
    
    # Default Wrist/Gripper for this phase
    wrist_pitch = 90
    wrist_roll = 90
    gripper = 0
    
    # Clamp and Round
    angles = [base_angle, shoulder_angle, elbow_angle, wrist_pitch, wrist_roll, gripper]
    clean_angles = []
    for a in angles:
        val = max(0, min(180, round(a, 2)))
        clean_angles.append(val)
        
    return clean_angles
