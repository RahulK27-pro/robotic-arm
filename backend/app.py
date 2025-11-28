from flask import Flask, Response, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from camera import VideoCamera
from brain.llm_engine import process_command
from brain.kinematics import solve_angles
from hardware.robot_driver import RobotArm
import traceback

load_dotenv()

app = Flask(__name__)
CORS(app)

global_camera = VideoCamera()
robot = RobotArm(simulation_mode=True)

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

        # 1. Prepare Vision State
        vision_state = {}
        if global_camera.last_detection:
            for obj in global_camera.last_detection:
                color = obj['color'].lower()
                key = f"{color}_cube"
                # Prefer CM coordinates if available, else pixel
                if 'cm_x' in obj:
                    vision_state[key] = [obj['cm_x'], obj['cm_y'], 0] # Assume z=0 for table
                else:
                    vision_state[key] = [obj['x'], obj['y'], 0] # Fallback to pixels (will need calibration)

        # 2. Call LLM
        llm_response = process_command(user_text, vision_state)
        plan = llm_response.get("plan", [])
        reply = llm_response.get("reply", "")

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
                        
                        # Move Robot
                        robot.move_to(angles)
                        
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
                # Handle gripper logic if needed
                simulated_execution.append({
                    "step": step,
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
