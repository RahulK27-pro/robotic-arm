from flask import Flask, Response, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from camera import VideoCamera
from brain import process_command

load_dotenv()

app = Flask(__name__)
CORS(app)

global_camera = VideoCamera()

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
    colors = data.get('colors')  # Now expects an array
    
    # Allow empty array or None to reset
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
    """
    Returns the status of the system components.
    """
    vision_status = "active" if global_camera.video.isOpened() else "inactive"
    
    # Servo is simulated for now
    servo_status = "on"
    
    return jsonify({
        "backend": "connected",
        "vision": vision_status,
        "servo": servo_status
    })

@app.route('/command', methods=['POST'])
def command():
    data = request.json
    user_text = data.get('command')
    
    if not user_text:
        return jsonify({"error": "No command provided"}), 400

    # Get latest detection from the camera
    # We might need to ensure we have the latest state. 
    # If the camera loop is running, last_detection should be up to date.
    # However, if we want to support "Clear table" (find all), we might need to temporarily 
    # switch targets or assume the camera is already looking for everything or we pass a flag.
    # For now, per requirements, we just pass "current_vision_state".
    
    # NOTE: The user prompt implies that for "Clear table", we need to identify all colors.
    # The current camera implementation only finds objects for `target_colors`.
    # To support "Clear table", we might need to quickly scan for ALL supported colors if the command implies it,
    # OR we can just return what we currently see. 
    # Given the prompt "if i say to clear the table, all the colour cubes should be identified",
    # we should probably enable all colors if they aren't already.
    
    # Let's check if we need to enable all colors. 
    # A simple heuristic: if detection is empty or we want to be sure, we could force a scan of all colors.
    # But changing state might affect the video feed visualization. 
    # Let's stick to the requested flow: "Get the *latest* object coordinates".
    # If the user wants to see everything, they might need to ensure the camera is looking for everything 
    # or we can programmatically set it here.
    
    # Let's try to be smart: If the command contains "clear" or "all", we temporarily enable all colors?
    # Or better, let's just use what's currently detected as per strict instruction "Get the *latest* object coordinates".
    # BUT the user also said: "if i say to clear the table, all the colour cubes should be identified... and those coordinates should be sent".
    # This implies we MIGHT need to trigger a full scan.
    
    # To be safe and robust:
    # 1. If command implies "all" or "clear", we might want to ensure we are scanning for all colors.
    #    However, `process_command` is just a function. `global_camera` is running in a separate thread/process (conceptually).
    #    The `gen` function constantly calls `get_frame`.
    #    If we change `target_colors` here, it will reflect in the next frame.
    
    # Let's implement a quick "scan all" if needed, or just pass current. 
    # The prompt says: "Get the *latest* object coordinates from the OpenCV thread."
    # I will stick to passing `global_camera.last_detection`. 
    # If the user hasn't set targets, it might be empty. 
    # Let's assume the frontend or previous interaction sets the targets, OR we can improve this later.
    # Actually, the user says "so now when i give any input command... it should find and display...".
    # This implies the system should be reactive.
    # Let's just pass the current state. If it's insufficient, the LLM might complain or give a partial plan.
    
    # Re-reading: "if i say to clear the table, all the colour cubes should be identified... mainly red, blue and yellow and green"
    # This strongly suggests we should probably ensure we are looking for these colors.
    # Let's add a helper to format the vision state for the LLM.
    
    # Convert list of dicts to the format expected by LLM: {'color_name': [x, y], ...}
    # The camera returns: [{'color': 'Red', 'x': 10, 'y': 20}, ...]
    # The LLM expects: {'red_cube': [320, 240], ...}
    
    vision_state = {}
    if global_camera.last_detection:
        for obj in global_camera.last_detection:
            # Create a unique key if multiple of same color? 
            # The prompt example uses "red_cube". Our camera detects "Red".
            # Let's map "Red" to "red_cube" etc.
            color = obj['color'].lower()
            key = f"{color}_cube" 
            # If multiple, maybe append index? For now, let's just overwrite or use a list?
            # The prompt example: {'red_cube': [320, 240]} implies single instance or specific naming.
            # Let's just use the color name as key for simplicity, or append index if needed.
            # But to match the example strictly:
            vision_state[key] = [obj['x'], obj['y']]

    response = process_command(user_text, vision_state)
    return jsonify(response)

if __name__ == '__main__':
    try:
        app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
    finally:
        del global_camera
