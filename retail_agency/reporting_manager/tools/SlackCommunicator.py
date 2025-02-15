# reporting_manager/tools/SlackCommunicator.py
from agency_swarm.tools import BaseTool
from pydantic import Field
import os
from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import logging
from typing import Optional, Dict, Any
import json

load_dotenv()

slack_token = os.getenv("SLACK_BOT_TOKEN")

logger = logging.getLogger(__name__)

class SlackCommunicator(BaseTool):
    """
    A tool for sending inventory report notifications and updates to Slack channels.
    Handles posting report links, summaries, and updates about inventory status.
    """
    
    channel_id: str = Field(
        ..., description="The Slack channel ID where the report notification should be sent"
    )
    message: str = Field(
        ..., description="The message content containing report details and links"
    )
    thread_ts: Optional[str] = Field(
        None, description="The timestamp of the parent message to create a thread (optional)"
    )
    blocks: Optional[list] = Field(
        None, description="Optional Slack blocks for rich message formatting"
    )

    def _format_message(self) -> Dict[str, Any]:
        """Format the message payload with proper markdown and blocks if provided."""
        payload = {
            "channel": self.channel_id,
            "text": self.message,
            "mrkdwn": True
        }
        
        # Add thread_ts if provided
        if self.thread_ts:
            payload["thread_ts"] = self.thread_ts
            
        # Add blocks if provided
        if self.blocks:
            payload["blocks"] = self.blocks
            
        return payload

    def run(self) -> dict:
        """
        Sends a report notification to Slack and handles any threading requirements.
        Returns the response from the Slack API.
        """
        try:
            # Validate Slack token
            if not slack_token:
                error_msg = "SLACK_BOT_TOKEN not set in environment variables"
                logger.error(error_msg)
                return {"error": error_msg, "status": "error"}

            # Initialize Slack client
            client = WebClient(token=slack_token)
            
            # Format message payload
            msg_payload = self._format_message()
            
            # Log message being sent
            logger.info(f"Sending message to channel {self.channel_id}")
            if self.thread_ts:
                logger.info(f"Message is in thread: {self.thread_ts}")
            
            # Send message
            try:
                response = client.chat_postMessage(**msg_payload)
                logger.info("Message sent successfully")
                
                return {
                    "status": "success",
                    "ok": response["ok"],
                    "ts": response["ts"],
                    "channel": response["channel"]
                }
                
            except SlackApiError as slack_error:
                error_msg = f"Slack API Error: {str(slack_error)}"
                logger.error(error_msg)
                if slack_error.response["error"] == "channel_not_found":
                    return {
                        "status": "error",
                        "error": "Channel not found. Please check the channel ID.",
                        "details": str(slack_error)
                    }
                elif slack_error.response["error"] == "not_in_channel":
                    return {
                        "status": "error",
                        "error": "Bot is not in the channel. Please add the bot to the channel.",
                        "details": str(slack_error)
                    }
                else:
                    return {
                        "status": "error",
                        "error": error_msg,
                        "details": str(slack_error)
                    }
            
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                "status": "error",
                "error": error_msg,
                "details": str(e)
            }

if __name__ == "__main__":
    # Test the tool
    test_message = """📊 *Test Inventory Report*
Query: Show items with low stock

📈 *Google Sheets*: https://docs.google.com/spreadsheets/d/test
📝 *Notion Checklist*: https://notion.so/test-page

Found 10 matching items."""

    # Test with blocks
    test_blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "Inventory Report"
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": test_message
            }
        }
    ]

    tool = SlackCommunicator(
        channel_id=os.getenv("SLACK_CHANNEL_ID", "TEST_CHANNEL_ID"),
        message=test_message,
        blocks=test_blocks
    )
    
    result = tool.run()
    print(json.dumps(result, indent=2)) 