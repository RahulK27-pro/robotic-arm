import requests
import json

def test_move():
    url = "http://localhost:5000/process_command"
    
    # Command to move to a specific position
    payload = {
        "command": "move the robot to the right" 
        # The LLM will interpret this and generate angles. 
        # Or we can try to force a move if we had a direct endpoint, 
        # but process_command is the main one.
    }
    
    print(f"🚀 Sending command to {url}...")
    try:
        response = requests.post(url, json=payload)
        print(f"Status Code: {response.status_code}")
        print("Response:")
        print(json.dumps(response.json(), indent=2))
        print("\n👉 NOW CHECK THE TERMINAL WHERE 'python app.py' IS RUNNING!")
        print("   You should see: '📥 Arduino Reply: ...'")
    except Exception as e:
        print(f"❌ Failed to contact backend: {e}")

if __name__ == "__main__":
    test_move()
