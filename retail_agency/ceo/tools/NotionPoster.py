from agency_swarm.tools import BaseTool
from pydantic import Field
import os
from dotenv import load_dotenv
from notion_client import Client
import json
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

# Initialize Notion client with token from environment variables
notion_token = os.getenv("NOTION_TOKEN")
notion_database_id = os.getenv("NOTION_DATABASE_ID")

class NotionPoster(BaseTool):
    """
    A tool for creating and sharing Notion pages.
    Can create new pages in a specified database and return their URLs.
    """
    
    title: str = Field(
        ..., description="The title of the Notion page"
    )
    content: str = Field(
        ..., description="The content to post to Notion. Can include markdown formatting."
    )
    tags: list = Field(
        default=[], description="List of tags/categories for the page"
    )

    def run(self):
        """
        Creates a new page in Notion and returns its URLs.
        Returns both the direct page URL and a sharing link.
        """
        try:
            if not notion_token:
                return "Error: Notion token not found in environment variables."
            
            if not notion_database_id:
                return "Error: Notion database ID not found in environment variables."
            
            logger.info(f"Using Notion token: {notion_token[:10]}...")
            logger.info(f"Using database ID: {notion_database_id}")
            
            # Initialize Notion client
            notion = Client(auth=notion_token)
            
            # Test the connection
            try:
                db = notion.databases.retrieve(notion_database_id)
                logger.info("Successfully connected to Notion database")
                logger.info(f"Database title: {db.get('title', [{}])[0].get('text', {}).get('content', 'Untitled')}")
            except Exception as e:
                logger.error(f"Error connecting to database: {str(e)}")
                return f"Error connecting to database: {str(e)}"
            
            # Create page properties
            properties = {
                "title": {
                    "title": [
                        {
                            "text": {
                                "content": self.title
                            }
                        }
                    ]
                }
            }
            
            # Add tags if provided
            if self.tags:
                properties["Tags"] = {
                    "multi_select": [{"name": tag} for tag in self.tags]
                }
            
            # Create the page
            new_page = notion.pages.create(
                parent={"database_id": notion_database_id},
                properties=properties,
                children=[
                    {
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [
                                {
                                    "type": "text",
                                    "text": {"content": self.content}
                                }
                            ]
                        }
                    }
                ]
            )
            
            # Get the page ID and create URLs
            page_id = new_page["id"]
            workspace_id = db.get("workspace_id") or db.get("parent", {}).get("workspace_id")
            
            # Format URLs
            direct_url = f"https://notion.so/{page_id.replace('-', '')}"
            sharing_url = f"https://notion.so/{workspace_id}/{page_id.replace('-', '')}" if workspace_id else direct_url
            
            return f"""Successfully created Notion page!
Direct URL: {direct_url}
Sharing URL: {sharing_url}
Database: {db.get('title', [{}])[0].get('text', {}).get('content', 'Untitled')}"""
            
        except Exception as e:
            logger.error(f"Error creating Notion page: {str(e)}", exc_info=True)
            return f"Error creating Notion page: {str(e)}"

if __name__ == "__main__":
    # Test the tool
    tool = NotionPoster(
        title="Test Page with Sharing",
        content="This is a test page created by the NotionPoster tool with sharing enabled.",
        tags=["test", "sharing"]
    )
    print(tool.run()) 