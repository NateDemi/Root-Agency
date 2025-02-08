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
                "for data analysis and insights."
            ),
            instructions="./instructions.md",
            tools=[SlackCommunicator, TaskManager, GetDate, NotionPoster],
            temperature=0.5,
            max_prompt_tokens=25000
        )
        
    def _create_notion_report(self, title, data, insights=None, request_context=None):
        """Create a detailed Notion report with data and insights."""
        try:
            # Format the content
            content = f"## Request Context\n{request_context}\n\n" if request_context else ""
            content += f"## Generated at\n{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            
            # Add data section
            if isinstance(data, str):
                content += f"## Data\n{data}\n\n"
            elif isinstance(data, dict):
                content += "## Data\n"
                for key, value in data.items():
                    content += f"### {key}\n{value}\n\n"
            elif isinstance(data, list):
                content += "## Data\n"
                for item in data:
                    content += f"- {item}\n"
                content += "\n"
                
            # Add insights section
            if insights:
                content += "## Key Insights\n"
                if isinstance(insights, list):
                    for insight in insights:
                        content += f"- {insight}\n"
                else:
                    content += f"{insights}\n"
            
            # Create Notion page
            notion_poster = NotionPoster(
                title=title,
                content=content,
                tags=["report", "data_analysis"]
            )
            result = notion_poster.run()
            
            # Extract URL from result
            if "Direct URL:" in result:
                url = result.split("Direct URL:")[1].split()[0]
                return url
                
            return result
            
        except Exception as e:
            logger.error(f"Error creating Notion report: {str(e)}")
            return None
            
    def _format_data_response(self, data, notion_url=None):
        """Format the response message with data and optional Notion link."""
        response = ""
        
        # Add summary section
        if isinstance(data, dict) and "summary" in data:
            response += f"Summary:\n{data['summary']}\n\n"
            
        # Add key metrics if available
        if isinstance(data, dict) and "key_metrics" in data:
            response += "Key Metrics:\n"
            for metric, value in data["key_metrics"].items():
                response += f"- {metric}: {value}\n"
            response += "\n"
            
        # Add Notion link if available
        if notion_url:
            response += f"View the full report here: {notion_url}\n"
            
        return response.strip() 