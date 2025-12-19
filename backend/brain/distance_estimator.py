"""
Distance Estimation Module for Monocular Visual Servoing

Uses pinhole camera model to estimate distance to objects based on their pixel width.

Formula:
    Distance (cm) = (Known Width × Focal Length) / Pixel Width

Camera Specifications (Logitech C270):
    - Resolution: 1280x720
    - FOV: 60 degrees
    - Focal Length: 1110 pixels (calculated from FOV)
"""

import math


# Camera Configuration (External Webcam at 1280x720)
CAMERA_WIDTH = 1280
CAMERA_HEIGHT = 720
FOCAL_LENGTH_DEFAULT = 1424  # pixels (calibrated with 4cm object at 27cm)


def calibrate_focal_length(known_distance_cm, known_width_cm, pixel_width):
    """
    Calibrate camera focal length using a known object at a known distance.
    
    This is a one-time calibration step to get accurate focal length for your camera.
    
    Args:
        known_distance_cm (float): Measured distance from camera to object (cm)
        known_width_cm (float): Real-world width of the object (cm)
        pixel_width (int): Width of the object in pixels (from bounding box)
    
    Returns:
        float: Calculated focal length in pixels
    
    Example:
        # Place a 3cm cube at 20cm from camera
        # Measure its pixel width in the detection (e.g., 165 pixels)
        focal_length = calibrate_focal_length(20.0, 3.0, 165)
        # focal_length ≈ 1100 pixels
    """
    if pixel_width == 0:
        raise ValueError("Pixel width cannot be zero")
    
    focal_length = (pixel_width * known_distance_cm) / known_width_cm
    print(f"📏 Calibrated Focal Length: {focal_length:.2f} pixels")
    print(f"   (Object: {known_width_cm}cm at {known_distance_cm}cm = {pixel_width}px)")
    
    return focal_length


def calculate_distance(focal_length, known_width_cm, pixel_width):
    """
    Calculate distance to an object using pinhole camera model.
    
    Args:
        focal_length (float): Camera focal length in pixels
        known_width_cm (float): Real-world width of the object (cm)
        pixel_width (int): Width of the object in pixels (from bounding box)
    
    Returns:
        float: Estimated distance in cm, or -1 if calculation fails
    
    Example:
        # Detect a 3cm cube with 110 pixel width
        distance = calculate_distance(1110, 3.0, 110)
        # distance ≈ 30.27 cm
    """
    if pixel_width == 0:
        return -1.0
    
    distance_cm = (known_width_cm * focal_length) / pixel_width
    return round(distance_cm, 2)


def estimate_focal_length_from_fov(fov_degrees, image_width_px):
    """
    Estimate focal length from camera field of view (FOV).
    
    Formula:
        focal_length = (image_width / 2) / tan(FOV / 2)
    
    Args:
        fov_degrees (float): Horizontal field of view in degrees
        image_width_px (int): Image width in pixels
    
    Returns:
        float: Estimated focal length in pixels
    
    Example:
        # Logitech C270 has 60° FOV at 1280x720
        focal_length = estimate_focal_length_from_fov(60, 1280)
        # focal_length ≈ 1108 pixels
    """
    fov_radians = math.radians(fov_degrees)
    focal_length = (image_width_px / 2) / math.tan(fov_radians / 2)
    
    return round(focal_length, 2)


def get_object_pixel_width(bbox):
    """
    Extract pixel width from bounding box.
    
    Args:
        bbox (list): Bounding box [x1, y1, x2, y2]
    
    Returns:
        int: Width in pixels
    """
    x1, y1, x2, y2 = bbox
    return abs(x2 - x1)


def get_object_pixel_height(bbox):
    """
    Extract pixel height from bounding box.
    
    Args:
        bbox (list): Bounding box [x1, y1, x2, y2]
    
    Returns:
        int: Height in pixels
    """
    x1, y1, x2, y2 = bbox
    return abs(y2 - y1)


# Known object dimensions (in cm)
# These are real-world measurements of common objects
KNOWN_OBJECT_WIDTHS = {
    'cube': 4.0,        # Test cube (user confirmed 4cm)
    'bottle': 4.0,      # Test object (user using 4cm cube/bottle interchangeably)
    'cup': 8.0,         # Standard coffee cup diameter
    'cell phone': 7.0,  # Average smartphone width
    'book': 15.0,       # Standard paperback width
    'mouse': 6.0,       # Computer mouse width
    'keyboard': 30.0,   # Standard keyboard width
}


def get_known_width(object_name):
    """
    Get known width for an object class.
    
    Args:
        object_name (str): Object class name (e.g., 'bottle', 'cube')
    
    Returns:
        float: Known width in cm, or None if unknown
    """
    object_name_lower = object_name.lower()
    return KNOWN_OBJECT_WIDTHS.get(object_name_lower)


def estimate_distance_from_detection(detection, focal_length=FOCAL_LENGTH_DEFAULT):
    """
    Estimate distance from a YOLO detection dictionary.
    
    Args:
        detection (dict): Detection with 'object_name' and 'bbox' keys
        focal_length (float): Camera focal length in pixels
    
    Returns:
        float: Estimated distance in cm, or -1 if cannot estimate
    
    Example:
        detection = {
            'object_name': 'cube',
            'bbox': [100, 200, 210, 310]  # 110px wide
        }
        distance = estimate_distance_from_detection(detection)
    """
    object_name = detection.get('object_name', '').lower()
    bbox = detection.get('bbox')
    
    if not bbox:
        return -1.0
    
    # Get known width for this object
    known_width = get_known_width(object_name)
    if known_width is None:
        # Unknown object, cannot estimate distance
        return -1.0
    
    # Calculate pixel width
    pixel_width = get_object_pixel_width(bbox)
    
    # Calculate distance
    distance = calculate_distance(focal_length, known_width, pixel_width)
    
    return distance


if __name__ == "__main__":
    # Test the distance estimation
    print("=" * 60)
    print("Distance Estimation Module - Test")
    print("=" * 60)
    
    # Test 1: Focal length estimation
    print("\n1. Estimating focal length from FOV:")
    focal = estimate_focal_length_from_fov(60, 1280)
    print(f"   Logitech C270 (60° FOV, 1280px): {focal} pixels")
    
    # Test 2: Calibration
    print("\n2. Calibration test:")
    print("   Scenario: 3cm cube at 20cm distance, measures 165px")
    calibrated_focal = calibrate_focal_length(20.0, 3.0, 165)
    
    # Test 3: Distance calculation
    print("\n3. Distance calculation tests:")
    test_cases = [
        (1110, 3.0, 165, 20.0),   # 3cm cube, 165px → should be ~20cm
        (1110, 3.0, 110, 30.27),  # 3cm cube, 110px → should be ~30cm
        (1110, 3.0, 83, 40.12),   # 3cm cube, 83px → should be ~40cm
        (1110, 6.0, 165, 40.36),  # 6cm bottle, 165px → should be ~40cm
    ]
    
    for focal, width, pixels, expected in test_cases:
        distance = calculate_distance(focal, width, pixels)
        error = abs(distance - expected)
        print(f"   {width}cm object, {pixels}px → {distance}cm (expected {expected}cm, error: {error:.2f}cm)")
    
    # Test 4: Detection integration
    print("\n4. Detection integration test:")
    mock_detection = {
        'object_name': 'cube',
        'bbox': [100, 200, 210, 310]  # 110px wide
    }
    distance = estimate_distance_from_detection(mock_detection)
    print(f"   Detected cube (110px wide) → {distance}cm")
    
    print("\n" + "=" * 60)
    print("✅ All tests complete!")
    print("=" * 60)
