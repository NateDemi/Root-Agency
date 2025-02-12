import os
import sys
from pathlib import Path
from agency_swarm import Agency, set_openai_key, set_openai_client
from retail_agency import ReportingManager, CEO
from firebase_admin import initialize_app, credentials, firestore, get_app
from dotenv import load_dotenv
import openai
import logging
from datetime import datetime
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from utils.firebase_db import get_threads_from_db, save_threads_to_db
from retail_agency.ceo.tools.SlackCommunicator import SlackCommunicator

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

# Configure logging
logging.basicConfig(
    filename='retail_agency_bot.log',
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv(Path(__file__).parent / ".env")

# Configure OpenAI
set_openai_key(os.environ["OPENAI_API_KEY"])
client = openai.OpenAI(
    api_key=os.environ["OPENAI_API_KEY"],
    max_retries=10,
    default_headers={"OpenAI-Beta": "assistants=v2"}
)
set_openai_client(client)

# Initialize Firebase
try:
    firebase_app = get_app()
    logger.info("Using existing Firebase app")
except ValueError:
    service_account_key = Path(__file__).parent / "firebase-credentials.json"
    cred = credentials.Certificate(service_account_key)
    firebase_app = initialize_app(cred, name='retail-agency')
    logger.info("Initialized new Firebase app")

db = firestore.client()

# Initialize agents
ceo = CEO()
reporting_manager = ReportingManager()

# Create agency with bidirectional communication
agency = Agency(
    [
        ceo,  # CEO is the entry point for user communication
        [ceo, reporting_manager],  # CEO can initiate communication with Reporting Manager
        [reporting_manager, ceo],  # Reporting Manager can respond back to CEO
    ],
    shared_instructions='./agency_manifesto.md',
    temperature=0.5,
    max_prompt_tokens=25000
)

def generate_response(message: str, channel_id: str, thread_ts: str = None) -> tuple:
    """Generate and send a response using the agency."""
    try:
        # Get completion from agency
        response = agency.get_completion(message)
        
        # Process response through CEO
        formatted_response = ceo.handle_response(response)
        
        # Create SlackCommunicator instance
        slack_tool = SlackCommunicator(
            channel_id=channel_id,
            message=formatted_response,
            thread_ts=thread_ts
        )
        
        # Send response using CEO's SlackCommunicator tool
        slack_response = slack_tool.run()
        
        return formatted_response, slack_response
        
    except Exception as e:
        logger.error(f"Error generating response: {str(e)}", exc_info=True)
        error_msg = "I apologize, but I encountered an error processing your request. Please try again."
        
        try:
            slack_tool = SlackCommunicator(
                channel_id=channel_id,
                message=error_msg,
                thread_ts=thread_ts
            )
            slack_response = slack_tool.run()
        except Exception as slack_error:
            logger.error(f"Error sending error message: {str(slack_error)}")
            
        return error_msg, None

# Initialize the Slack Bolt app
app = App(token=os.environ["SLACK_BOT_TOKEN"])

@app.message()
def handle_message(message, say):
    """Handle incoming messages."""
    try:
        # Ignore bot messages
        if message.get("bot_id"):
            return

        channel_id = message["channel"]
        user_id = message["user"]
        text = message["text"]
        message_ts = message["ts"]
        thread_ts = message.get("thread_ts", message_ts)
        
        # Create conversation_id for Firebase
        conversation_id = f"{channel_id}:{thread_ts}"
        
        logging.info(f"Processing message from user {user_id} in channel {channel_id}")
        
        if text:
            # Generate and send response
            response, slack_response = generate_response(text, channel_id, thread_ts)
            
            # Initialize thread data structure
            thread_data = {
                'channel_id': channel_id,
                'thread_ts': thread_ts,
                'user_id': user_id,
                'initial_message': text,
                'is_active': True,
                'message_count': 1,
                'messages': {
                    message_ts: {
                        'content': text,
                        'user_id': user_id,
                        'timestamp': message_ts,
                        'created_at': datetime.utcnow()
                    }
                }
            }
            
            # Add bot response if successful
            if response:
                response_ts = str(datetime.utcnow().timestamp())
                thread_data['messages'][response_ts] = {
                    'content': response,
                    'user_id': 'BOT',
                    'timestamp': response_ts,
                    'created_at': datetime.utcnow()
                }
                thread_data['message_count'] = len(thread_data['messages'])
            
            # Create threads dictionary
            threads = {thread_ts: thread_data}
            
            # Save threads
            save_threads_to_db(conversation_id, threads)
            
            logging.info("Message processed and saved successfully")

    except Exception as e:
        logger.error(f"Error processing message: {str(e)}", exc_info=True)
        try:
            slack_communicator = next(
                (tool for tool in ceo.tools if tool.__class__.__name__ == 'SlackCommunicator'),
                None
            )
            if slack_communicator:
                slack_communicator(
                    channel_id=channel_id,
                    message="Sorry, I encountered an error processing your message.",
                    thread_ts=thread_ts
                ).run()
        except Exception as slack_error:
            logger.error(f"Error sending error message: {str(slack_error)}")
            say(text="Sorry, I encountered an error processing your message.", thread_ts=thread_ts)

def start_bot():
    """Initialize and start the Slack bot."""
    try:
        logger.info("=" * 50)
        logger.info("Starting Retail Management Agency Slack Bot...")
        logger.info(f"Bot started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 50)
        
        handler = SocketModeHandler(
            app=app,
            app_token=os.environ["SLACK_APP_TOKEN"]
        )
        handler.start()
        
    except Exception as e:
        logger.error(f"Error starting bot: {str(e)}")
        raise

if __name__ == "__main__":
    start_bot()