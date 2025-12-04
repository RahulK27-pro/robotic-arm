from flask import Flask, Response, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from camera import VideoCamera
from brain.llm_engine import process_command
from brain.kinematics import solve_angles, compute_forward_kinematics
from hardware.robot_driver import RobotArm
import traceback
import time
import json

load_dotenv()

app = Flask(__name__)
CORS(app)

# Initialize camera with YOLO detection mode
global_camera = VideoCamera(detection_mode='yolo')
# Initialize robot in HARDWARE mode to communicate with Arduino on COM4
# If Arduino is not connected, it will automatically fall back to simulation mode
robot = RobotArm(simulation_mode=False, port='COM4', baudrate=115200)

def gen(camera):
    while True:
        frame = camera.get_frame()
        if frame is None:
            continue
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n\r\n')

@app.route('/video_feed')
def video_feed():
    return Response(gen(global_camera),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/set_target_color', methods=['POST'])
def set_target_color():
    data = request.json
    colors = data.get('colors')
    if not colors:
        colors = None
    global_camera.set_target_colors(colors)
    return jsonify({"status": "success", "targets": colors})

@app.route('/get_detection_result', methods=['GET'])
def get_detection_result():
    if global_camera.last_detection and len(global_camera.last_detection) > 0:
        return jsonify({
            "status": "found",
            "data": global_camera.last_detection,
            "count": len(global_camera.last_detection)
        })
    else:
        return jsonify({"status": "searching"})

@app.route('/set_target_object', methods=['POST'])
def set_target_object():
    """
    Set target object for center-seeking mode.
    Only the specified object will be detected and shown.
    """
    try:
        data = request.json
        object_name = data.get('object_name')  # e.g., "bottle", "cup"
        
        if object_name:
            global_camera.set_target_object(object_name)
            return jsonify({
                "status": "success",
                "target_object": object_name,
                "message": f"Target object set to: {object_name}"
            })
        else:
            global_camera.clear_target_object()
            return jsonify({
                "status": "success",
                "target_object": None,
                "message": "Target object cleared - showing all objects"
            })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/status', methods=['GET'])
def status():
    vision_status = "active" if global_camera.video.isOpened() else "inactive"
    servo_status = "on" # Mocked
    
    return jsonify({
        "backend": "connected",
        "vision": vision_status,
        "servo": servo_status,
        "robot_mode": "simulation" if robot.simulation_mode else "hardware"
    })

@app.route('/manual_control', methods=['POST'])
def manual_control():
    """
    Direct manual control endpoint for Engineer Mode.
    Accepts 6 servo angles and sends them directly to the robot.
    """
    try:
        data = request.json
        angles = data.get('angles')
        
        if not angles:
            return jsonify({"error": "No angles provided"}), 400
        
        if len(angles) != 6:
            return jsonify({"error": f"Expected 6 angles, got {len(angles)}"}), 400
        
        # Validate all angles are in 0-180 range
        for i, angle in enumerate(angles):
            if not isinstance(angle, (int, float)):
                return jsonify({"error": f"Invalid angle at index {i}: must be a number"}), 400
            if angle < 0 or angle > 180:
                return jsonify({"error": f"Invalid angle at index {i}: {angle}° (must be 0-180)"}), 400
        
        # Send to robot
        success = robot.move_to(angles)
        
        if success:
            return jsonify({
                "status": "success",
                "angles": robot.current_angles,
                "mode": "simulation" if robot.simulation_mode else "hardware"
            })
        else:
            return jsonify({"error": "Failed to move robot"}), 500
            
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/get_servo_positions', methods=['GET'])
def get_servo_positions():
    """
    Get current servo positions for real-time feedback.
    """
    try:
        return jsonify({
            "status": "success",
            "angles": robot.current_angles,
            "mode": "simulation" if robot.simulation_mode else "hardware",
            "connected": robot.serial.is_open if robot.serial else False
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

def generate_servo_stream():
    """Generator function for SSE servo updates."""
    while True:
        try:
            # Calculate XYZ coordinates from current angles
            x, y, z = compute_forward_kinematics(robot.current_angles)
            
            # Determine gripper state based on angle
            # Typically: 0-60° = CLOSED, 60-180° = OPEN
            gripper_angle = robot.current_angles[5]
            gripper_state = "OPEN" if gripper_angle > 60 else "CLOSED"
            
            # Create data packet
            data = {
                "angles": robot.current_angles,
                "coordinates": {
                    "x": x,
                    "y": y,
                    "z": z
                },
                "gripper_state": gripper_state,
                "mode": "simulation" if robot.simulation_mode else "hardware",
                "connected": robot.serial.is_open if robot.serial else False
            }
            # Format as SSE message
            yield f"data: {json.dumps(data)}\n\n"
            time.sleep(0.1) # 100ms update rate
        except Exception as e:
            print(f"Stream error: {e}")
            break

@app.route('/servo_stream')
def servo_stream():
    """Endpoint for Server-Sent Events of servo positions."""
    return Response(generate_servo_stream(), mimetype='text/event-stream')

@app.route('/process_command', methods=['POST'])
def handle_command():
    """
    Main endpoint for processing user commands.
    1. Gets command and current vision state.
    2. Calls LLM to get a plan (target coordinates).
    3. Calls IK to get angles for each step.
    4. Calls RobotDriver to execute (simulated).
    """
    try:
        data = request.json
        user_text = data.get('command')
        
        if not user_text:
            return jsonify({"error": "No command provided"}), 400

        # 1. Prepare Vision State (before setting target)
        vision_state = {}
        if global_camera.last_detection:
            for obj in global_camera.last_detection:
                # Handle YOLO detection format (object_name)
                if 'object_name' in obj:
                    object_name = obj['object_name'].lower().replace(' ', '_')
                    key = object_name
                # Handle color detection format (color) - for backward compatibility
                elif 'color' in obj:
                    color = obj['color'].lower()
                    key = f"{color}_cube"
                else:
                    continue
                
                # Prefer CM coordinates if available, else pixel
                if 'cm_x' in obj:
                    vision_state[key] = [obj['cm_x'], obj['cm_y'], 0] # Assume z=0 for table
                else:
                    vision_state[key] = [obj['x'], obj['y'], 0] # Fallback to pixels (will need calibration)

        # 2. Call LLM to get plan and target object
        print(f"[DEBUG] Vision state being sent to LLM: {vision_state}")
        print(f"[DEBUG] Detection count: {len(global_camera.last_detection)}")
        llm_response = process_command(user_text, vision_state)
        plan = llm_response.get("plan", [])
        reply = llm_response.get("reply", "")
        
        # 3. Extract and set target object for center-seeking
        target_object = llm_response.get("target_object")
        if target_object:
            global_camera.set_target_object(target_object)
            print(f"[DEBUG] Target object extracted from command: {target_object}")
            
            # 4. Wait for object to be detected (search timeout: 5 seconds)
            search_timeout = 5.0  # seconds
            search_interval = 0.5  # check every 0.5 seconds
            elapsed_time = 0.0
            object_found = False
            
            print(f"[INFO] Searching for '{target_object}' (timeout: {search_timeout}s)...")
            while elapsed_time < search_timeout:
                # Check if object is now detected
                if global_camera.last_detection and len(global_camera.last_detection) > 0:
                    # Object found!
                    object_found = True
                    detected_obj = global_camera.last_detection[0]
                    print(f"[INFO] Found '{target_object}' after {elapsed_time:.1f}s - Error: ({detected_obj['error_x']}, {detected_obj['error_y']})")
                    
                    # Update vision state with found object
                    vision_state = {}
                    key = target_object.lower().replace(' ', '_')
                    vision_state[key] = [detected_obj['cm_x'], detected_obj['cm_y'], 0]
                    break
                
                # Wait before checking again
                time.sleep(search_interval)
                elapsed_time += search_interval
            
            if not object_found:
                print(f"[WARN] '{target_object}' not found after {search_timeout}s timeout")
                # Clear target and return error
                global_camera.clear_target_object()
                return jsonify({
                    "status": "success",
                    "reply": f"I searched for the {target_object} for {search_timeout} seconds but couldn't find it. Please check if the object is in the camera's view.",
                    "plan": [],
                    "execution_log": []
                })
        else:
            # If no target object, clear filter to show all objects
            global_camera.clear_target_object()
            print(f"[DEBUG] No target object in command - showing all objects")

        simulated_execution = []

        # 3. Execute Plan (Simulation)
        for step in plan:
            if step.get("action") == "move":
                target = step.get("target") # [x, y, z]
                if target and len(target) == 3:
                    try:
                        # Calculate IK
                        # Default pitch -90 (downwards), roll 0
                        angles = solve_angles(target[0], target[1], target[2], pitch=-90, roll=0)
                        
                        # Preserve current gripper state
                        # solve_angles returns 0 for gripper by default, so we overwrite it
                        angles[5] = robot.current_angles[5]

                        # Move Robot
                        robot.move_to_sequenced(angles)
                        
                        simulated_execution.append({
                            "step": step,
                            "angles": angles,
                            "status": "executed"
                        })
                    except ValueError as e:
                        simulated_execution.append({
                            "step": step,
                            "error": str(e),
                            "status": "failed"
                        })
            elif step.get("action") == "grip":
                angle = step.get("angle")
                if angle is not None:
                    # Create new configuration with updated gripper
                    new_angles = list(robot.current_angles)
                    new_angles[5] = angle
                    
                    # Move Robot
                    robot.move_to_sequenced(new_angles)
                    
                    simulated_execution.append({
                        "step": step,
                        "angles": new_angles,
                        "status": "executed"
                    })

        return jsonify({
            "status": "success",
            "reply": reply,
            "plan": plan,
            "execution_log": simulated_execution
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    try:
        app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
    finally:
        del global_camera
