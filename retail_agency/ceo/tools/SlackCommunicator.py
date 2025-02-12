# ceo/tools/SlackCommunicator.py
from agency_swarm.tools import BaseTool
from pydantic import Field
import os
from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import logging

load_dotenv()

slack_token = os.getenv("SLACK_BOT_TOKEN")

logger = logging.getLogger(__name__)

class SlackCommunicator(BaseTool):
    """
    A tool for handling Slack communications, including sending messages, creating threads,
    and managing conversations in a retail management context.
    """
    
    channel_id: str = Field(
        ..., description="The Slack channel ID where the message should be sent"
    )
    message: str = Field(
        ..., description="The message content to be sent"
    )
    thread_ts: str = Field(
        None, description="The timestamp of the parent message to create a thread (optional)"
    )

    def run(self) -> dict:
        """
        Sends a message to Slack and handles any threading requirements.
        Returns the response from the Slack API.
        """
        try:
            client = WebClient(token=slack_token)
            
            # Prepare message payload
            msg_payload = {
                "channel": self.channel_id,
                "text": self.message
            }
            
            # Add thread_ts if provided
            if self.thread_ts:
                msg_payload["thread_ts"] = self.thread_ts
                
            # Send message
            response = client.chat_postMessage(**msg_payload)
            
            return {
                "ok": response["ok"],
                "ts": response["ts"],
                "channel": response["channel"]
            }
            
        except SlackApiError as e:
            logger.error(f"Error sending message to Slack: {str(e)}")
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            return {"error": str(e)}

if __name__ == "__main__":
    # Test the tool
    tool = SlackCommunicator(
        channel_id="TEST_CHANNEL_ID",
        message="This is a test message from the Retail Management Agency.",
    )
    print(tool.run()) 