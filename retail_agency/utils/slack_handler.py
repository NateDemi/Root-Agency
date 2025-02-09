from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
import os
import logging
from typing import Optional, Dict, Any
from pathlib import Path
from agency_swarm import Agency
from ..agency import generate_response

logger = logging.getLogger(__name__)

class SlackEventHandler:
    def __init__(self):
        self.app = App(token=os.environ["SLACK_BOT_TOKEN"])
        self._setup_event_handlers()

    def _setup_event_handlers(self):
        """Set up all Slack event handlers."""
        
        @self.app.event("message")
        def handle_message(event, say):
            """Handle incoming messages."""
            try:
                # Ignore bot messages
                if event.get("bot_id"):
                    return

                channel_id = event["channel"]
                user_id = event["user"]
                message = event["text"]
                message_ts = event["ts"]
                thread_ts = event.get("thread_ts", message_ts)  # Use message_ts as thread_ts for new threads
                
                # Create conversation_id for Firebase
                conversation_id = f"{channel_id}:{thread_ts}"

                # Process the message using Agency
                response = generate_response(message, conversation_id)

                # Send response
                say(text=response, thread_ts=thread_ts)

            except Exception as e:
                logger.error(f"Error handling message event: {str(e)}", exc_info=True)
                # Notify user of error if appropriate
                say(text="Sorry, I encountered an error processing your message.", thread_ts=thread_ts)

    def start(self):
        """Start the Slack event handler."""
        try:
            handler = SocketModeHandler(
                app=self.app,
                app_token=os.environ["SLACK_APP_TOKEN"]
            )
            logger.info("Starting Slack event handler...")
            handler.start()
        except Exception as e:
            logger.error(f"Failed to start Slack event handler: {str(e)}")
            raise

if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Start the event handler
    handler = SlackEventHandler()
    handler.start() 