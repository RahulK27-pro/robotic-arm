from flask import Flask, Response, request, jsonify
from flask_cors import CORS
from camera import VideoCamera

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

if __name__ == '__main__':
    try:
        app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
    finally:
        del global_camera
