import math
import numpy as np

class TrajectoryPlanner:
    """
    Handles trajectory generation for robotic arm movement.
    Implements S-Curve Velocity Profiling using cubic easing.
    """
    
    @staticmethod
    def s_curve(t):
        """
        Cubic easing function (smooth start/stop).
        s = 3t^2 - 2t^3
        Maps time t (0 to 1) to progress s (0 to 1).
        """
        return 3 * t**2 - 2 * t**3

    @staticmethod
    def generate_path(start_angles, end_angles, duration, frequency=50):
        """
        Generates a list of waypoints for a smooth path.
        
        Args:
            start_angles (list): Starting servo angles [deg].
            end_angles (list): Target servo angles [deg].
            duration (float): Time to complete movement in seconds.
            frequency (int): Updates per second (default 50Hz = 20ms).
            
        Returns:
            list: List of angle lists (waypoints).
        """
        steps = int(duration * frequency)
        if steps == 0:
            return [end_angles]
            
        path = []
        dt = 1.0 / steps
        
        # Convert lists to numpy arrays for easier math if complex, 
        # but standard python lists are fine for 6 elements.
        
        for i in range(steps + 1):
            t = i / steps
            ease = TrajectoryPlanner.s_curve(t)
            
            current_angles = []
            for j in range(len(start_angles)):
                start = start_angles[j]
                end = end_angles[j]
                
                # Interpolate
                val = start + (end - start) * ease
                current_angles.append(round(val, 2))  # Keep precision reasonable
                
            path.append(current_angles)
            
        return path
