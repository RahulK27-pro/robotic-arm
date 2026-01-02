"""
Pick-and-Place Controller for Robotic Arm

Manages the complete pick-and-place operation after visual servoing grab completion.
Executes a smooth, sequential workflow:
1. LIFTING - Raise object by moving shoulder/elbow
2. ROTATING - Rotate base to target position
3. LOWERING - Lower object to placement height
4. RELEASING - Open gripper gradually
5. RETURNING - Move back to home position
6. COMPLETE - Operation finished

All movements use S-curve interpolation for smooth acceleration/deceleration.
"""

import time
import threading
import math
from hardware.robot_driver import RobotArm


class PickPlaceController:
    def __init__(self, robot: RobotArm):
        """
        Initialize pick-and-place controller.
        
        Args:
            robot: RobotArm instance for servo control
        """
        self.robot = robot
        self.running = False
        self.state = "IDLE"
        self.thread = None
        
        # Operation parameters
        self.target_base_angle = 0  # Default target position (0 degrees)
        
        # Telemetry
        self.current_telemetry = {
            "state": "IDLE",
            "phase": "None",
            "progress": 0.0,
            "current_angles": [0, 0, 0, 0, 0, 0],
            "message": "Ready"
        }
        
        # Movement configuration
        self.LIFT_SHOULDER = 100  # Safe horizontal position (user requested max 100°)
        self.LIFT_ELBOW = 120     # Maintain stable elbow position during transport
        self.PLACE_SHOULDER = 100  # Forward/down position
        self.PLACE_ELBOW = 140     # More open (lowers wrist)
        self.GRIPPER_CLOSED = 120
        self.GRIPPER_OPEN = 170  # Full open for complete release
        self.HOME_POSITION = [23, 100, 140, 90, 12, 155]
        
        print("✅ PickPlaceController initialized")
    
    def start(self, target_base_angle=0, modifier="normal"):
        """
        Start the pick-and-place sequence.
        
        Args:
            target_base_angle: Base rotation angle for placement (default: 0°)
            modifier: Placement distance modifier ("normal", "near", "far")
        """
        if self.running:
            print("⚠️ Pick-and-place already running!")
            return False
        
        self.target_base_angle = target_base_angle
        self.modifier = modifier
        self.running = True
        self.state = "STARTING"
        
        print(f"\n{'='*60}")
        print(f"🚀 PICK-AND-PLACE STARTED")
        print(f"   Target Base Angle: {target_base_angle}° | Modifier: {modifier}")
        print(f"{'='*60}\n")
        
        # Start execution thread
        self.thread = threading.Thread(target=self._execute_sequence, daemon=True)
        self.thread.start()
        
        return True


    
    def stop(self):
        """Emergency stop the operation."""
        if self.running:
            print("🛑 EMERGENCY STOP - Pick-and-Place")
            self.running = False
            self.state = "STOPPED"
            self.current_telemetry["state"] = "STOPPED"
            self.current_telemetry["message"] = "Emergency stopped by user"
    
    def get_status(self):
        """Get current status and telemetry."""
        return {
            "running": self.running,
            "state": self.state,
            **self.current_telemetry
        }
    
    def s_curve(self, t):
        """
        S-curve smoothing function (0 to 1).
        Provides smooth acceleration at start and deceleration at end.
        
        Args:
            t: Time parameter (0.0 to 1.0)
        
        Returns:
            Smoothed value (0.0 to 1.0)
        """
        return t * t * (3.0 - 2.0 * t)
    
    def _smooth_move(self, start_angles, target_angles, duration, steps, phase_name):
        """
        Execute smooth interpolated movement between two poses.
        
        Args:
            start_angles: Starting servo angles [6]
            target_angles: Target servo angles [6]
            duration: Total duration in seconds
            steps: Number of interpolation steps
            phase_name: Name of the phase for telemetry
        """
        dt = duration / steps
        
        for i in range(steps + 1):
            if not self.running:
                break
            
            # Calculate smooth interpolation parameter
            t = i / steps
            t_smooth = self.s_curve(t)
            
            # Interpolate all servo angles
            current_angles = []
            for j in range(6):
                # LOCK UNCHANGED JOINTS to prevent float drift
                if start_angles[j] == target_angles[j]:
                    current_angles.append(int(start_angles[j]))
                else:
                    angle = start_angles[j] + (target_angles[j] - start_angles[j]) * t_smooth
                    current_angles.append(int(angle))
            
            # Move robot
            self.robot.move_to(current_angles)
            
            # Update telemetry
            progress = (i / steps) * 100.0
            self.current_telemetry["phase"] = phase_name
            self.current_telemetry["progress"] = progress
            self.current_telemetry["current_angles"] = current_angles
            
            print(f"  [{phase_name}] Progress: {progress:.1f}% | Angles: {current_angles}")
            
            time.sleep(dt)
    
    def _execute_sequence(self):
        """Main execution loop for pick-and-place state machine."""
        try:
            # ============================================================
            # PHASE 1: LIFTING
            # ============================================================
            self.state = "LIFTING"
            self.current_telemetry["state"] = "LIFTING"
            self.current_telemetry["message"] = "Lifting object"
            
            print(f"\n{'='*60}")
            print("📤 PHASE 1: LIFTING OBJECT")
            print(f"{'='*60}")
            
            # Get current position
            current_angles = list(self.robot.current_angles)
            # FORCE-LOCK wrist angles in START position to prevent drift-based interpolation
            current_angles[3] = 90  # Wrist pitch
            current_angles[4] = 12  # Wrist roll
            
            # Target: Raise shoulder and close elbow to lift
            lift_angles = list(current_angles)
            lift_angles[1] = self.LIFT_SHOULDER  # Shoulder backward/up
            lift_angles[2] = self.LIFT_ELBOW     # Elbow more closed
            lift_angles[3] = 90  # LOCK wrist pitch to prevent twitch
            lift_angles[4] = 12  # LOCK wrist roll
            
            self._smooth_move(
                start_angles=current_angles,
                target_angles=lift_angles,
                duration=2.3,  # 1.5x faster than 3.5s
                steps=23,
                phase_name="LIFTING"
            )
            
            time.sleep(0.5)  # Stabilization pause
            
            if not self.running:
                return
            
            # ============================================================
            # PHASE 2: ROTATING
            # ============================================================
            self.state = "ROTATING"
            self.current_telemetry["state"] = "ROTATING"
            self.current_telemetry["message"] = f"Rotating to {self.target_base_angle}°"
            
            print(f"\n{'='*60}")
            print(f"🔄 PHASE 2: ROTATING BASE TO {self.target_base_angle}°")
            print(f"{'='*60}")
            
            current_angles = list(self.robot.current_angles)
            # FORCE-LOCK wrist angles
            current_angles[3] = 90
            current_angles[4] = 12
            
            rotate_angles = list(current_angles)
            rotate_angles[0] = self.target_base_angle  # Base rotation only
            rotate_angles[3] = 90  # LOCK wrist pitch to prevent twitch
            rotate_angles[4] = 12  # LOCK wrist roll
            
            self._smooth_move(
                start_angles=current_angles,
                target_angles=rotate_angles,
                duration=2.0,
                steps=20,
                phase_name="ROTATING"
            )
            
            time.sleep(0.5)
            
            if not self.running:
                return
            
            # ============================================================
            # PHASE 3: LOWERING
            # ============================================================
            self.state = "LOWERING"
            self.current_telemetry["state"] = "LOWERING"
            self.current_telemetry["message"] = f"Lowering to placement height ({self.modifier})"
            
            print(f"\n{'='*60}")
            print(f"📥 PHASE 3: LOWERING OBJECT ({self.modifier.upper()})")
            print(f"{'='*60}")
            
            # Determine placement shoulder angle based on modifier
            # Standard: 90
            # Far (Reach out): 75
            # Near (Close in): 105
            place_shoulder = 90
            if self.modifier == "far":
                place_shoulder = 75
            elif self.modifier == "near":
                place_shoulder = 105
            
            current_angles = list(self.robot.current_angles)
            # FORCE-LOCK wrist angles
            current_angles[3] = 90
            current_angles[4] = 12
            
            lower_angles = list(current_angles)
            lower_angles[1] = place_shoulder  # Adjusted shoulder for distance
            lower_angles[2] = self.PLACE_ELBOW  # Elbow more open
            lower_angles[3] = 90  # LOCK wrist pitch to prevent twitch
            lower_angles[4] = 12  # LOCK wrist roll
            
            self._smooth_move(
                start_angles=current_angles,
                target_angles=lower_angles,
                duration=2.3,  # 1.5x faster than 3.5s
                steps=23,
                phase_name="LOWERING"
            )
            
            time.sleep(0.5)
            
            if not self.running:
                return
            
            # ============================================================
            # PHASE 4: RELEASING
            # ============================================================
            self.state = "RELEASING"
            self.current_telemetry["state"] = "RELEASING"
            self.current_telemetry["message"] = "Releasing object"
            
            print(f"\n{'='*60}")
            print("🤲 PHASE 4: RELEASING OBJECT")
            print(f"{'='*60}")
            
            current_angles = list(self.robot.current_angles)
            
            # Gradual gripper opening: 120° → 135° → 155°
            # First partial open
            partial_open = list(current_angles)
            partial_open[5] = 135
            self.robot.move_to(partial_open)
            time.sleep(0.4)
            
            # Full open
            full_open = list(current_angles)
            full_open[5] = self.GRIPPER_OPEN
            self.robot.move_to(full_open)
            time.sleep(0.6)
            
            self.current_telemetry["progress"] = 100.0
            print("  ✅ Object released")
            
            time.sleep(0.5)
            
            if not self.running:
                return
            
            # ============================================================
            # PHASE 5: RETURNING HOME
            # ============================================================
            self.state = "RETURNING"
            self.current_telemetry["state"] = "RETURNING"
            self.current_telemetry["message"] = "Returning to home position"
            
            print(f"\n{'='*60}")
            print("🏠 PHASE 5: RETURNING HOME")
            print(f"{'='*60}")
            
            # Sequential movement for safety: one joint at a time
            current_angles = list(self.robot.current_angles)
            
            # 1. Lift slightly first (safety)
            current_angles[1] = 120
            self.robot.move_to(current_angles)
            time.sleep(0.3)
            
            # 2. Move to home position smoothly
            self._smooth_move(
                start_angles=current_angles,
                target_angles=self.HOME_POSITION,
                duration=3.0,
                steps=30,
                phase_name="RETURNING"
            )
            
            print("  ✅ Returned to home position")
            
            # ============================================================
            # COMPLETE
            # ============================================================
            self.state = "COMPLETE"
            self.current_telemetry["state"] = "COMPLETE"
            self.current_telemetry["message"] = "Pick-and-place complete!"
            self.current_telemetry["progress"] = 100.0
            
            print(f"\n{'='*60}")
            print("✅ PICK-AND-PLACE COMPLETE!")
            print(f"{'='*60}\n")
            
        except Exception as e:
            print(f"❌ Error during pick-and-place: {e}")
            import traceback
            traceback.print_exc()
            self.state = "ERROR"
            self.current_telemetry["state"] = "ERROR"
            self.current_telemetry["message"] = f"Error: {str(e)}"
        
        finally:
            self.running = False
