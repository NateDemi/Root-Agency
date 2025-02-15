from agency_swarm import Agent
from .tools.SlackCommunicator import SlackCommunicator
from .tools.TaskManager import TaskManager
from .tools.GetDate import GetDate
from .tools.NotionPoster import NotionPoster
import json
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class CEO(Agent):
    """
    CEO Agent - Entry point for the retail assistant agency.
    Responsible for understanding user requests and delegating to appropriate agents.
    """
    
    def __init__(self):
        super().__init__(
            name="CEO",
            description=(
                "I am the CEO of this retail assistant agency. "
                "I understand your business needs and coordinate with our ReportingManager "
                "to provide you with accurate data and insights about your inventory and sales. "
                "I ensure you get the information you need in the format that works best for you."
            ),
            instructions="./instructions.md",
            tools=[],  # CEO doesn't need tools as it delegates to ReportingManager
            temperature=0.5,
            model="gpt-4"
        )

    def handle_response(self, response):
        """Process responses from other agents before relaying to user."""
        try:
            if isinstance(response, dict):
                # Handle ReportingManager response
                if "natural_response" in response:
                    natural_response = response["natural_response"]
                    total_rows = response.get("total_rows", 0)
                    files = response.get("files", {})
                    
                    # Format response for user
                    formatted_response = [
                        natural_response,
                        f"\nAdditional Details:",
                        f"- Total items found: {total_rows}"
                    ]
                    
                    # Add file information if available
                    if files.get("csv"):
                        formatted_response.append(f"- Full results saved to: {files['csv']}")
                    
                    return "\n".join(formatted_response)
                    
            # Default to returning the original response
            return str(response)
            
        except Exception as e:
            logger.error(f"Error processing agent response: {str(e)}")
            return str(response)

if __name__ == "__main__":
    # Test the CEO agent
    ceo = CEO()
    print("CEO agent initialized successfully")