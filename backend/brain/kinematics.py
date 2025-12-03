import math

# Link lengths in cm (Mock values - UPDATE THESE after measuring)
LINK_1 = 10.0  # Base to Shoulder
LINK_2 = 15.0  # Shoulder to Elbow
LINK_3 = 15.0  # Elbow to Wrist
LINK_4 = 5.0   # Wrist to Gripper

def normalize_angle(angle):
    """
    Normalize any angle to 0-180 range for servo compatibility.
    Maps negative angles and angles > 180 to valid servo range.
    """
    # First normalize to -180 to +180
    angle = angle % 360
    if angle > 180:
        angle -= 360
    
    # Map to 0-180 range
    # Negative angles wrap around: -10 becomes 170, -90 becomes 90, etc.
    if angle < 0:
        angle = 180 + angle  # e.g., -30 becomes 150
    
    # Clamp to ensure we're in range (safety)
    return max(0, min(180, angle))

def solve_angles(x, y, z, pitch=0, roll=0):
    """
    Calculates 6-DOF angles for a target (x, y, z) with desired pitch/roll.
    Returns a list of 6 angles [base, shoulder, elbow, wrist_pitch, wrist_roll, gripper].
    """
    angles = [0, 0, 0, 0, 0, 0]

    # 1. Base Angle (Theta 1)
    # Simple atan2 of y and x
    # atan2 returns -180 to +180, normalize to 0-180
    angles[0] = normalize_angle(math.degrees(math.atan2(y, x)))

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
    wrist_pitch_raw = pitch - angles[1] - (angles[2] - 180)
    angles[3] = normalize_angle(wrist_pitch_raw)  # Normalize to 0-180

    # 5. Wrist Roll (Theta 5)
    angles[4] = normalize_angle(roll)  # Normalize to 0-180

    # 6. Gripper (Theta 6)
    # Default open/close state, passed as 0 for now or handled separately
    angles[5] = 0 

    # All angles are now normalized to 0-180 range
    return [round(a, 2) for a in angles]

def compute_forward_kinematics(angles):
    """
    Computes the forward kinematics to get XYZ position from 6 servo angles.
    Takes servo angles [base, shoulder, elbow, wrist_pitch, wrist_roll, gripper]
    Returns (x, y, z) position in mm of the end effector.
    """
    # Extract angles and convert to radians
    theta1 = math.radians(angles[0])  # Base rotation
    theta2 = math.radians(angles[1])  # Shoulder angle
    theta3 = math.radians(angles[2])  # Elbow angle
    theta4 = math.radians(angles[3])  # Wrist pitch
    # angles[4] is wrist roll (doesn't affect XYZ position)
    # angles[5] is gripper (doesn't affect XYZ position)
    
    # Calculate position of each joint in 3D space
    # Starting from base and working up to end effector
    
    # Base height (LINK_1 is vertical from ground to shoulder)
    z1 = LINK_1
    
    # Shoulder to elbow (LINK_2 projects in the plane defined by base rotation)
    # In the arm's plane, LINK_2 is at angle theta2 from horizontal
    r2 = LINK_2 * math.cos(theta2)
    z2 = z1 + LINK_2 * math.sin(theta2)
    
    # Elbow to wrist (LINK_3)
    # The elbow angle theta3 is the internal angle
    # Global angle of forearm = theta2 + (theta3 - 180) if theta3 is internal
    # Simplified: accumulated angle = theta2 + theta3
    forearm_angle = theta2 + theta3 - math.pi  # Assuming theta3=180° is straight
    r3 = r2 + LINK_3 * math.cos(forearm_angle)
    z3 = z2 + LINK_3 * math.sin(forearm_angle)
    
    # Wrist to gripper (LINK_4)
    # Similar calculation with wrist pitch
    # Global pitch = forearm_angle + theta4
    gripper_angle = forearm_angle + theta4
    r_final = r3 + LINK_4 * math.cos(gripper_angle)
    z_final = z3 + LINK_4 * math.sin(gripper_angle)
    
    # Convert from polar to cartesian (r, theta1) -> (x, y)
    x = r_final * math.cos(theta1)
    y = r_final * math.sin(theta1)
    z = z_final
    
    return (round(x, 1), round(y, 1), round(z, 1))
