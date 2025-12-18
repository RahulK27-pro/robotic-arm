"""
Visual Grab Controller

High-level orchestrator for complete visual servoing grab workflow.
Coordinates X/Y alignment, Z-axis approach, and grab execution.

State Machine:
    IDLE → ALIGNING → APPROACHING → GRAB_READY → GRABBING → COMPLETE/FAILED
"""

import time
import threading
from enum import Enum


class GrabState(Enum):
    """States for the grab workflow"""
    IDLE = "idle"
    ALIGNING = "aligning"  # X/Y centering
    APPROACHING = "approaching"  # Z-axis (depth) movement
    GRAB_READY = "grab_ready"  # Within grab range
    GRABBING = "grabbing"  # Executing grab
    COMPLETE = "complete"
    FAILED = "failed"


class VisualGrabController:
    """
    Orchestrates the complete visual grab workflow.
    
    Workflow:
        1. ALIGNING: Use visual servoing to center object (X/Y)
        2. APPROACHING: Move forward incrementally using IK (Z-axis)
        3. GRAB_READY: Within 2cm of target
        4. GRABBING: Execute blind grab sequence
        5. COMPLETE/FAILED: Final state
    """
    
    def __init__(self, robot, camera, servoing_agent):
        """
        Initialize grab controller.
        
        Args:
            robot: RobotArm instance
            camera: VideoCamera instance
            servoing_agent: VisualServoingAgent instance
        """
        self.robot = robot
        self.camera = camera
        self.servoing_agent = servoing_agent
        
        self.state = GrabState.IDLE
        self.target_object = None
        self.running = False
        self.thread = None
        
        # Configuration
        self.xy_tolerance = 20  # pixels (for centering)
        self.distance_tolerance = 2.0  # cm (when to stop approaching)
        self.target_distance = 15.0  # cm (gripper_length + safety_offset)
        self.approach_step_size = 0.5  # cm per iteration
        self.max_approach_iterations = 50
        self.alignment_timeout = 10.0  # seconds
        self.approach_timeout = 15.0  # seconds
        
        # Status tracking
        self.status_message = ""
        self.progress = 0.0  # 0.0 to 1.0
        self.error_message = None
        
    def start_grab(self, target_object_name):
        """
        Start the grab sequence for a target object.
        
        Args:
            target_object_name (str): Name of object to grab (e.g., 'cube', 'bottle')
        
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
        self.thread = threading.Thread(target=self._grab_workflow, daemon=True)
        self.thread.start()
        
        print(f"🚀 Visual Grab started for '{target_object_name}'")
        return True
    
    def stop(self):
        """Stop the grab sequence."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)
        
        # Stop visual servoing if active
        if self.servoing_agent.running:
            self.servoing_agent.stop()
        
        self.state = GrabState.IDLE
        print("🛑 Visual Grab stopped")
    
    def get_status(self):
        """
        Get current grab status.
        
        Returns:
            dict: Status information
        """
        return {
            "active": self.running,
            "state": self.state.value,
            "target_object": self.target_object,
            "status_message": self.status_message,
            "progress": self.progress,
            "error": self.error_message
        }
    
    def _grab_workflow(self):
        """
        Main grab workflow (runs in separate thread).
        
        Phases:
            1. ALIGNING: X/Y centering using visual servoing
            2. APPROACHING: Z-axis movement using IK
            3. GRABBING: Final grab execution
        """
        try:
            print("=" * 60)
            print("🎯 VISUAL GRAB WORKFLOW - STARTING")
            print("=" * 60)
            
            # Phase 1: X/Y Alignment
            success = self._phase_1_align()
            if not success:
                self._fail("X/Y alignment failed")
                return
            
            # Phase 2: Z-Axis Approach
            success = self._phase_2_approach()
            if not success:
                self._fail("Z-axis approach failed")
                return
            
            # Phase 3: Grab Execution
            success = self._phase_3_grab()
            if not success:
                self._fail("Grab execution failed")
                return
            
            # Success!
            self.state = GrabState.COMPLETE
            self.status_message = "Grab complete!"
            self.progress = 1.0
            print("=" * 60)
            print("✅ VISUAL GRAB COMPLETE!")
            print("=" * 60)
            
        except Exception as e:
            self._fail(f"Unexpected error: {e}")
        finally:
            self.running = False
    
    def _phase_1_align(self):
        """
        Phase 1: X/Y Alignment
        
        Uses existing visual servoing to center the object.
        
        Returns:
            bool: True if aligned successfully
        """
        self.state = GrabState.ALIGNING
        self.status_message = "Aligning X/Y axes..."
        self.progress = 0.1
        
        print("\n📍 PHASE 1: X/Y ALIGNMENT")
        print("-" * 60)
        
        # Start visual servoing
        self.servoing_agent.start(self.target_object)
        
        # Wait for alignment
        start_time = time.time()
        while self.running:
            # Check timeout
            if time.time() - start_time > self.alignment_timeout:
                print("❌ Alignment timeout")
                self.servoing_agent.stop()
                return False
            
            # Check if object is detected and centered
            detections = self.camera.last_detection
            if detections and len(detections) > 0:
                det = detections[0]
                if det.get('is_centered', False):
                    print("✅ Object centered!")
                    self.servoing_agent.stop()
                    self.progress = 0.3
                    time.sleep(0.5)  # Brief pause
                    return True
            
            time.sleep(0.1)
        
        return False
    
    def _phase_2_approach(self):
        """
        Phase 2: Z-Axis Approach
        
        Moves forward incrementally using IK until within grab range.
        Only moves SHOULDER and ELBOW servos.
        Base stays fixed from alignment phase.
        Wrist stays fixed.
        Gripper opens at start, closes when distance <= 2cm.
        
        Returns:
            bool: True if approached successfully
        """
        from brain.visual_ik_solver import get_wrist_angles, check_reachability
        
        self.state = GrabState.APPROACHING
        self.status_message = "Approaching object..."
        self.progress = 0.4
        
        print("\n🚀 PHASE 2: Z-AXIS APPROACH")
        print("-" * 60)
        
        # Open gripper at start
        print("   Opening gripper...")
        current_angles = list(self.robot.current_angles)
        current_angles[5] = 170  # Open gripper
        self.robot.move_to(current_angles)
        time.sleep(0.5)
        
        start_time = time.time()
        iteration = 0
        
        while self.running and iteration < self.max_approach_iterations:
            # Check timeout
            if time.time() - start_time > self.approach_timeout:
                print("❌ Approach timeout")
                return False
            
            # Get current detection
            detections = self.camera.last_detection
            if not detections or len(detections) == 0:
                print("⚠️ Object lost during approach")
                time.sleep(0.1)
                continue
            
            det = detections[0]
            current_distance = det.get('distance_cm', -1)
            
            if current_distance <= 0:
                print("⚠️ Cannot estimate distance (unknown object)")
                return False
            
            print(f"   Iteration {iteration}: Distance = {current_distance:.1f}cm")
            
            # Check if ready to grab (within 2cm)
            if current_distance <= 2.0:
                print(f"✅ Ready to grab! Distance: {current_distance:.1f}cm")
                
                # Close gripper
                print("   🤏 Closing gripper...")
                current_angles = list(self.robot.current_angles)
                current_angles[5] = 120  # Close gripper
                self.robot.move_to(current_angles)
                time.sleep(0.5)
                
                self.state = GrabState.GRAB_READY
                self.progress = 0.9
                return True
            
            # Check reachability
            reachable, reason, wrist_dist = check_reachability(current_distance, object_height_cm=5.0)
            if not reachable:
                print(f"❌ {reason}")
                return False
            
            # Calculate IK for current distance
            # We want to move the wrist to: current_distance - gripper_length - safety_offset
            angles = get_wrist_angles(current_distance, object_height_cm=5.0)
            if angles is None:
                print(f"❌ IK failed for distance {current_distance:.1f}cm")
                return False
            
            shoulder_angle, elbow_angle = angles
            
            # Get current robot angles
            current_angles = list(self.robot.current_angles)
            
            # Update ONLY shoulder and elbow
            # Keep base (from alignment), wrist, and gripper unchanged
            new_angles = list(current_angles)
            new_angles[1] = shoulder_angle  # Shoulder
            new_angles[2] = elbow_angle     # Elbow
            # new_angles[0] = base (unchanged from alignment)
            # new_angles[3] = wrist pitch (unchanged)
            # new_angles[4] = wrist roll (unchanged)
            # new_angles[5] = gripper (stays open until distance <= 2cm)
            
            # Move robot
            print(f"      → Moving: Shoulder={shoulder_angle:.1f}°, Elbow={elbow_angle:.1f}°")
            success = self.robot.move_to(new_angles)
            
            if not success:
                print("❌ Robot movement failed")
                return False
            
            # Update progress based on distance
            # Progress from 0.4 to 0.7 as we approach from far to near
            if current_distance > 0:
                # Assume max distance is 40cm, min is 2cm
                distance_ratio = max(0, min(1, (40 - current_distance) / 38))
                self.progress = 0.4 + (distance_ratio * 0.3)  # 0.4 to 0.7
            
            iteration += 1
            time.sleep(0.3)  # Pause for visual feedback and distance update
        
        if iteration >= self.max_approach_iterations:
            print("❌ Max iterations reached")
            return False
        
        return False
    
    def _phase_3_grab(self):
        """
        Phase 3: Lift Object
        
        Gripper already closed in Phase 2.
        Just lift the object.
        
        Returns:
            bool: True if lifted successfully
        """
        self.state = GrabState.GRABBING
        self.status_message = "Lifting object..."
        self.progress = 0.95
        
        print("\n📦 PHASE 3: LIFT OBJECT")
        print("-" * 60)
        
        # Lift by raising shoulder
        print("   Lifting...")
        current_angles = list(self.robot.current_angles)
        current_angles[1] += 15  # Lift shoulder by 15 degrees
        current_angles[1] = min(180, current_angles[1])  # Clamp to max
        
        self.robot.move_to(current_angles)
        time.sleep(0.5)
        
        print("✅ Grab complete!")
        return True
    
    def _fail(self, reason):
        """
        Mark grab as failed.
        
        Args:
            reason (str): Failure reason
        """
        self.state = GrabState.FAILED
        self.error_message = reason
        self.status_message = f"Failed: {reason}"
        print(f"❌ GRAB FAILED: {reason}")
        
        # Stop visual servoing if active
        if self.servoing_agent.running:
            self.servoing_agent.stop()


if __name__ == "__main__":
    print("=" * 60)
    print("Visual Grab Controller - Module Loaded")
    print("=" * 60)
    print("\nThis module provides the VisualGrabController class.")
    print("It orchestrates the complete grab workflow:")
    print("  1. ALIGNING: X/Y centering")
    print("  2. APPROACHING: Z-axis movement")
    print("  3. GRABBING: Final grab execution")
    print("\nUsage:")
    print("  controller = VisualGrabController(robot, camera, servoing_agent)")
    print("  controller.start_grab('cube')")
    print("  status = controller.get_status()")
    print("=" * 60)
