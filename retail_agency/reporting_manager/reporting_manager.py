from agency_swarm import Agent
from .tools.SQLQueryToolV3 import SQLQueryTool
from .tools.FileReaderTool import FileReaderTool
from .tools.GoogleDriveTool import GoogleDriveTool
from .tools.NotionPosterTool import NotionPosterTool
from .tools.SlackCommunicator import SlackCommunicator
import logging
import json
import pandas as pd
from typing import Dict, Any, List, Optional
from datetime import datetime
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ReportingManager(Agent):
    """
    Primary point of contact for users seeking business information and insights.
    
    Key Responsibilities:
    1. Understands and processes user queries about business data
    2. Retrieves data from database using SQL queries
    3. Analyzes data context and patterns using FileReader
    4. Shares data through multiple platforms:
       - Google Sheets for detailed spreadsheets
       - Notion for checklist-style inventory tracking
       - Slack for quick updates and notifications
    5. Maintains clear communication with users in simple, active voice
    6. Automatically formats vendor-based data as Notion checklists
    """
    
    MAX_DISPLAY_ROWS = 10  # Maximum number of rows to display in natural language response
    
    def __init__(self):
        super().__init__(
            name="ReportingManager",
            description=(
                "I am your direct point of contact for all business information needs. "
                "I help you understand your data by retrieving information from the database, "
                "analyzing patterns, and sharing insights in your preferred format. "
                "I communicate clearly and can share data through Google Sheets, Notion checklists, "
                "or Slack updates based on your needs."
            ),
            instructions="./instructions.md",
            tools=[SQLQueryTool, FileReaderTool, GoogleDriveTool, NotionPosterTool, SlackCommunicator],
            temperature=0,
            model="gpt-4"
        )

    def _generate_insights(self, data: Dict[str, Any]) -> str:
        """Generate insights from the query results."""
        try:
            total_records = data.get('total_records', 0)
            preview_data = data.get('preview', [])
            sql_query = data.get('sql_query', '')
            
            insights = [
                f"Found {total_records} records matching your query.",
                f"\nSQL Query Used: {sql_query}",
                "\nKey findings:"
            ]
            
            if preview_data:
                for item in preview_data:
                    item_str = ", ".join([f"{k}: {v}" for k, v in item.items()])
                    insights.append(f"• {item_str}")
                
                if total_records > len(preview_data):
                    insights.append(f"\nAnd {total_records - len(preview_data)} more items.")
                    
            if data.get('file_paths'):
                insights.append("\nComplete results have been saved to:")
                for file_type, path in data['file_paths'].items():
                    insights.append(f"• {file_type}: {path}")
            
            if data.get('google_sheet_url'):
                insights.append(f"\nReport available in Google Sheets: {data['google_sheet_url']}")
                
            if data.get('notion_url'):
                insights.append(f"\nReport available in Notion: {data['notion_url']}")
            
            return "\n".join(insights)
            
        except Exception as e:
            logger.error(f"Error generating insights: {str(e)}")
            return "Error generating insights from the data."

    def analyze_results(self, csv_path: str, question: str) -> str:
        """Use FileReaderTool to analyze the query results in detail."""
        try:
            file_reader = FileReaderTool(
                question=question,
                gcs_uri=csv_path,
                use_local_file=True  # Use local file since we're reading from saved CSV
            )
            
            analysis = file_reader.run()
            return analysis
            
        except Exception as e:
            error_msg = f"Error analyzing results: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return f"Error: {error_msg}"

    def _export_to_google_sheets(self, data: Dict[str, Any], query: str) -> Optional[Dict[str, str]]:
        """Export query results to Google Sheets."""
        try:
            # Convert preview data to DataFrame
            if data.get('preview'):
                df = pd.DataFrame(data['preview'])
            else:
                # If no preview data, try to read from CSV
                csv_path = data.get('file_paths', {}).get('csv_path')
                if not csv_path or not os.path.exists(csv_path):
                    logger.error("No data available for Google Sheets export")
                    return None
                df = pd.read_csv(csv_path)

            # Create title for the sheet
            title = f"Inventory Report - {datetime.now().strftime('%Y%m%d_%H%M%S')}"

            # Initialize Google Drive tool
            drive_tool = GoogleDriveTool(
                title=title,
                data=df
            )

            # Create the sheet
            result = drive_tool.run()
            return result

        except Exception as e:
            logger.error(f"Error exporting to Google Sheets: {str(e)}")
            return None

    def _export_to_notion(self, data: Dict[str, Any], query: str, analysis: Optional[str] = None) -> Optional[Dict[str, str]]:
        """Export query results to Notion."""
        try:
            # Get data from GCS if available
            if data.get('gcs_uris', {}).get('response_uri'):
                logger.info(f"Reading data from GCS: {data['gcs_uris']['response_uri']}")
                file_reader = FileReaderTool(
                    question="Get raw data for Notion export",
                    gcs_uri=data['gcs_uris']['response_uri'],
                    max_rows=1000  # Adjust if needed
                )
                # Get the DataFrame from FileReader's internal state after running
                file_reader.run()  # This loads the data
                df = file_reader._read_csv_from_gcs()
            else:
                logger.error("No GCS URI available for Notion export")
                return None

            # Create title for the page
            title = f"Inventory Reorder List - {datetime.now().strftime('%Y%m%d_%H%M%S')}"

            # Process DataFrame for vendor grouping
            if 'vendor_name' not in df.columns and 'vendor' in df.columns:
                df['vendor_name'] = df['vendor']
            
            # Ensure we have vendor information, use 'Unknown Vendor' if missing
            if 'vendor_name' not in df.columns:
                df['vendor_name'] = 'Unknown Vendor'

            # Sort by vendor and stock count
            df = df.sort_values(['vendor_name', 'stock_count'])

            # Group by vendor and chunk into smaller groups
            grouped_data = {}
            for vendor, group in df.groupby('vendor_name'):
                items = []
                for _, row in group.iterrows():
                    item_text = []
                    
                    # Add item name
                    if 'name' in row:
                        item_text.append(str(row['name']))
                    
                    # Add stock count with urgency indicator
                    if 'stock_count' in row:
                        stock = row['stock_count']
                        if stock <= 0:
                            urgency = "🔴"  # Red circle for critical
                        elif stock < 5:
                            urgency = "🟡"  # Yellow circle for low
                        else:
                            urgency = "🟢"  # Green circle for ok
                        item_text.append(f"{urgency} Stock: {stock}")
                    
                    # Add recent sales if available
                    if 'recent_sales' in row:
                        item_text.append(f"Recent Sales: {row['recent_sales']}")
                    
                    items.append(" | ".join(item_text))
                
                # Split items into chunks of 50 for each vendor
                chunk_size = 50
                chunks = [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]
                
                # Create a separate key for each chunk
                for i, chunk in enumerate(chunks):
                    chunk_key = f"{vendor} (Part {i+1})" if len(chunks) > 1 else vendor
                    grouped_data[chunk_key] = chunk

            # Initialize Notion tool with checklist format
            notion_tool = NotionPosterTool(
                title=title,
                data=grouped_data,
                data_format="checklist",  # Always use checklist format
                query=query,
                analysis=analysis
            )

            # Create the page
            result = notion_tool.run()
            return result

        except Exception as e:
            logger.error(f"Error exporting to Notion: {str(e)}")
            return None

    def _notify_slack(self, result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Send a notification to Slack with the report links."""
        try:
            # Get the channel ID from environment variable
            channel_id = os.getenv("SLACK_CHANNEL_ID")
            if not channel_id:
                logger.warning("SLACK_CHANNEL_ID not set, skipping Slack notification")
                return None

            # Create a message with the report links
            message = f"[NEW REPORT] Inventory Report Available\n"
            message += f"Query: {result.get('query', 'N/A')}\n\n"
            
            if result.get('google_sheet_url'):
                message += f"[SHEETS] {result['google_sheet_url']}\n"
            
            if result.get('notion_url'):
                message += f"[NOTION] {result['notion_url']}\n"
            
            if result.get('total_rows'):
                message += f"\nFound {result['total_rows']} matching items."

            # Initialize Slack tool
            slack_tool = SlackCommunicator(
                channel_id=channel_id,
                message=message
            )
            
            # Send the message
            slack_result = slack_tool.run()
            return slack_result

        except Exception as e:
            logger.error(f"Error sending Slack notification: {str(e)}")
            return None

    def handle_message(self, message: str) -> Dict[str, Any]:
        """Handle incoming messages by executing SQL queries and formatting responses."""
        try:
            logger.info(f"[DEBUG] Processing query: {message}")
            
            # Step 1: Execute SQL query and get GCS URIs
            sql_tool = SQLQueryTool(
                question=message,
                db_schema=os.getenv('CLOUD_SCHEMA')
            )
            
            result = sql_tool.run()
            logger.info(f"[DEBUG] SQLQueryTool result: {result[:500]}...")  # Log first 500 chars
            result_data = json.loads(result)
            
            if "error" in result_data:
                logger.error(f"[DEBUG] Error in result: {result_data['error']}")
                return {
                    "natural_response": f"Error: {result_data['error']}",
                    "query": message,
                    "execution_time": datetime.now().isoformat()
                }
            
            # Step 2: Get initial data context using FileReader
            logger.info(f"[DEBUG] Getting data context from: {result_data['gcs_uris']['response_uri']}")
            file_reader = FileReaderTool(
                question=f"Give me a brief summary of this data to understand the context: {message}",
                gcs_uri=result_data['gcs_uris']['response_uri']
            )
            initial_context = file_reader.run()
            logger.info(f"[DEBUG] Initial context: {initial_context[:500]}...")
            
            # Step 3: Export to Notion if this is a reordering query
            notion_url = None
            if "reorder" in message.lower() or "stock" in message.lower():
                notion_result = self._export_to_notion(
                    data=result_data,
                    query=message,
                    analysis=initial_context
                )
                if notion_result and notion_result.get('url'):
                    notion_url = notion_result['url']
            
            # Step 4: Generate natural language response with context
            natural_response = (
                f"I've found some data matching your query. Here's what I found:\n\n"
                f"{initial_context}\n\n"
            )
            
            if notion_url:
                natural_response += f"I've created a checklist in Notion to help track these items: {notion_url}\n\n"
            
            natural_response += (
                f"Would you like to know more about any specific aspect of this data? "
                f"For example, I can:\n"
                f"- Analyze patterns or trends\n"
                f"- Break down the data by specific categories\n"
                f"- Generate a detailed report in Google Sheets\n"
                f"- Share quick insights via Slack"
            )
            
            # Step 5: Prepare the response
            response = {
                "natural_response": natural_response,
                "query": message,
                "sql_query": result_data['sql_query'],
                "gcs_uris": result_data['gcs_uris'],
                "execution_time": datetime.now().isoformat(),
                "initial_context": initial_context
            }
            
            if notion_url:
                response["notion_url"] = notion_url
            
            logger.info(f"[DEBUG] Final response: {json.dumps(response, indent=2)}")
            return response
            
        except Exception as e:
            error_msg = f"Error processing query: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                "natural_response": f"Error: {error_msg}",
                "query": message,
                "execution_time": datetime.now().isoformat()
            }

    def analyze_specific_aspect(self, gcs_uri: str, aspect_question: str) -> str:
        """Analyze a specific aspect of the data using FileReader."""
        try:
            file_reader = FileReaderTool(
                question=aspect_question,
                gcs_uri=gcs_uri
            )
            return file_reader.run()
        except Exception as e:
            logger.error(f"Error analyzing specific aspect: {str(e)}")
            return f"Error analyzing data: {str(e)}"

    def handle_response(self, response: str) -> str:
        """Process and format responses before sending to user.
        
        Args:
            response (str): Raw response string or JSON string
            
        Returns:
            str: Formatted response with timestamps and proper formatting
        """
        try:
            # Try to parse response as JSON if it's a string
            if isinstance(response, str):
                try:
                    response_data = json.loads(response)
                except json.JSONDecodeError:
                    # If not JSON, return as is with timestamp
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    return f"[{timestamp}] {response}"
            else:
                response_data = response

            # Handle error responses
            if isinstance(response_data, dict) and "error" in response_data:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                return f"[{timestamp}] Error: {response_data['error']}"

            # Format response based on type
            if isinstance(response_data, dict):
                # Extract key information
                natural_response = response_data.get("natural_response", "")
                gcs_uris = response_data.get("gcs_uris", {})
                metadata = response_data.get("metadata", {})
                
                # Build formatted response
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                formatted_parts = [f"[{timestamp}]"]
                
                if natural_response:
                    formatted_parts.append(natural_response)
                
                if metadata:
                    formatted_parts.append("\nMetadata:")
                    for key, value in metadata.items():
                        formatted_parts.append(f"- {key}: {value}")
                
                if gcs_uris:
                    formatted_parts.append("\nStored Results:")
                    for key, uri in gcs_uris.items():
                        formatted_parts.append(f"- {key}: {uri}")
                
                return "\n".join(formatted_parts)
            
            elif isinstance(response_data, list):
                # Format list as bullet points
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                formatted_items = [f"[{timestamp}]"]
                formatted_items.extend([f"- {item}" for item in response_data])
                return "\n".join(formatted_items)
            
            else:
                # Default formatting with timestamp
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                return f"[{timestamp}] {str(response_data)}"
                
        except Exception as e:
            logger.error(f"Error formatting response: {str(e)}")
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            return f"[{timestamp}] Error formatting response: {str(e)}"

if __name__ == "__main__":
    # Test the ReportingManager
    manager = ReportingManager()
    test_query = "Show me inventory items with stock count below 5"
    
    try:
        result = manager.handle_message(test_query)
        print("\nQuery Response:")
        print("=" * 50)
        print(result["natural_response"])
        
        if result.get("gcs_uris"):
            print("\nStored Results:")
            print("-" * 50)
            for key, uri in result["gcs_uris"].items():
                print(f"{key}: {uri}")
        
    except Exception as e:
        print(f"Error in test execution: {str(e)}")
        logger.error(f"Test error details: {str(e)}", exc_info=True)