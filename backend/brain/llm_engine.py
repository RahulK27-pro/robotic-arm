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
Your task is to classify the user's command into a specific INTENT and extract PARAMETERS.

**1. DETECT INTENT**
Classify the command into EXACTLY ONE of these categories:
- `PICK_ONLY`: User wants to grab an object but NOT place it immediately. (e.g., "Pick up the bottle", "Grab the red block")
- `PLACE_ONLY`: User wants to place the CURRENTLY HELD object. (e.g., "Place it down", "Put it on the table", "Place it near me")
- `PICK_AND_PLACE`: User wants to pick AND place in one go. (e.g., "Pick the bottle and put it on the right", "Give me the cup")
- `MOVE_BASE`: User wants to rotate the base manually. (e.g., "Move right 20 degrees", "Rotate left")
- `EXTEND`: User wants to reach out/forward manualy. (e.g. "Extend 10 degrees", "Reach out a bit", "Go forward")
- `RETRACT`: User wants to pull back manually. (e.g. "Retract 10 degrees", "Pull back", "Come back")

**2. EXTRACT PARAMETERS**
Return a JSON object with this structure:
{
    "intent": "PICK_ONLY" | "PLACE_ONLY" | "PICK_AND_PLACE" | "MOVE_BASE" | "EXTEND" | "RETRACT",
    "target_object": "string" or null, (Required for PICK intents)
    "params": {
        "modifier": "normal" | "near" | "far" | null, (For PLACE intents)
        "angle": integer or null, (For MOVE_BASE/EXTEND/RETRACT, in degrees)
        "direction": "left" | "right" | null (For MOVE_BASE)
    },
    "reply": "Brief confirmation message."
}

**RULES:**
- **target_object**: Extract the main object name (e.g. "bottle", "red block").
- **modifier**:
  - "near", "closer", "here" -> "near"
  - "far", "away", "there" -> "far"
  - default -> "normal"
- **MOVE_BASE**: If user says "Move right", direction="right". If "Move left", direction="left". Angle is the number.
- **EXTEND/RETRACT**: Extract the number of degrees/steps as "angle". Default to 10 if unspecified.
- **PICK_AND_PLACE**: Use this if the user specifies a destination OR implies a full transfer (e.g. "Give me...").

**EXAMPLES:**
1. "Pick up the red block" ->
   {"intent": "PICK_ONLY", "target_object": "red_block", "params": {}, "reply": "Picking up the red block."}

2. "Place it down near me" ->
   {"intent": "PLACE_ONLY", "target_object": null, "params": {"modifier": "near"}, "reply": "Placing it near you."}

3. "Move right 45 degrees" ->
   {"intent": "MOVE_BASE", "target_object": null, "params": {"angle": 45, "direction": "right"}, "reply": "Rotating base 45 degrees right."}

4. "Extend 15 degrees" ->
   {"intent": "EXTEND", "target_object": null, "params": {"angle": 15}, "reply": "Extending arm 15 degrees."}
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
