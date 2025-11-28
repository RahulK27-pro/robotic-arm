from coordinate_mapper import CoordinateMapper

def test_mapping():
    # Example Camera Resolution (e.g., 640x480)
    FRAME_WIDTH = 640
    FRAME_HEIGHT = 480
    
    # Initialize Mapper
    mapper = CoordinateMapper(FRAME_WIDTH, FRAME_HEIGHT)
    
    print(f"Initialized Mapper with Frame: {FRAME_WIDTH}x{FRAME_HEIGHT}")
    print(f"Real Dimensions: {mapper.REAL_WIDTH}cm x {mapper.REAL_HEIGHT}cm")
    print("-" * 30)

    # Test Cases
    test_points = [
        (0, 0),                         # Top-Left
        (FRAME_WIDTH, FRAME_HEIGHT),    # Bottom-Right
        (FRAME_WIDTH // 2, FRAME_HEIGHT // 2), # Center
        (100, 100)                      # Arbitrary point
    ]

    for px, py in test_points:
        cm_x, cm_y = mapper.pixel_to_cm(px, py)
        print(f"Pixel ({px}, {py}) -> Real World ({cm_x} cm, {cm_y} cm)")

    # Integration Example Simulation
    print("-" * 30)
    print("Integration Example:")
    
    # Simulate a detected object
    detected_object = {"color": "Red", "cx": 320, "cy": 240}
    
    real_x, real_y = mapper.pixel_to_cm(detected_object["cx"], detected_object["cy"])
    
    print(f"Object Detected: {detected_object['color']} Cube at X={real_x}cm, Y={real_y}cm")

if __name__ == "__main__":
    test_mapping()
