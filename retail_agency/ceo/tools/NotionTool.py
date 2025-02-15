from agency_swarm.tools import BaseTool
from pydantic import Field
import os
from dotenv import load_dotenv
from notion_client import Client
import logging
from typing import Optional, Dict, Any, List, Union
from datetime import datetime
import random

load_dotenv()

# Verify environment variables
notion_api_key = os.getenv("NOTION_API_KEY")
notion_db_id = os.getenv("NOTION_INVENTORY_DB_ID")

if not notion_api_key or not notion_db_id:
    raise ValueError(
        "Missing required environment variables. "
        "Please ensure NOTION_API_KEY and NOTION_INVENTORY_DB_ID are set in your .env file."
    )

logger = logging.getLogger(__name__)
notion = Client(auth=notion_api_key)

class NotionTool(BaseTool):
    """
    Tool for creating and updating Notion pages with different schemas and content types.
    Supports multiple block types: paragraphs, checklists, tables, callouts, headings, etc.
    """
    
    database_id: str = Field(
        ..., 
        description="The ID of the Notion database to create/update page in"
    )
    
    title: str = Field(
        ..., 
        description="Title of the Notion page"
    )
    
    content: Union[str, List[str], Dict[str, Any]] = Field(
        ..., 
        description="Content to add to the page"
    )
    
    schema_type: str = Field(
        ..., 
        description="Type of schema to use (e.g., 'inventory', 'sales', 'report')"
    )
    
    page_id: Optional[str] = Field(
        None, 
        description="Optional page ID if updating existing page"
    )
    
    properties: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional properties based on the schema"
    )
    
    content_type: str = Field(
        "paragraph",
        description="Type of content block to create (paragraph, checklist, table, callout, heading, toggle, bullet, numbered)"
    )
    
    heading_level: Optional[int] = Field(
        1,
        description="Heading level (1, 2, or 3) when content_type is 'heading'"
    )
    
    callout_icon: Optional[str] = Field(
        None,
        description="Emoji icon for callout blocks (e.g., '💡', '⚠️', '📝')"
    )

    def run(self) -> dict:
        """Create or update a Notion page with the specified schema."""
        try:
            # Get schema configuration
            schema_config = self._get_schema_config(self.schema_type)
            
            # Prepare page properties
            page_properties = self._prepare_properties(schema_config)
            
            # Prepare content blocks
            content_blocks = self._prepare_content_blocks()
            
            if self.page_id:
                # Update existing page
                response = notion.pages.update(
                    page_id=self.page_id,
                    properties=page_properties
                )
                
                # Update content
                notion.blocks.children.append(
                    block_id=self.page_id,
                    children=content_blocks
                )
                
                logger.info(f"Updated Notion page: {self.page_id}")
                return {
                    "status": "updated",
                    "page_id": self.page_id,
                    "url": response["url"],
                    "title": self.title
                }
            else:
                # Create new page
                response = notion.pages.create(
                    parent={"database_id": self.database_id},
                    properties=page_properties,
                    children=content_blocks
                )
                
                logger.info(f"Created new Notion page: {response['id']}")
                return {
                    "status": "created",
                    "page_id": response["id"],
                    "url": response["url"],
                    "title": self.title
                }

        except Exception as e:
            logger.error(f"Error with Notion operation: {str(e)}")
            raise

    def _get_schema_config(self, schema_type: str) -> Dict[str, Any]:
        """Get schema configuration based on type."""
        schemas = {
            "inventory": {
                "required_properties": ["Title", "Tags", "Created time", "Last edited time"],
                "property_types": {
                    "Title": "title",
                    "Tags": "multi_select",
                    "Created time": "created_time",
                    "Last edited time": "last_edited_time"
                }
            },
            "sales": {
                "required_properties": ["Period", "Revenue", "Status"],
                "property_types": {
                    "Period": "date",
                    "Revenue": "number",
                    "Status": "select"
                }
            },
            "report": {
                "required_properties": ["Type", "Date", "Department"],
                "property_types": {
                    "Type": "select",
                    "Date": "date",
                    "Department": "select"
                }
            }
        }
        
        return schemas.get(schema_type, {})

    def _prepare_properties(self, schema_config: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare page properties based on schema configuration."""
        # Title is required and must be in correct format
        properties = {
            "Title": {
                "title": [{"text": {"content": self.title}}]
            }
        }
        
        # Handle Tags if provided
        if self.properties and "Tags" in self.properties:
            tags = self.properties["Tags"]
            if isinstance(tags, list):
                properties["Tags"] = {
                    "multi_select": [{"name": tag} for tag in tags]
                }
        
        return properties

    def _format_property(self, value: Any, prop_type: str) -> Dict[str, Any]:
        """Format property value based on Notion property type."""
        if prop_type == "select":
            return {"select": {"name": str(value)}}
        elif prop_type == "multi_select":
            return {"multi_select": [{"name": name} for name in value]}
        elif prop_type == "date":
            if isinstance(value, datetime):
                date_str = value.isoformat()
            else:
                date_str = value
            return {"date": {"start": date_str}}
        elif prop_type == "number":
            return {"number": float(value)}
        else:
            return {"rich_text": [{"text": {"content": str(value)}}]}

    def _prepare_content_blocks(self) -> List[Dict[str, Any]]:
        """Prepare content blocks based on content_type."""
        content_handlers = {
            "checklist": self._create_checklist_blocks,
            "table": self._create_table_blocks,
            "paragraph": self._create_paragraph_blocks,
            "callout": self._create_callout_blocks,
            "heading": self._create_heading_blocks,
            "toggle": self._create_toggle_blocks,
            "bullet": self._create_bullet_blocks,
            "numbered": self._create_numbered_blocks,
            "divider": self._create_divider_block
        }
        
        handler = content_handlers.get(self.content_type, self._create_paragraph_blocks)
        return handler()

    def _create_checklist_blocks(self) -> List[Dict[str, Any]]:
        """Create to-do list blocks from content."""
        blocks = []
        
        # Handle both string and list inputs
        items = self.content if isinstance(self.content, list) else self.content.split('\n')
        
        for item in items:
            if item.strip():  # Skip empty lines
                blocks.append({
                    "object": "block",
                    "type": "to_do",
                    "to_do": {
                        "rich_text": [{"type": "text", "text": {"content": item.strip()}}],
                        "checked": False
                    }
                })
        
        return blocks

    def _create_table_blocks(self) -> List[Dict[str, Any]]:
        """Create table blocks from content."""
        if not isinstance(self.content, dict) or 'headers' not in self.content or 'rows' not in self.content:
            raise ValueError("Table content must be a dict with 'headers' and 'rows' keys")
            
        table_width = len(self.content['headers'])
        blocks = [
            {
                "object": "block",
                "type": "table",
                "table": {
                    "table_width": table_width,
                    "has_column_header": True,
                    "has_row_header": False,
                    "children": []
                }
            }
        ]
        
        # Add header row
        header_cells = [{"type": "text", "text": {"content": header}} for header in self.content['headers']]
        blocks[0]["table"]["children"].append({
            "type": "table_row",
            "table_row": {"cells": header_cells}
        })
        
        # Add data rows
        for row in self.content['rows']:
            row_cells = [{"type": "text", "text": {"content": str(cell)}} for cell in row]
            blocks[0]["table"]["children"].append({
                "type": "table_row",
                "table_row": {"cells": row_cells}
            })
        
        return blocks

    def _create_paragraph_blocks(self) -> List[Dict[str, Any]]:
        """Create paragraph blocks from content."""
        return [
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": str(self.content)}}]
                }
            }
        ]

    def _create_bullet_blocks(self) -> List[Dict[str, Any]]:
        """Create bullet list blocks from content."""
        blocks = []
        items = self.content if isinstance(self.content, list) else self.content.split('\n')
        
        for item in items:
            if item.strip():
                blocks.append({
                    "object": "block",
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {
                        "rich_text": [{"type": "text", "text": {"content": item.strip()}}]
                    }
                })
        
        return blocks

    def _create_numbered_blocks(self) -> List[Dict[str, Any]]:
        """Create numbered list blocks from content."""
        blocks = []
        items = self.content if isinstance(self.content, list) else self.content.split('\n')
        
        for item in items:
            if item.strip():
                blocks.append({
                    "object": "block",
                    "type": "numbered_list_item",
                    "numbered_list_item": {
                        "rich_text": [{"type": "text", "text": {"content": item.strip()}}]
                    }
                })
        
        return blocks

    def _create_callout_blocks(self) -> List[Dict[str, Any]]:
        """Create callout blocks with optional icon."""
        return [{
            "object": "block",
            "type": "callout",
            "callout": {
                "rich_text": [{"type": "text", "text": {"content": str(self.content)}}],
                "icon": {"type": "emoji", "emoji": self.callout_icon or "💡"}
            }
        }]

    def _create_heading_blocks(self) -> List[Dict[str, Any]]:
        """Create heading blocks with specified level."""
        heading_type = f"heading_{self.heading_level}"
        return [{
            "object": "block",
            "type": heading_type,
            heading_type: {
                "rich_text": [{"type": "text", "text": {"content": str(self.content)}}]
            }
        }]

    def _create_toggle_blocks(self) -> List[Dict[str, Any]]:
        """Create toggle blocks from content."""
        if not isinstance(self.content, dict) or 'summary' not in self.content or 'details' not in self.content:
            raise ValueError("Toggle content must be a dict with 'summary' and 'details' keys")
            
        return [{
            "object": "block",
            "type": "toggle",
            "toggle": {
                "rich_text": [{"type": "text", "text": {"content": self.content['summary']}}],
                "children": [
                    {
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [{"type": "text", "text": {"content": self.content['details']}}]
                        }
                    }
                ]
            }
        }]

    def _create_divider_block(self) -> List[Dict[str, Any]]:
        """Create a divider block."""
        return [{
            "object": "block",
            "type": "divider",
            "divider": {}
        }]

    def _get_database_schema(self) -> Dict[str, str]:
        """Get the actual schema from the Notion database."""
        try:
            database = notion.databases.retrieve(self.database_id)
            schema = {}
            for prop_name, prop_data in database['properties'].items():
                schema[prop_name] = prop_data['type']
            logger.info(f"Database schema: {schema}")
            return schema
        except Exception as e:
            logger.error(f"Error getting database schema: {str(e)}")
            raise


if __name__ == "__main__":
    try:
        # Test creating a page with multiple block types
        test_tool = NotionTool(
            database_id=os.getenv("NOTION_INVENTORY_DB_ID"),
            title="Test Inventory Report",
            content=[
                "Check MacBook Pro inventory",
                "Update iPhone stock count",
                "Review iPad availability"
            ],
            content_type="checklist",  # This will create checkboxes
            schema_type="inventory",
            properties={
                "Title": {"title": [{"text": {"content": "Test Inventory Report"}}]},
                "Tags": ["Test", "Inventory"]
            }
        )
        
        # Run the test and print results
        result = test_tool.run()
        print("\nTest Results:")
        print(f"Status: {result['status']}")
        print(f"Page URL: {result['url']}")
        print(f"Page ID: {result['page_id']}")
        
        # Test updating the same page with a table
        if result['page_id']:
            table_tool = NotionTool(
                database_id=os.getenv("NOTION_INVENTORY_DB_ID"),
                title="Test Inventory Report",
                content={
                    "headers": ["Item", "Current Stock", "Status"],
                    "rows": [
                        ["MacBook Pro", "5", "Low Stock"],
                        ["iPhone", "20", "In Stock"],
                        ["iPad", "0", "Out of Stock"]
                    ]
                },
                content_type="table",
                schema_type="inventory",
                page_id=result['page_id'],
                properties={
                    "Title": {"title": [{"text": {"content": "Test Inventory Report"}}]},
                    "Tags": ["Test", "Inventory"]
                }
            )
            
            table_result = table_tool.run()
            print("\nTable Addition Results:")
            print(f"Status: {table_result['status']}")
            print(f"Updated Page URL: {table_result['url']}")
            
    except Exception as e:
        print(f"Error in test: {str(e)}") 