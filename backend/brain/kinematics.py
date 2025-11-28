import math

# Link lengths in cm (Mock values - UPDATE THESE after measuring)
LINK_1 = 10.0  # Base to Shoulder
LINK_2 = 15.0  # Shoulder to Elbow
LINK_3 = 15.0  # Elbow to Wrist
LINK_4 = 5.0   # Wrist to Gripper

def solve_angles(x, y, z, pitch=0, roll=0):
    """
    Calculates 6-DOF angles for a target (x, y, z) with desired pitch/roll.
    Returns a list of 6 angles [base, shoulder, elbow, wrist_pitch, wrist_roll, gripper].
    """
    angles = [0, 0, 0, 0, 0, 0]

    # 1. Base Angle (Theta 1)
    # Simple atan2 of y and x
    angles[0] = math.degrees(math.atan2(y, x))

    # 2. Wrist Position Calculation
    # We need to back off from the target (x,y,z) by the gripper length (LINK_4)
    # to find the wrist center position.
    # Assuming pitch is relative to the horizon.
    
    # Convert pitch to radians
    pitch_rad = math.radians(pitch)
    
    # Calculate wrist center (xc, yc, zc)
    # Project LINK_4 onto the XY plane
    r_gripper = LINK_4 * math.cos(pitch_rad)
    z_gripper = LINK_4 * math.sin(pitch_rad)
    
    # Direction of the arm in XY plane
    theta1_rad = math.radians(angles[0])
    
    xc = x - r_gripper * math.cos(theta1_rad)
    yc = y - r_gripper * math.sin(theta1_rad)
    zc = z - z_gripper

    # 3. Inverse Kinematics for 2-link planar arm (Shoulder & Elbow)
    # We are now working in the plane defined by the base angle.
    # r is the distance from the base axis (z-axis) to the wrist center projected on XY
    r = math.sqrt(xc**2 + yc**2)
    
    # z_eff is the height of wrist center relative to the shoulder pivot
    z_eff = zc - LINK_1
    
    # Distance from shoulder pivot to wrist center
    D = math.sqrt(r**2 + z_eff**2)
    
    # Check if target is reachable
    if D > (LINK_2 + LINK_3):
        raise ValueError("Target out of reach")
        
    # Law of Cosines to find angles
    # Angle at Elbow (internal)
    cos_theta3 = (LINK_2**2 + LINK_3**2 - D**2) / (2 * LINK_2 * LINK_3)
    # Clamp value for stability
    cos_theta3 = max(-1.0, min(1.0, cos_theta3))
    theta3_rad = math.acos(cos_theta3)
    
    # Angle at Shoulder (relative to horizon)
    # alpha is angle of the line D to the horizon
    alpha = math.atan2(z_eff, r)
    # beta is angle between line D and LINK_2
    cos_beta = (LINK_2**2 + D**2 - LINK_3**2) / (2 * LINK_2 * D)
    cos_beta = max(-1.0, min(1.0, cos_beta))
    beta = math.acos(cos_beta)
    
    theta2_rad = alpha + beta
    
    # Convert to degrees
    # Note: Servo orientation might need adjustment (e.g., 90 - angle) depending on hardware
    angles[1] = math.degrees(theta2_rad)
    # Elbow angle usually defined relative to upper arm. 
    # If 0 is straight, then we want (180 - internal_angle).
    # If 90 is straight, etc. Let's return the internal angle logic for now.
    # Standard: 0 is fully folded back, 180 is fully extended? 
    # Let's assume standard IK output: 
    # Theta 2 is angle from ground.
    # Theta 3 is angle relative to LINK_2 line.
    # But usually servos take absolute positions.
    # Let's just output the calculated geometric angles for now.
    angles[2] = math.degrees(theta3_rad) # This is the internal angle. 

    # 4. Wrist Pitch (Theta 4)
    # Global pitch = Theta2 - Theta3 + Theta4 (depending on sign conventions)
    # Let's assume: Pitch = Theta2 + Theta3_relative + Theta4_relative
    # We want the end effector to be at `pitch`.
    # So Theta4 = pitch - (angle of forearm)
    # Angle of forearm (relative to ground) = Theta2 - (180 - Theta3_internal) ... this gets complex with signs.
    # Simplified: 
    # Forearm angle global = Theta2 - Theta3 (if Theta3 is angle down from straight line)
    # Let's stick to a simple sum for now, can be tuned.
    # For a simple 3-link chain in 2D:
    # Global Pitch = Theta2 + Theta3 + Theta4
    # So Theta4 = Global Pitch - Theta2 - Theta3
    angles[3] = pitch - angles[1] - (angles[2] - 180) # Adjusting for the internal angle nature

    # 5. Wrist Roll (Theta 5)
    angles[4] = roll

    # 6. Gripper (Theta 6)
    # Default open/close state, passed as 0 for now or handled separately
    angles[5] = 0 

    # Normalize angles to 0-180 range if possible, or keep as is
    return [round(a, 2) for a in angles]
