import re
from os import getenv
from pathlib import Path
import json
from typing import Dict, Any
from openai import OpenAI
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slack_bolt import App
from slack_bolt.adapter.fastapi import SlackRequestHandler
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv(Path(__file__).parent / ".env")

# Load settings
settings_path = Path(__file__).parent / "settings.json"
with open(settings_path) as f:
    settings = json.load(f)

# Initialize OpenAI clients
aiclient = OpenAI(api_key=getenv("OPENAI_API_KEY"))  # For message analysis
assistant_client = OpenAI(  # For assistant responses
    api_key=getenv("OPENAI_API_KEY"),
    default_headers={"OpenAI-Beta": "assistants=v1"}
)

# Initialize Slack app
app = App(
    token=getenv("SLACK_BOT_TOKEN"),
    signing_secret=getenv("SLACK_SIGNING_SECRET")
)
app_handler = SlackRequestHandler(app)
api = FastAPI()

# In-memory storage for testing
active_threads: Dict[str, Dict[str, Any]] = {}

def get_or_create_thread(conversation_id: str) -> Dict[str, Any]:
    """Get an existing thread or create a new one for the conversation."""
    if conversation_id not in active_threads:
        logger.info(f"Creating new thread for conversation {conversation_id}")
        
        # Create a new thread
        thread = assistant_client.beta.threads.create()
        
        # Store thread info
        active_threads[conversation_id] = {
            "thread_id": thread.id,
            "messages": []
        }
        
        logger.info(f"Created thread {thread.id} for conversation {conversation_id}")
    else:
        logger.info(f"Using existing thread for conversation {conversation_id}")
    
    return active_threads[conversation_id]

def generate_response(message: str, conversation_id: str) -> str:
    """Generate a response using OpenAI."""
    try:
        logger.info(f"Generating response for conversation {conversation_id}")
        logger.info(f"Input message: {message}")
        
        # Get or create thread
        thread_info = get_or_create_thread(conversation_id)
        thread_id = thread_info["thread_id"]
        
        # Add message to thread
        assistant_client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=message
        )
        
        # Create a run
        run = assistant_client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=settings["assistant_id"]
        )
        
        # Wait for run to complete
        while True:
            run_status = assistant_client.beta.threads.runs.retrieve(
                thread_id=thread_id,
                run_id=run.id
            )
            if run_status.status == 'completed':
                break
            elif run_status.status in ['failed', 'cancelled', 'expired']:
                raise Exception(f"Run failed with status: {run_status.status}")
        
        # Get messages
        messages = assistant_client.beta.threads.messages.list(thread_id=thread_id)
        
        # Get the latest assistant message
        for msg in messages.data:
            if msg.role == "assistant":
                response = msg.content[0].text.value
                break
        else:
            response = "No response generated"
        
        # Log the response
        logger.info(f"Generated response: {response}")
        
        return response
        
    except Exception as e:
        error_msg = f"Error generating response: {str(e)}"
        logger.error(error_msg)
        return f"I apologize, but I encountered an error: {str(e)}"

def is_response_required(message_input: str) -> bool:
    """Determine if a response is required for the message."""
    try:
        response = aiclient.chat.completions.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a helpful assistant responsible for analyzing slack chat messages. "
                        "You work as a part of AI agency that is helping clients automate their businesses."
                        "Your role within that agency is to help manager determine, if they should create "
                        "a new task for developers or not.\n"
                        "Your primary instructions are:\n"
                        "1. Take a chat message from Slack as an input.\n"
                        "2. Analyze the message and determine if user's message requires agency's "
                        "manager to schedule a new task. Specifically, look if contains any feedback, "
                        "has any issues regarding the product or new requirements\n"
                        "3. Clarifications or follow-up questions do not require task creation.\n"
                        "If a new task needs to be created, you need to respond with a single `True` word. "
                        "If it doesn't, respond with a single `False` word."
                    ),
                },
                {
                    "role": "user",
                    "content": message_input,
                },
            ],
            max_tokens=4000,
            temperature=0.0,
        )
        response_value = response.choices[0].message.content
        return "true" in response_value.lower()

    except Exception as e:
        logger.error(f"Error analyzing message: {str(e)}")
        return True  # Default to responding if there's an error

@api.post("/slack/events")
async def endpoint(req: Request):
    """Handle Slack events."""
    try:
        body = await req.json()
        
        # Handle Slack URL verification challenge
        if "challenge" in body:
            logger.info("Authorizing Slack endpoint")
            return JSONResponse(content={"challenge": body["challenge"]})
            
        # Handle other requests via SlackRequestHandler
        return await app_handler.handle(req)
        
    except Exception as e:
        logger.error(f"Error handling Slack event: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.event("app_mention")
@app.event("message")
def handle_message_events(event, say):
    """Handle incoming Slack messages."""
    try:
        # Filter out system messages
        if "user" not in event:
            return

        event_type = event["type"]
        user_id = event["user"]
        
        # Get user info
        user_info = app.client.users_info(user=user_id)
        workspace_id = app.client.auth_test()["team_id"]
        message_text = event.get("text", "")
        
        # Filter out messages that have mentions or coming from a manager
        if event_type != "app_mention":
            user_mentions = re.findall(r"<@U[A-Z0-9]+>", message_text)
            if workspace_id == user_info["user"]["team_id"] or user_mentions:
                return
        
        # Get user's real name
        real_name = user_info["user"]["profile"]["real_name"]
        message = f"{real_name}: {message_text}"
        
        # Check if response is required
        if event_type == "app_mention" or is_response_required(message):
            conversation_id = f"{event['channel']}:{event.get('thread_ts', event['ts'])}"
            response = generate_response(message, conversation_id)
            
            # Send response
            if "thread_ts" not in event:
                # Start new thread
                app.client.chat_postMessage(
                    channel=event["channel"],
                    text=response,
                    thread_ts=event["ts"]
                )
            else:
                # Reply in existing thread
                say(
                    text=response,
                    thread_ts=event["thread_ts"],
                    channel=event["channel"]
                )
            
    except Exception as e:
        logger.error(f"Error handling message: {e}")
        error_message = "I apologize, but I encountered an error processing your request."
        say(
            text=error_message,
            thread_ts=event.get("thread_ts", event["ts"]),
            channel=event["channel"]
        )

if __name__ == "__main__":
    import uvicorn
    
    print("\nRetail Assistant API Configuration")
    print("=================================")
    print("Starting server...")
    print("\nEndpoints:")
    print("- Slack Events URL: http://your-domain:8000/slack/events")
    print("\nConfiguration Steps:")
    print("1. Use ngrok to expose your local server:")
    print("   ngrok http 8000")
    print("\n2. Configure your Slack app:")
    print("   - Event Subscriptions URL: https://your-ngrok-url/slack/events")
    print("   - Subscribe to bot events: message.channels, app_mention")
    print("\nStarting server on port 8000...")
    
    uvicorn.run(api, host="0.0.0.0", port=8000)