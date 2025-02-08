from agency_swarm.tools import BaseTool
from pydantic import Field
import os
from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

load_dotenv()

slack_token = os.getenv("SLACK_BOT_TOKEN")

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

    def run(self):
        """
        Sends a message to Slack and handles any threading requirements.
        Returns the response from the Slack API.
        """
        try:
            client = WebClient(token=slack_token)
            
            # Prepare message payload
            message_payload = {
                "channel": self.channel_id,
                "text": self.message,
            }
            
            # Add thread_ts if it's a reply
            if self.thread_ts:
                message_payload["thread_ts"] = self.thread_ts
            
            # Send message
            response = client.chat_postMessage(**message_payload)
            
            return f"Message sent successfully. Timestamp: {response['ts']}"
            
        except SlackApiError as e:
            return f"Error sending message: {str(e)}"

if __name__ == "__main__":
    # Test the tool
    tool = SlackCommunicator(
        channel_id="TEST_CHANNEL_ID",
        message="This is a test message from the Retail Management Agency.",
    )
    print(tool.run()) 