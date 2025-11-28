class CoordinateMapper:
    # Real-world dimensions of A4 paper in cm
    REAL_WIDTH = 29.7
    REAL_HEIGHT = 21.0

    def __init__(self, frame_width, frame_height):
        """
        Initialize the mapper with the camera frame dimensions.
        
        Args:
            frame_width (int): Width of the camera frame in pixels.
            frame_height (int): Height of the camera frame in pixels.
        """
        self.frame_width = frame_width
        self.frame_height = frame_height
        
        # Calculate pixels per centimeter for both axes
        # We map independently to handle aspect ratio mismatches
        self.pixels_per_cm_x = self.frame_width / self.REAL_WIDTH
        self.pixels_per_cm_y = self.frame_height / self.REAL_HEIGHT

    def pixel_to_cm(self, pixel_x, pixel_y):
        """
        Convert pixel coordinates to real-world centimeters.
        
        Args:
            pixel_x (int): X coordinate in pixels.
            pixel_y (int): Y coordinate in pixels.
            
        Returns:
            tuple: (cm_x, cm_y) rounded to 2 decimal places.
        """
        # Map pixels to cm
        cm_x = pixel_x / self.pixels_per_cm_x
        cm_y = pixel_y / self.pixels_per_cm_y
        
        # Round to 2 decimal places
        return round(cm_x, 2), round(cm_y, 2)
