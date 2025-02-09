from pathlib import Path
from agency_swarm import Agency, set_openai_key, set_openai_client
from ceo.ceo import CEO
from reporting_manager.reporting_manager import ReportingManager
from firebase_admin import initialize_app, credentials, firestore, get_app
from dotenv import load_dotenv
import openai
import os
import logging
from datetime import datetime
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
import time
from utils.firebase_db import get_threads_from_db, save_threads_to_db

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
    # Try to get existing app
    firebase_app = get_app()
    logger.info("Using existing Firebase app")
except ValueError:
    # Initialize new app if none exists
    service_account_key = Path(__file__).parent / "firebase-credentials.json"
    cred = credentials.Certificate(service_account_key)
    firebase_app = initialize_app(cred, name='retail-agency')
    logger.info("Initialized new Firebase app")

db = firestore.client()

# Initialize agents
ceo = CEO()
reporting_manager = ReportingManager()

# Create agency
agency = Agency(
    [
        ceo,  # CEO is the entry point
        [ceo, reporting_manager],  # CEO can communicate with Reporting Manager
    ],
    shared_instructions='./agency_manifesto.md'
)

def wait_for_run_completion(thread_id, run_id, max_wait_time=60):
    """Wait for an active run to complete."""
    start_time = time.time()
    while time.time() - start_time < max_wait_time:
        try:
            run = client.beta.threads.runs.retrieve(
                thread_id=thread_id,
                run_id=run_id
            )
            if run.status in ['completed', 'failed', 'cancelled']:
                return True
            time.sleep(2)
        except Exception as e:
            logger.error(f"Error checking run status: {str(e)}")
            return False
    return False

def generate_response(message: str, conversation_id: str) -> str:
    """Generate a response using the agency."""
    try:
        # Get completion from agency
        completion = agency.get_completion(message, yield_messages=False)
        return completion
    except Exception as e:
        logger.error(f"Error generating response: {str(e)}", exc_info=True)
        return "I apologize, but I encountered an error processing your request. Please try again in a moment."

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
        thread_ts = message.get("thread_ts", message_ts)  # Use message_ts as thread_ts for new threads
        
        # Create conversation_id for Firebase
        conversation_id = f"{channel_id}:{thread_ts}"
        
        logging.info(f"Processing message from user {user_id} in channel {channel_id}")
        
        if text:
            # Get response from agency
            response = generate_response(text, conversation_id)
            
            # Send response
            response_msg = say(text=response, thread_ts=thread_ts)
            
            # Get existing threads
            threads = get_threads_from_db(conversation_id)
            
            # Initialize threads dict if it doesn't exist
            if not threads:
                threads = {}
            
            # If this is a new thread or thread doesn't exist yet
            if thread_ts not in threads:
                threads[thread_ts] = {
                    'channel_id': channel_id,
                    'thread_ts': thread_ts,
                    'user_id': user_id,
                    'initial_message': text,
                    'messages': {},
                    'is_active': True,
                    'message_count': 0
                }
            
            # Ensure messages dict exists
            if 'messages' not in threads[thread_ts]:
                threads[thread_ts]['messages'] = {}
                
            threads[thread_ts]['messages'][message_ts] = {
                'content': text,
                'user_id': user_id,
                'timestamp': message_ts,
                'created_at': datetime.utcnow()
            }
            
            # Add bot response
            if response_msg:
                bot_msg_ts = response_msg['ts']
                threads[thread_ts]['messages'][bot_msg_ts] = {
                    'content': response,
                    'user_id': 'BOT',
                    'timestamp': bot_msg_ts,
                    'created_at': datetime.utcnow()
                }
            
            # Update thread metadata
            threads[thread_ts]['message_count'] = len(threads[thread_ts]['messages'])
            threads[thread_ts]['updated_at'] = datetime.utcnow()
            
            # Save updated threads
            save_threads_to_db(conversation_id, threads)
            
            logging.info("Message processed and saved successfully")

    except Exception as e:
        logger.error(f"Error processing message: {str(e)}", exc_info=True)
        # Notify user of error if appropriate
        say(text="Sorry, I encountered an error processing your message.", thread_ts=thread_ts)

def start_bot():
    """Initialize and start the Slack bot."""
    try:
        # Print startup message
        logger.info("=" * 50)
        logger.info("Starting Retail Management Agency Slack Bot...")
        logger.info(f"Bot started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 50)
        
        # Start the Socket Mode handler
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