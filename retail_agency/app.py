import os
import logging
from datetime import datetime
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from agency_swarm import Agency
from ceo.ceo import CEO
from reporting_manager.reporting_manager import ReportingManager
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Initialize the Slack Bolt app
app = App(token=os.environ["SLACK_BOT_TOKEN"])

def create_agency():
    """Create and return a new instance of the Agency."""
    logging.info("Creating new agency instance...")
    ceo = CEO()
    reporting_manager = ReportingManager()
    
    agency = Agency(
        agency_chart=[
            ceo,  # CEO will be the entry point
            [ceo, reporting_manager],  # CEO can communicate with Reporting Manager
        ],
        shared_instructions="""You are a helpful assistant that can get dates and create Notion pages. 
When asked about dates:
1. Get the current date using GetDate
2. Create a Notion page with a descriptive title (e.g., "Daily Update - February 8, 2025")
3. Use NotionPoster to create the page with the title and date information
4. In your response:
   - Tell the current date
   - Format the Notion URL as a clickable link using Slack's format: "<URL|TITLE>"
   - Your response should look like: "Today's date is [DATE]. View the note here: <URL|TITLE>"

Make sure to use descriptive titles for the Notion pages and include them in the link text.""",
        temperature=0.5,
        max_prompt_tokens=25000
    )
    logging.info("Agency created successfully")
    return agency

@app.message()
def handle_message(message, say):
    """Handle incoming messages."""
    try:
        # Ignore bot messages
        if "bot_id" in message:
            return

        user_id = message.get("user")
        channel_id = message.get("channel")
        text = message.get("text", "")
        thread_ts = message.get("thread_ts", message.get("ts"))

        logging.info(f"Processing message from user {user_id} in channel {channel_id}")
        logging.info(f"Message content: {text}")

        if text:
            logging.info(f"Received message: {text[:20]}...")
            
            # Create a new agency instance for this interaction
            agency = create_agency()
            
            logging.info("Getting response from agency...")
            # Use the agency's get_completion method to handle the message
            response = agency.get_completion(
                message=text,
                yield_messages=False,
                verbose=True
            )
            
            # Send the response back to Slack
            say(
                text=response,
                thread_ts=thread_ts
            )
            logging.info("Response sent successfully")

    except Exception as e:
        logging.error(f"Error processing message: {str(e)}")
        logging.error("Full traceback:", exc_info=True)
        # Send error message
        say(
            text="I apologize, but I encountered an error processing your request. Please try again.",
            thread_ts=thread_ts
        )

def start_bot():
    """Initialize and start the Slack bot."""
    try:
        # Print startup message
        logging.info("=" * 50)
        logging.info("Starting Retail Management Agency Slack Bot...")
        logging.info(f"Bot started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logging.info("=" * 50)
        
        # Start the Socket Mode handler
        handler = SocketModeHandler(
            app=app,
            app_token=os.environ["SLACK_APP_TOKEN"]
        )
        handler.start()
        
    except Exception as e:
        logging.error(f"Error starting bot: {str(e)}")
        raise

if __name__ == "__main__":
    start_bot() 