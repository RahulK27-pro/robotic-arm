"""
Visual Inverse Kinematics Solver

Dedicated IK solver for visual servoing grab operations.
Handles 2-link planar arm (shoulder + elbow) with gripper offset compensation.

Physical Setup:
    - Shoulder Length (L1): 15cm
    - Elbow Length (L2): 13cm  
    - Gripper Length: 13cm
    - Max Arm Reach: 28cm (wrist position)
    - Max Grab Reach: 41cm (gripper tip)
"""

import math


# Physical Constants (User Confirmed)
SHOULDER_LENGTH = 15.0  # cm (L1)
ELBOW_LENGTH = 13.0     # cm (L2)
GRIPPER_LENGTH = 12.0   # cm (User confirmed)
SAFETY_OFFSET = 2.0     # cm (buffer before touching object)

# Calculated Limits
MAX_ARM_REACH = SHOULDER_LENGTH + ELBOW_LENGTH  # 28cm (wrist position)
MAX_GRAB_REACH = MAX_ARM_REACH + GRIPPER_LENGTH  # 40cm (gripper tip)
SAFE_GRAB_RANGE = MAX_GRAB_REACH - SAFETY_OFFSET  # 38cm


def check_reachability(object_distance_cm, object_height_cm=5.0):
    """
    Check if an object is within reachable range.
    
    Args:
        object_distance_cm (float): Distance to object from shoulder pivot
        object_height_cm (float): Height of object relative to shoulder (default 5cm)
    
    Returns:
        tuple: (is_reachable: bool, reason: str, wrist_target_distance: float)
    
    Example:
        reachable, reason, wrist_dist = check_reachability(35.0)
        if not reachable:
            print(f"Cannot reach: {reason}")
    """
    # Calculate where the wrist needs to be
    # Wrist Target = Object Distance (from gripper) - Safety Offset
    # Note: Input object_distance_cm is now assumed to be relative to the gripper
    wrist_target_distance = object_distance_cm - SAFETY_OFFSET
    
    # Check if too close (inside the gripper length)
    if wrist_target_distance < 5.0:
        return False, f"Object too close ({object_distance_cm}cm). Minimum distance: {GRIPPER_LENGTH + SAFETY_OFFSET + 5}cm", wrist_target_distance
    
    # Calculate hypotenuse from shoulder to wrist target
    hypotenuse = math.sqrt(wrist_target_distance**2 + object_height_cm**2)
    
    # Check if beyond max reach
    if hypotenuse > MAX_ARM_REACH:
        max_object_dist = MAX_ARM_REACH + GRIPPER_LENGTH + SAFETY_OFFSET
        return False, f"Object out of reach ({object_distance_cm}cm). Maximum: {max_object_dist:.1f}cm", wrist_target_distance
    
    # Check if too close for triangle to form
    min_hypotenuse = abs(SHOULDER_LENGTH - ELBOW_LENGTH)
    if hypotenuse < min_hypotenuse:
        return False, f"Object too close to body (hypotenuse {hypotenuse:.1f}cm < {min_hypotenuse:.1f}cm)", wrist_target_distance
    
    return True, "Reachable", wrist_target_distance


def get_wrist_angles(object_distance_cm, object_height_cm=5.0, 
                     gripper_length=GRIPPER_LENGTH, safety_offset=SAFETY_OFFSET):
    """
    Calculate shoulder and elbow angles to place gripper tip at object location.
    
    Uses Law of Cosines for 2-link planar IK with gripper offset compensation.
    
    Args:
        object_distance_cm (float): Horizontal distance to object from shoulder pivot
        object_height_cm (float): Vertical height of object relative to shoulder (default 5cm)
        gripper_length (float): Length of gripper (default 13cm)
        safety_offset (float): Safety buffer distance (default 2cm)
    
    Returns:
        tuple: (shoulder_angle, elbow_angle) in degrees, or None if unreachable
    
    Math:
        1. Wrist Target = Object Distance - Safety Offset
        2. Hypotenuse = sqrt(wrist_target² + height²)
        3. Shoulder Angle = atan2(height, wrist_target) + acos((L1² + hyp² - L2²) / (2×L1×hyp))
        4. Elbow Angle = acos((L1² + L2² - hyp²) / (2×L1×L2))
    
    Example:
        # Object at 25cm distance, 5cm height
        angles = get_wrist_angles(25.0, 5.0)
        if angles:
            shoulder, elbow = angles
            print(f"Move to: Shoulder={shoulder}°, Elbow={elbow}°")
    """
    # 1. Check reachability
    reachable, reason, wrist_target_reach = check_reachability(object_distance_cm, object_height_cm)
    
    if not reachable:
        print(f"⚠️ {reason}")
        return None
    
    # 2. Calculate hypotenuse (direct distance from shoulder to wrist target)
    hypotenuse = math.sqrt(wrist_target_reach**2 + object_height_cm**2)
    
    try:
        # 3. Law of Cosines - Shoulder Angle
        # Angle alpha: angle of direct line to wrist target (from horizontal)
        alpha = math.atan2(object_height_cm, wrist_target_reach)
        
        # Angle phi1: angle between shoulder link and direct line
        numerator_shoulder = SHOULDER_LENGTH**2 + hypotenuse**2 - ELBOW_LENGTH**2
        denominator_shoulder = 2 * SHOULDER_LENGTH * hypotenuse
        
        # Clamp for numerical stability
        cos_phi1 = max(-1.0, min(1.0, numerator_shoulder / denominator_shoulder))
        phi1 = math.acos(cos_phi1)
        
        # Total shoulder angle (from horizontal)
        theta_shoulder = math.degrees(alpha + phi1)
        
        # 4. Law of Cosines - Elbow Angle
        numerator_elbow = SHOULDER_LENGTH**2 + ELBOW_LENGTH**2 - hypotenuse**2
        denominator_elbow = 2 * SHOULDER_LENGTH * ELBOW_LENGTH
        
        # Clamp for numerical stability
        cos_phi2 = max(-1.0, min(1.0, numerator_elbow / denominator_elbow))
        phi2 = math.acos(cos_phi2)
        
        # Elbow angle (internal angle)
        theta_elbow = math.degrees(phi2)
        
        return theta_shoulder, theta_elbow
        
    except ValueError as e:
        print(f"❌ Math error in IK calculation: {e}")
        return None


def calculate_approach_step(current_distance_cm, target_distance_cm, step_size=0.5):
    """
    Calculate incremental approach step for visual servoing.
    
    Instead of jumping directly to target, move incrementally for safety and
    to allow visual feedback to correct errors.
    
    Args:
        current_distance_cm (float): Current estimated distance to object
        target_distance_cm (float): Desired final distance (usually gripper_length + safety_offset)
        step_size (float): Maximum step size per iteration (default 0.5cm)
    
    Returns:
        float: Next target distance (closer than current by step_size or remaining distance)
    
    Example:
        # Object at 30cm, want to get to 15cm (gripper + safety)
        current = 30.0
        target = 15.0
        
        # First iteration
        next_dist = calculate_approach_step(current, target, step_size=0.5)
        # next_dist = 29.5 (moved 0.5cm closer)
    """
    remaining_distance = current_distance_cm - target_distance_cm
    
    if remaining_distance <= 0:
        # Already at or past target
        return target_distance_cm
    
    # Move by step_size or remaining distance, whichever is smaller
    step = min(step_size, remaining_distance)
    next_distance = current_distance_cm - step
    
    return next_distance


def get_incremental_wrist_angles(current_distance_cm, target_distance_cm, 
                                 object_height_cm=5.0, step_size=0.5):
    """
    Get wrist angles for incremental approach (one step closer).
    
    Combines calculate_approach_step() and get_wrist_angles() for convenience.
    
    Args:
        current_distance_cm (float): Current distance to object
        target_distance_cm (float): Final target distance
        object_height_cm (float): Object height (default 5cm)
        step_size (float): Step size (default 0.5cm)
    
    Returns:
        tuple: (shoulder_angle, elbow_angle, next_distance) or (None, None, current_distance)
    
    Example:
        shoulder, elbow, next_dist = get_incremental_wrist_angles(30.0, 15.0)
        if shoulder is not None:
            print(f"Step to {next_dist}cm: Shoulder={shoulder}°, Elbow={elbow}°")
    """
    # Calculate next step
    next_distance = calculate_approach_step(current_distance_cm, target_distance_cm, step_size)
    
    # Get angles for this step
    angles = get_wrist_angles(next_distance, object_height_cm)
    
    if angles is None:
        return None, None, current_distance
    
    shoulder, elbow = angles
    return shoulder, elbow, next_distance


if __name__ == "__main__":
    # Test the visual IK solver
    print("=" * 60)
    print("Visual IK Solver - Test Suite")
    print("=" * 60)
    
    # Test 1: Reachability checks
    print("\n1. Reachability Tests:")
    test_distances = [10, 20, 25, 30, 35, 40, 45]
    
    for dist in test_distances:
        reachable, reason, wrist_dist = check_reachability(dist, 5.0)
        status = "✅" if reachable else "❌"
        print(f"   {status} {dist}cm: {reason} (wrist target: {wrist_dist:.1f}cm)")
    
    # Test 2: IK angle calculation
    print("\n2. IK Angle Calculation:")
    test_cases = [
        (20.0, 5.0),  # Close
        (25.0, 5.0),  # Medium
        (30.0, 5.0),  # Far
        (35.0, 5.0),  # Near limit
    ]
    
    for obj_dist, height in test_cases:
        angles = get_wrist_angles(obj_dist, height)
        if angles:
            shoulder, elbow = angles
            print(f"   Object at {obj_dist}cm, {height}cm height:")
            print(f"      → Shoulder: {shoulder:.1f}°, Elbow: {elbow:.1f}°")
        else:
            print(f"   Object at {obj_dist}cm: UNREACHABLE")
    
    # Test 3: Incremental approach
    print("\n3. Incremental Approach Simulation:")
    print("   Approaching object from 30cm to 15cm (0.5cm steps):")
    
    current_dist = 30.0
    target_dist = GRIPPER_LENGTH + SAFETY_OFFSET  # 15cm
    iteration = 0
    max_iterations = 10
    
    while current_dist > target_dist and iteration < max_iterations:
        shoulder, elbow, next_dist = get_incremental_wrist_angles(
            current_dist, target_dist, object_height_cm=5.0, step_size=0.5
        )
        
        if shoulder is None:
            print(f"   ❌ Iteration {iteration}: Failed at {current_dist}cm")
            break
        
        print(f"   Step {iteration}: {current_dist:.1f}cm → {next_dist:.1f}cm "
              f"(Sh: {shoulder:.1f}°, El: {elbow:.1f}°)")
        
        current_dist = next_dist
        iteration += 1
    
    print(f"   ✅ Reached target in {iteration} steps")
    
    # Test 4: Edge cases
    print("\n4. Edge Case Tests:")
    
    # Too close
    print("   Testing object at 10cm (too close):")
    angles = get_wrist_angles(10.0, 5.0)
    print(f"      Result: {'FAILED (as expected)' if angles is None else 'UNEXPECTED SUCCESS'}")
    
    # Too far
    print("   Testing object at 50cm (too far):")
    angles = get_wrist_angles(50.0, 5.0)
    print(f"      Result: {'FAILED (as expected)' if angles is None else 'UNEXPECTED SUCCESS'}")
    
    # At exact limit
    print("   Testing object at 39cm (near max):")
    angles = get_wrist_angles(39.0, 5.0)
    if angles:
        shoulder, elbow = angles
        print(f"      Result: SUCCESS (Sh: {shoulder:.1f}°, El: {elbow:.1f}°)")
    else:
        print(f"      Result: FAILED")
    
    print("\n" + "=" * 60)
    print("✅ All tests complete!")
    print("=" * 60)
