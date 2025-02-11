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
    def __init__(self):
        super().__init__(
            name="CEO",
            description=(
                "Retail Management Agency CEO responsible for client communication, "
                "task delegation, and coordinating with specialized agents like the ReportingManager "
                "for data analysis and insights. Processes and relays agent responses to users."
            ),
            instructions="./instructions.md",
            tools=[SlackCommunicator, TaskManager, GetDate, NotionPoster],
            temperature=0.5,
            max_prompt_tokens=25000
        )
    
    def  response(self, response):
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