"""
Continuous Alignment Grab Controller

Combines visual servoing (X/Y alignment) with Z-axis approach in a single continuous loop.
Maintains center alignment while approaching the object.

Key Features:
- Continuous center alignment during approach
- Only shoulder and elbow move during approach
- Base adjusts for X-axis centering
- Gripper opens at start, closes when object within reach
"""

import time
import threading
from enum import Enum


class GrabState(Enum):
    """States for the continuous grab workflow"""
    IDLE = "idle"
    CENTERING = "centering"  # Initial X/Y centering
    APPROACHING = "approaching"  # Forward movement with alignment
    GRABBING = "grabbing"  # Gripper closing
    LIFTING = "lifting"  # Lift object
    COMPLETE = "complete"
    FAILED = "failed"


class ContinuousGrabController:
    """
    Continuous alignment grab controller.
    
    Maintains object centering while approaching using distance-based IK.
    """
    
    def __init__(self, robot, camera):
        """
        Initialize continuous grab controller.
        
        Args:
            robot: RobotArm instance
            camera: VideoCamera instance
        """
        self.robot = robot
        self.camera = camera
        
        self.state = GrabState.IDLE
        self.target_object = None
        self.running = False
        self.thread = None
        
        # Configuration
        self.xy_tolerance = 20  # pixels (centering threshold)
        self.grab_distance = 2.0  # cm (SAFETY_OFFSET from gripper)
        self.max_iterations = 100
        self.timeout = 30.0  # seconds
        
        # Control gains
        self.gain_x = 0.03  # Base rotation gain
        self.max_base_step = 2.0  # Max base movement per frame
        
        # Status tracking
        self.status_message = ""
        self.progress = 0.0
        self.error_message = None
        
    def start_grab(self, target_object_name):
        """
        Start continuous grab sequence.
        
        Args:
            target_object_name (str): Name of object to grab
        
        Returns:
            bool: True if started successfully
        """
        if self.running:
            print("⚠️ Grab already in progress")
            return False
        
        self.target_object = target_object_name
        self.state = GrabState.IDLE
        self.running = True
        self.error_message = None
        
        # Start grab thread
        self.thread = threading.Thread(target=self._continuous_grab_workflow, daemon=True)
        self.thread.start()
        
        print(f"🚀 Continuous Grab started for '{target_object_name}'")
        return True
    
    def stop(self):
        """Stop grab sequence."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)
        
        self.state = GrabState.IDLE
        print("🛑 Continuous Grab stopped")
    
    def get_status(self):
        """Get current grab status."""
        return {
            "active": self.running,
            "state": self.state.value,
            "target_object": self.target_object,
            "status_message": self.status_message,
            "progress": self.progress,
            "error": self.error_message
        }
    
    def _continuous_grab_workflow(self):
        """
        Main continuous grab workflow.
        
        Phase 1: Center object (X/Y only)
        Phase 2: Approach while maintaining center (X + Z)
        """
        from brain.visual_ik_solver import get_wrist_angles, check_reachability
        
        try:
            print("=" * 60)
            print("🎯 CONTINUOUS GRAB WORKFLOW - STARTING")
            print("=" * 60)
            
            # Set camera target
            self.camera.set_target_object(self.target_object)
            
            # ===== PHASE 1: CENTERING =====
            self.state = GrabState.CENTERING
            self.status_message = "Centering object..."
            self.progress = 0.1
            
            print("\n📍 PHASE 1: CENTERING OBJECT")
            print("-" * 60)
            
            # Open gripper
            print("Opening gripper...")
            current_angles = list(self.robot.current_angles)
            current_angles[5] = 170  # Open
            self.robot.move_to(current_angles)
            time.sleep(0.5)
            
            # Wait for object to be centered
            centering_start = time.time()
            centering_timeout = 15.0  # seconds
            centered_frames = 0
            required_centered_frames = 5  # Need 5 consecutive centered frames
            
            while self.running:
                if time.time() - centering_start > centering_timeout:
                    self._fail("Centering timeout")
                    return
                
                detections = self.camera.last_detection
                if not detections:
                    centered_frames = 0
                    time.sleep(0.1)
                    continue
                
                det = detections[0]
                error_x = det.get('error_x', 0)
                error_y = det.get('error_y', 0)
                
                is_centered = abs(error_x) < self.xy_tolerance and abs(error_y) < self.xy_tolerance
                
                if is_centered:
                    centered_frames += 1
                    print(f"Centered! ({centered_frames}/{required_centered_frames})")
                    
                    if centered_frames >= required_centered_frames:
                        print("✅ Object fully centered! Starting approach...")
                        break
                else:
                    centered_frames = 0
                    print(f"Centering... ErrX:{error_x:+4.0f}px ErrY:{error_y:+4.0f}px")
                
                time.sleep(0.2)
            
            self.progress = 0.3
            
            # ===== PHASE 2: APPROACH WITH ALIGNMENT =====
            self.state = GrabState.APPROACHING
            self.status_message = "Approaching with alignment..."
            
            print("\n🚀 PHASE 2: APPROACHING (with continuous alignment)")
            print("-" * 60)
            
            start_time = time.time()
            iteration = 0
            object_grabbed = False
            
            while self.running and iteration < self.max_iterations:
                # Check timeout
                if time.time() - start_time > self.timeout:
                    self._fail("Approach timeout")
                    return
                
                # Get current detection
                detections = self.camera.last_detection
                if not detections or len(detections) == 0:
                    print(f"[{iteration}] ⚠️ No object detected, waiting...")
                    time.sleep(0.1)
                    iteration += 1
                    continue
                
                det = detections[0]
                
                # Get alignment errors and distance
                error_x = det.get('error_x', 0)
                error_y = det.get('error_y', 0)
                distance_cm = det.get('distance_cm', -1)
                
                if distance_cm <= 0:
                    print(f"[{iteration}] ⚠️ Cannot estimate distance")
                    time.sleep(0.1)
                    iteration += 1
                    continue
                
                # Check if within grab range
                if distance_cm <= self.grab_distance:
                    print(f"\n✅ OBJECT WITHIN REACH! Distance: {distance_cm:.1f}cm (Threshold: {self.grab_distance}cm)")
                    object_grabbed = True
                    break
                
                # Check reachability
                reachable, reason, _ = check_reachability(distance_cm, object_height_cm=5.0)
                if not reachable:
                    self._fail(reason)
                    return
                
                # Calculate IK for current distance
                angles = get_wrist_angles(distance_cm, object_height_cm=5.0)
                if angles is None:
                    self._fail(f"IK failed for distance {distance_cm:.1f}cm")
                    return
                
                shoulder_target, elbow_target = angles
                
                # Get current angles
                current_angles = list(self.robot.current_angles)
                
                # Calculate base adjustment for X-axis centering
                # error_x > 0: object is LEFT → rotate RIGHT → INCREASE base angle
                base_correction = error_x * self.gain_x
                base_correction = max(-self.max_base_step, min(self.max_base_step, base_correction))
                
                new_base = current_angles[0] + base_correction
                new_base = max(0, min(180, new_base))  # Clamp to servo limits
                
                # Build new angle set
                new_angles = list(current_angles)
                new_angles[0] = new_base        # Base (X-axis alignment)
                new_angles[1] = shoulder_target # Shoulder (Z-axis approach)
                new_angles[2] = elbow_target    # Elbow (Z-axis approach)
                # new_angles[3] = wrist pitch (unchanged)
                # new_angles[4] = wrist roll (unchanged)
                # new_angles[5] = gripper (stays open)
                
                # Status display
                is_centered_x = abs(error_x) < self.xy_tolerance
                is_centered_y = abs(error_y) < self.xy_tolerance
                center_status = "✓" if (is_centered_x and is_centered_y) else "✗"
                
                print(f"[{iteration:3d}] Dist:{distance_cm:5.1f}cm | "
                      f"ErrX:{error_x:+4.0f}px | ErrY:{error_y:+4.0f}px | "
                      f"Centered:{center_status} | "
                      f"Base:{current_angles[0]:.0f}°→{new_base:.0f}° | "
                      f"Sh:{shoulder_target:.0f}° El:{elbow_target:.0f}°")
                
                # Move robot
                success = self.robot.move_to(new_angles)
                if not success:
                    self._fail("Robot movement failed")
                    return
                
                # Update progress (0.3 to 0.8 based on distance)
                if distance_cm > 0:
                    distance_ratio = max(0, min(1, (40 - distance_cm) / 38))
                    self.progress = 0.3 + (distance_ratio * 0.5)
                
                iteration += 1
                time.sleep(0.15)  # Small delay for stability
            
            if not object_grabbed:
                self._fail("Max iterations reached without grabbing")
                return
            
            # ===== PHASE 3: CLOSE GRIPPER =====
            print("\n🤏 PHASE 3: CLOSING GRIPPER")
            print("-" * 60)
            
            self.state = GrabState.GRABBING
            self.status_message = "Closing gripper..."
            self.progress = 0.85
            
            current_angles = list(self.robot.current_angles)
            current_angles[5] = 120  # Close
            self.robot.move_to(current_angles)
            time.sleep(0.8)
            
            # ===== PHASE 4: LIFT =====
            print("\n📦 PHASE 4: LIFTING OBJECT")
            print("-" * 60)
            
            self.state = GrabState.LIFTING
            self.status_message = "Lifting object..."
            self.progress = 0.95
            
            current_angles[1] += 15  # Lift shoulder
            current_angles[1] = min(180, current_angles[1])
            self.robot.move_to(current_angles)
            time.sleep(0.5)
            
            # Success!
            self.state = GrabState.COMPLETE
            self.status_message = "Grab complete!"
            self.progress = 1.0
            
            print("=" * 60)
            print("✅ CONTINUOUS GRAB COMPLETE!")
            print("=" * 60)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            self._fail(f"Unexpected error: {e}")
        finally:
            self.running = False
            self.camera.clear_target_object()
    
    def _fail(self, reason):
        """Mark grab as failed."""
        self.state = GrabState.FAILED
        self.error_message = reason
        self.status_message = f"Failed: {reason}"
        print(f"❌ GRAB FAILED: {reason}")


if __name__ == "__main__":
    print("=" * 60)
    print("Continuous Alignment Grab Controller - Module Loaded")
    print("=" * 60)
    print("\nThis module provides continuous center alignment during grab.")
    print("Features:")
    print("  - Maintains X/Y centering while approaching")
    print("  - Moves shoulder and elbow based on distance")
    print("  - Adjusts base for X-axis alignment")
    print("  - Closes gripper when object within reach")
    print("\nUsage:")
    print("  controller = ContinuousGrabController(robot, camera)")
    print("  controller.start_grab('bottle')")
    print("=" * 60)
