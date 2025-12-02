import os
import json
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# Initialize Groq Client
try:
    client = Groq(
        api_key=os.environ.get("GROQ_API_KEY"),
    )
except Exception as e:
    print(f"Error initializing Groq client: {e}")
    client = None

SYSTEM_PROMPT = """
You are the brain of a 6-DOF robotic arm.
Your task is to convert natural language commands into a structured JSON plan.
You will receive:
1. A user command (e.g., "Pick the red block and put it on the blue block").
2. A list of visible objects with their coordinates (e.g., {"red_block": [10, 20, 0], "blue_block": [30, 40, 0]}).

You must return a JSON object with the following structure:
{
    "plan": [
        {
            "action": "move",
            "target": [x, y, z],
            "description": "Moving to red block"
        },
        {
            "action": "grip",
            "angle": 45,
            "description": "Opening gripper"
        },
        ...
    ],
    "reply": "I am picking up the red block."
}

Rules:
- Return ONLY JSON.
- If the user provides explicit coordinates (e.g., "at 10, 20, 5"), use those coordinates directly.
- If no coordinates are provided, look for the object in the vision state.
- If the object is not found and no coordinates are provided, return a polite error in the "reply" field and an empty "plan".
- Assume z=0 is the table surface. A safe travel height is z=10.
- "Pick" involves: 
    1. Move to object coordinates (x, y, z).
    2. Grip with angle 45 (Open).
    3. Grip with angle 30 (Close to grab).
    4. Move to (x, y, z + 10) (Lift).
- "Place" involves: 
    1. Move to target coordinates (x, y, z + 10) (Approach from above).
    2. Move to target coordinates (x, y, z) (Lower).
    3. Grip with angle 90 (Open/Release).
    4. Move to target coordinates (x, y, z + 10) (Lift away).
"""

def process_command(user_text, vision_state):
    """
    Sends the user command and current vision state to the Groq API.
    Returns the parsed JSON plan and reply.
    """
    if not client:
        return {
            "plan": [],
            "reply": "Error: Groq client not initialized. Please check your API key."
        }

    # Construct the user message
    user_message = f"""
    Command: "{user_text}"
    Vision State: {json.dumps(vision_state)}
    """

    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": user_message,
                }
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.1,
            response_format={"type": "json_object"},
        )

        response_content = chat_completion.choices[0].message.content
        
        # Parse the JSON response
        try:
            parsed_response = json.loads(response_content)
            return parsed_response
        except json.JSONDecodeError:
            print(f"Failed to parse JSON from LLM: {response_content}")
            return {
                "plan": [],
                "reply": "Error: The robot's brain returned an invalid response format."
            }

    except Exception as e:
        print(f"Error calling Groq API: {e}")
        return {
            "plan": [],
            "reply": f"Error processing command: {str(e)}"
        }
