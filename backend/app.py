from flask import Flask, Response, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from camera import VideoCamera
from brain.llm_engine import process_command
from brain.kinematics import solve_angles, compute_forward_kinematics
from hardware.robot_driver import RobotArm
from visual_servoing import VisualServoingAgent
from features.mimic_logic import MimicController
from pick_place_controller import PickPlaceController
import traceback
import time
import json
import threading
import cv2
import numpy as np

# Load .env from the backend directory explicitly
import os
basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

app = Flask(__name__)
CORS(app)

# Initialize camera with YOLO detection mode
global_camera = VideoCamera(detection_mode='yolo')
# Initialize robot in HARDWARE mode to communicate with Arduino on COM4
# If Arduino is not connected, it will automatically fall back to simulation mode
robot = RobotArm(simulation_mode=False, port='COM4', baudrate=115200)

# Initialize pick-and-place controller
pick_place_ctrl = PickPlaceController(robot)

# Initialize visual servoing agent with pick-and-place callback
def on_grab_complete_callback():
    """Automatically trigger pick-and-place after grab completion."""
    print("\n" + "="*60)
    print("🎯 GRAB COMPLETE - STARTING PICK-AND-PLACE")
    print("="*60 + "\n")
    pick_place_ctrl.start(target_base_angle=0)

servoing_agent = VisualServoingAgent(robot, global_camera, on_grab_complete=on_grab_complete_callback)

# ... (Routes) ...

@app.route('/start_servoing', methods=['POST'])
def start_servoing():
    data = request.json
    target_object = data.get('target_object')
    if not target_object:
        return jsonify({"error": "Target object required"}), 400
        
    servoing_agent.start(target_object)
    return jsonify({"status": "started", "target": target_object})

@app.route('/stop_servoing', methods=['POST'])
def stop_servoing():
    servoing_agent.stop()
    return jsonify({"status": "stopped"})

@app.route('/servoing_status', methods=['GET'])
def get_servoing_status():
    return jsonify(servoing_agent.get_status())

# --- PICK-AND-PLACE INTEGRATION ---
@app.route('/pick_place/start', methods=['POST'])
def start_pick_place():
    """Start pick-and-place operation."""
    try:
        data = request.json or {}
        target_angle = data.get('target_base_angle', 0)  # Default to 0 degrees
        
        success = pick_place_ctrl.start(target_base_angle=target_angle)
        
        if success:
            return jsonify({
                "status": "started",
                "target_angle": target_angle,
                "message": "Pick-and-place sequence started"
            })
        else:
            return jsonify({
                "status": "already_running",
                "message": "Pick-and-place is already in progress"
            }), 400
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/pick_place/stop', methods=['POST'])
def stop_pick_place():
    """Emergency stop pick-and-place operation."""
    try:
        pick_place_ctrl.stop()
        return jsonify({
            "status": "stopped",
            "message": "Pick-and-place stopped"
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/pick_place/status', methods=['GET'])
def get_pick_place_status():
    """Get current pick-and-place status and telemetry."""
    try:
        status = pick_place_ctrl.get_status()
        return jsonify(status)
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

# --- MIMIC MODE INTEGRATION ---
mimic_thread = None
mimic_ctrl = MimicController(robot, global_camera)

@app.route('/mimic_start', methods=['POST'])
def start_mimic():
    global mimic_thread
    print("[DEBUG] /mimic_start endpoint called", flush=True)
    print(f"[DEBUG] Current thread status: {mimic_thread.is_alive() if mimic_thread else 'None'}", flush=True)
    print(f"[DEBUG] mimic_ctrl.active: {mimic_ctrl.active}", flush=True)
    
    if mimic_thread is None or not mimic_thread.is_alive():
        print("[DEBUG] Starting new mimic thread...", flush=True)
        
        # Pause YOLO detection to prevent terminal spam
        global_camera.pause_yolo = True
        print("[INFO] YOLO detection paused", flush=True)
        
        mimic_thread = threading.Thread(target=mimic_ctrl.start)
        mimic_thread.daemon = True
        mimic_thread.start()
        print("[DEBUG] Mimic thread started", flush=True)
        return jsonify({"status": "started", "message": "Mimic Mode Active"})
    else:
        print("[DEBUG] Thread already running", flush=True)
        return jsonify({"status": "already_running"})

@app.route('/mimic_stop', methods=['POST'])
def stop_mimic():
    mimic_ctrl.stop()
    
    # Resume YOLO detection
    global_camera.pause_yolo = False
    print("[INFO] YOLO detection resumed", flush=True)
    
    return jsonify({"status": "stopped", "message": "Mimic Mode Stopping..."})

@app.route('/mimic_telemetry', methods=['GET'])
def get_mimic_telemetry():
    """Get current mimic mode telemetry (error_x, error_y, reach, gripper)"""
    telemetry = mimic_ctrl.get_telemetry()
    telemetry["active"] = mimic_ctrl.active
    return jsonify(telemetry)

def gen_mimic(camera):
    """Generator for mimic mode video feed with ONLY hand overlay (no YOLO)"""
    while True:
        # Get raw frame without YOLO processing
        raw_frame = camera.get_raw_frame()
        if raw_frame is None:
            time.sleep(0.01)
            continue
        
        # Create a copy for processing
        img = raw_frame.copy()
        
        # Add "Mode: HAND TRACKING" text
        cv2.putText(img, "Mode: HAND TRACKING", (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        # Add hand landmarks if mimic mode is active
        if mimic_ctrl.active:
            img = mimic_ctrl.draw_hand_overlay(img)
        
        # Encode to JPEG
        _, jpeg = cv2.imencode('.jpg', img)
        frame = jpeg.tobytes()
        
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n\r\n')
        time.sleep(0.03)

@app.route('/mimic_video_feed')
def mimic_video_feed():
    """Video feed endpoint for Mimic Mode page"""
    return Response(gen_mimic(global_camera),
                    mimetype='multipart/x-mixed-replace; boundary=frame')






def gen(camera):
    while True:
        frame = camera.get_frame()
        if frame is None:
            time.sleep(0.01)
            continue
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n\r\n')
        # Cap to ~30 FPS
        time.sleep(0.03)

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
    try:
        if global_camera.last_detection and len(global_camera.last_detection) > 0:
            return jsonify({
                "status": "found",
                "data": global_camera.last_detection,
                "count": len(global_camera.last_detection)
            })
        else:
            return jsonify({"status": "searching"})
    except Exception as e:
        print(f"[ERROR] /get_detection_result failed: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e), "status": "error"}), 500

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

@app.route('/emergency_stop', methods=['POST'])
def emergency_stop():
    """
    Emergency Stop: Immediately kills the backend process.
    """
    try:
        print("!!! EMERGENCY STOP TRIGGERED !!!")
        if robot:
             # Attempt to detach/stop servos if possible (though we are killing process immediately)
             pass
        
        # Return response before dying so frontend knows it worked
        response = jsonify({"status": "stopping", "message": "Backend shutting down immediately"})
        
        # Schedule death in 1 second to allow response to send
        import threading
        import os
        def kill_server():
            time.sleep(1)
            print("Force exiting...")
            os._exit(1)
            
        threading.Thread(target=kill_server).start()
        
        return response
    except Exception as e:
        return jsonify({"error": str(e)}), 500

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
            print(f"[DEBUG] Target object extracted from command: {target_object}")
            
            # TRIGGER VISUAL SERVOING
            # Use the global instance 'servoing_agent' initialized at start
            if servoing_agent:
                # Stop any existing servoing
                servoing_agent.stop()
                # Start new servoing
                servoing_agent.start(target_object)
                
                return jsonify({
                    "status": "success", 
                    "reply": f"🚀 Starting visual servoing for '{target_object}'!\n\n"
                             f"I'm now tracking the {target_object} using the X/Y axis controller.\n"
                             f"Say 'stop' to cancel.",
                    "plan": [],
                    "execution_log": []
                })
            else:
                 return jsonify({
                    "status": "error",
                    "reply": "⚠️ Visual Servoing Agent is not initialized.",
                    "plan": [],
                    "execution_log": []
                })
        
        # If no target object found or parsed
        return jsonify({
            "status": "success",
            "reply": reply if reply else "I understood the command, but couldn't identify a specific target object to track. Please say 'track the bottle'.",
            "plan": [],
            "execution_log": []
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    try:
        print("\n==================================================================")
        print(" 🤖 Robotic Arm Backend Started")
        print(" 📡 API Area: http://localhost:5000")
        print(" 📸 Vision Stats: http://localhost:5000/servoing_status")
        print(" ℹ️  To start Auto-Alignment (Visual Servoing):")
        print("    POST /start_servoing with {'target_object': 'red'}")
        print("==================================================================\n")
        app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
    finally:
        del global_camera
