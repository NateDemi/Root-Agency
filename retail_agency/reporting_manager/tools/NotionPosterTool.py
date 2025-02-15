from agency_swarm.tools import BaseTool
from pydantic import Field, ConfigDict
import os
from dotenv import load_dotenv
from notion_client import Client
import logging
from typing import Optional, Dict, Any, List, Union, Literal
from datetime import datetime
import pandas as pd

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

class NotionPosterTool(BaseTool):
    """
    Tool for posting inventory reports to Notion.
    Creates a structured page with inventory data and analysis.
    Supports multiple data formats: table, checklist, or paragraph.
    """
    
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    database_id: str = Field(
        notion_db_id,
        description="The ID of the Notion database to create the report in"
    )
    
    title: str = Field(
        ..., 
        description="Title of the report"
    )
    
    data: Union[pd.DataFrame, Dict[str, Any], List[str]] = Field(
        ..., 
        description="Data to include in the report"
    )
    
    data_format: Literal["table", "checklist", "paragraph", "auto"] = Field(
        default="auto",
        description="Format to use for the data section (table, checklist, paragraph, or auto)"
    )
    
    query: Optional[str] = Field(
        None,
        description="The original query that generated this data"
    )
    
    analysis: Optional[str] = Field(
        None,
        description="Analysis of the data"
    )

    def _determine_format(self) -> str:
        """Determine the best format based on the data structure."""
        if self.data_format != "auto":
            return self.data_format
            
        if isinstance(self.data, pd.DataFrame):
            return "table"
        elif isinstance(self.data, list):
            # If list items are short, use checklist
            if all(len(str(item)) < 100 for item in self.data):
                return "checklist"
            return "paragraph"
        elif isinstance(self.data, dict):
            # If values are simple types, use table
            if all(isinstance(v, (str, int, float, bool)) for v in self.data.values()):
                return "table"
            return "paragraph"
        return "paragraph"

    def _create_table_blocks(self, data: Union[pd.DataFrame, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Create table blocks from DataFrame or dict."""
        if isinstance(data, pd.DataFrame):
            table_content = {
                "headers": data.columns.tolist(),
                "rows": data.values.tolist()
            }
        else:
            table_content = {
                "headers": list(data.keys()),
                "rows": [list(data.values())]
            }
        
        return [
            {
                "object": "block",
                "type": "table",
                "table": {
                    "table_width": len(table_content["headers"]),
                    "has_column_header": True,
                    "has_row_header": False,
                    "children": [
                        {
                            "type": "table_row",
                            "table_row": {
                                "cells": [[{"type": "text", "text": {"content": str(header)}}] for header in table_content["headers"]]
                            }
                        }
                    ] + [
                        {
                            "type": "table_row",
                            "table_row": {
                                "cells": [[{"type": "text", "text": {"content": str(cell)}}] for cell in row]
                            }
                        } for row in table_content["rows"]
                    ]
                }
            }
        ]

    def _create_checklist_blocks(self, data: Union[List[str], Dict[str, Any], pd.DataFrame]) -> List[Dict[str, Any]]:
        """Create to-do list blocks, grouped by vendor if available."""
        blocks = []
        total_blocks = 0
        max_blocks = 100  # Notion's limit
        
        def create_vendor_header(vendor: str) -> Dict[str, Any]:
            """Create a header block for a vendor group."""
            return {
                "object": "block",
                "type": "heading_3",
                "heading_3": {
                    "rich_text": [{"text": {"content": vendor}}]
                }
            }
        
        def create_todo_item(item: str) -> Dict[str, Any]:
            """Create a to-do block for an item."""
            return {
                "object": "block",
                "type": "to_do",
                "to_do": {
                    "rich_text": [{"text": {"content": str(item)}}],
                    "checked": False
                }
            }

        if isinstance(data, pd.DataFrame):
            # If DataFrame has vendor information
            if 'vendor' in data.columns or 'Vendor' in data.columns:
                vendor_col = 'vendor' if 'vendor' in data.columns else 'Vendor'
                # Group by vendor
                grouped = data.groupby(vendor_col)
                vendors = list(grouped.groups.keys())  # Get list of vendors
                
                for i, (vendor, group) in enumerate(grouped):
                    # Check if we've hit the block limit
                    if total_blocks >= max_blocks:
                        break
                        
                    # Add vendor header
                    blocks.append(create_vendor_header(vendor))
                    total_blocks += 1
                    
                    # Add items for this vendor
                    for _, row in group.iterrows():
                        if total_blocks >= max_blocks:
                            break
                            
                        # Format item text based on available columns
                        item_text = []
                        if 'Product' in row:
                            item_text.append(str(row['Product']))
                        elif 'name' in row or 'Name' in row:
                            name_col = 'name' if 'name' in row else 'Name'
                            item_text.append(str(row[name_col]))
                            
                        if 'stock_count' in row or 'Stock' in row:
                            stock_col = 'stock_count' if 'stock_count' in row else 'Stock'
                            item_text.append(f"{row[stock_col]} units")
                            
                        if 'status' in row or 'Status' in row:
                            status_col = 'status' if 'status' in row else 'Status'
                            item_text.append(f"({row[status_col]})")
                        
                        blocks.append(create_todo_item(" - ".join(item_text)))
                        total_blocks += 1
                    
                    # Add divider between vendor groups (except for last vendor)
                    if i < len(vendors) - 1 and total_blocks < max_blocks:
                        blocks.append({"object": "block", "type": "divider", "divider": {}})
                        total_blocks += 1
            else:
                # No vendor information, create simple checklist
                for _, row in data.iterrows():
                    if total_blocks >= max_blocks:
                        break
                    item_text = " - ".join(str(v) for v in row.values)
                    blocks.append(create_todo_item(item_text))
                    total_blocks += 1
                    
        elif isinstance(data, dict):
            # Check if dict has vendor grouping structure
            if any(isinstance(v, (list, dict)) for v in data.values()):
                # Assume dict keys are vendor names
                vendors = list(data.keys())
                for i, (vendor, items) in enumerate(data.items()):
                    if total_blocks >= max_blocks:
                        break
                        
                    blocks.append(create_vendor_header(vendor))
                    total_blocks += 1
                    
                    if isinstance(items, list):
                        for item in items:
                            if total_blocks >= max_blocks:
                                break
                            blocks.append(create_todo_item(str(item)))
                            total_blocks += 1
                    elif isinstance(items, dict):
                        for item_name, item_details in items.items():
                            if total_blocks >= max_blocks:
                                break
                            blocks.append(create_todo_item(f"{item_name}: {item_details}"))
                            total_blocks += 1
                    
                    # Add divider between vendor groups (except for last vendor)
                    if i < len(vendors) - 1 and total_blocks < max_blocks:
                        blocks.append({"object": "block", "type": "divider", "divider": {}})
                        total_blocks += 1
            else:
                # Simple key-value pairs
                for key, value in data.items():
                    if total_blocks >= max_blocks:
                        break
                    blocks.append(create_todo_item(f"{key}: {value}"))
                    total_blocks += 1
        else:
            # Simple list of items
            for item in data:
                if total_blocks >= max_blocks:
                    break
                blocks.append(create_todo_item(str(item)))
                total_blocks += 1
        
        return blocks

    def _create_paragraph_blocks(self, data: Union[List[str], Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Create paragraph blocks."""
        blocks = []
        
        if isinstance(data, dict):
            # For dictionaries, create a paragraph for each key-value pair
            for key, value in data.items():
                blocks.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"text": {"content": f"{key}: {value}"}}]
                    }
                })
        else:
            # For lists, create a paragraph for each item
            for item in data:
                blocks.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"text": {"content": str(item)}}]
                    }
                })
        
        return blocks

    def _create_data_blocks(self) -> List[Dict[str, Any]]:
        """Create blocks for the data section based on format."""
        format_type = self._determine_format()
        logger.info(f"Using {format_type} format for data")
        
        if format_type == "checklist":
            # For checklist, return just the checklist blocks without the "Data" header
            return self._create_checklist_blocks(self.data)
        
        # For other formats, include the "Data" header
        blocks = [
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"text": {"content": "Data"}}]
                }
            }
        ]
        
        if format_type == "table":
            blocks.extend(self._create_table_blocks(self.data))
        else:  # paragraph
            blocks.extend(self._create_paragraph_blocks(self.data))
            
        return blocks

    def _create_analysis_blocks(self, analysis: str) -> List[Dict[str, Any]]:
        """Break down analysis text into smaller blocks that fit Notion's limits."""
        blocks = [
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"text": {"content": "Analysis"}}]
                }
            }
        ]
        
        # Split analysis into paragraphs
        paragraphs = analysis.split('\n\n')
        
        for paragraph in paragraphs:
            if paragraph.strip():
                # If paragraph starts with #, treat it as a heading
                if paragraph.startswith('#'):
                    level = len(paragraph.split(' ')[0])  # Count the number of #
                    heading_text = ' '.join(paragraph.split(' ')[1:])
                    blocks.append({
                        "object": "block",
                        "type": f"heading_{min(level, 3)}",
                        f"heading_{min(level, 3)}": {
                            "rich_text": [{"text": {"content": heading_text.strip()}}]
                        }
                    })
                else:
                    # Split long paragraphs into chunks of 1900 characters (leaving room for formatting)
                    chunks = [paragraph[i:i+1900] for i in range(0, len(paragraph), 1900)]
                    for chunk in chunks:
                        blocks.append({
                            "object": "block",
                            "type": "paragraph",
                            "paragraph": {
                                "rich_text": [{"text": {"content": chunk.strip()}}]
                            }
                        })
        
        return blocks

    def run(self) -> dict:
        """Create a Notion page with the inventory report."""
        try:
            # Prepare page properties
            properties = {
                "Title": {"title": [{"text": {"content": self.title}}]},
                "Tags": {"multi_select": [{"name": "Inventory"}, {"name": "Report"}]},
                "Created time": {"date": {"start": datetime.now().isoformat()}}
            }
            
            # Prepare content blocks
            blocks = []
            
            # For checklist format, skip query and just add the checklist blocks
            format_type = self._determine_format()
            if format_type == "checklist":
                blocks.extend(self._create_data_blocks())
            else:
                # Add query if provided
                if self.query:
                    blocks.extend([
                        {
                            "object": "block",
                            "type": "heading_2",
                            "heading_2": {
                                "rich_text": [{"text": {"content": "Query"}}]
                            }
                        },
                        {
                            "object": "block",
                            "type": "paragraph",
                            "paragraph": {
                                "rich_text": [{"text": {"content": self.query}}]
                            }
                        },
                        {
                            "object": "block",
                            "type": "divider",
                            "divider": {}
                        }
                    ])
                
                # Add data section
                blocks.extend(self._create_data_blocks())
                
                # Add analysis if provided
                if self.analysis:
                    blocks.append({
                        "object": "block",
                        "type": "divider",
                        "divider": {}
                    })
                    blocks.extend(self._create_analysis_blocks(self.analysis))
            
            # Create the page
            response = notion.pages.create(
                parent={"database_id": self.database_id},
                properties=properties,
                children=blocks
            )
            
            logger.info(f"Created Notion page: {response['id']}")
            return {
                "status": "created",
                "page_id": response["id"],
                "url": response["url"]
            }

        except Exception as e:
            logger.error(f"Error creating Notion page: {str(e)}")
            raise

if __name__ == "__main__":
    # Test the NotionPosterTool with different formats including vendor grouping
    try:
        # Test data with vendor grouping
        test_data_grouped = {
            "Costco": [
                "MacBook Pro: 5 units (Low Stock)",
                "iPhone: 20 units (In Stock)"
            ],
            "Walmart": [
                "iPad: 0 units (Out of Stock)",
                "AirPods: 15 units (In Stock)"
            ],
            "Best Buy": [
                "Apple Watch: 3 units (Low Stock)",
                "iMac: 8 units (In Stock)"
            ]
        }
        
        # Test data as DataFrame with vendor information
        test_data_df_grouped = pd.DataFrame({
            "Vendor": ["Costco", "Costco", "Walmart", "Walmart", "Best Buy"],
            "Product": ["MacBook Pro", "iPhone", "iPad", "AirPods", "Apple Watch"],
            "Stock": [5, 20, 0, 15, 3],
            "Status": ["Low Stock", "In Stock", "Out of Stock", "In Stock", "Low Stock"]
        })
        
        # Original test data
        test_data_table = pd.DataFrame({
            "Product": ["MacBook Pro", "iPhone", "iPad"],
            "Stock": [5, 20, 0],
            "Status": ["Low Stock", "In Stock", "Out of Stock"]
        })
        
        test_data_checklist = [
            "MacBook Pro: 5 units (Low Stock)",
            "iPhone: 20 units (In Stock)",
            "iPad: 0 units (Out of Stock)"
        ]
        
        # Test with grouped data
        print("\nTesting with vendor-grouped dictionary data:")
        tool = NotionPosterTool(
            title="Test Inventory Report - Grouped Checklist",
            data=test_data_grouped,
            data_format="checklist",
            query="Show items with low stock by vendor",
            analysis="Several items are running low on stock across different vendors."
        )
        result = tool.run()
        print(f"Status: {result['status']}")
        print(f"Page URL: {result['url']}")
        
        print("\nTesting with vendor-grouped DataFrame:")
        tool = NotionPosterTool(
            title="Test Inventory Report - Grouped DataFrame",
            data=test_data_df_grouped,
            data_format="checklist",
            query="Show items with low stock by vendor",
            analysis="Several items are running low on stock across different vendors."
        )
        result = tool.run()
        print(f"Status: {result['status']}")
        print(f"Page URL: {result['url']}")
        
    except Exception as e:
        print(f"Error in test: {str(e)}") 