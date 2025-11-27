import os
import json
from groq import Groq
from dotenv import load_dotenv
from prompts import SYSTEM_PROMPT

load_dotenv()

# Initialize Groq Client
# Ensure GROQ_API_KEY is set in your environment variables
try:
    client = Groq(
        api_key=os.environ.get("GROQ_API_KEY"),
    )
except Exception as e:
    print(f"Error initializing Groq client: {e}")
    client = None

def process_command(user_text, current_vision_state):
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
    Vision State: {json.dumps(current_vision_state)}
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
            model="llama-3.3-70b-versatile", # Updated to Llama 3.3 70B as requested
            temperature=0.1, # Low temperature for more deterministic/structured output
            response_format={"type": "json_object"}, # Enforce JSON mode
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
