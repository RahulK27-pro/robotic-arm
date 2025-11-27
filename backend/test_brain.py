import os
import json
from brain import process_command

# Mock data
mock_vision_state = {
    "red_cube": [320, 240],
    "blue_cube": [100, 100]
}

mock_command = "Put red on blue"

print("--- Testing Brain Module ---")
print(f"Command: {mock_command}")
print(f"Vision State: {mock_vision_state}")

# Check if API key is set
if not os.environ.get("GROQ_API_KEY"):
    print("\n[WARNING] GROQ_API_KEY not found in environment variables.")
    print("The brain module will return an error.")

response = process_command(mock_command, mock_vision_state)

print("\n--- Response ---")
print(json.dumps(response, indent=2))

if response.get("plan"):
    print("\n[SUCCESS] Plan generated successfully.")
else:
    print("\n[INFO] No plan generated (or error occurred).")
