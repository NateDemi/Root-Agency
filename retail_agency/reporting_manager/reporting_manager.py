from agency_swarm import Agent
from tools.SQLQueryTool import SQLQueryTool
import logging
import json
from typing import Dict, Any, Optional
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ReportingManager(Agent):
    """Advanced reporting manager that handles database queries and analytics."""
    
    MAX_DISPLAY_ROWS = 10  # Maximum number of rows to display in natural language response
    
    def __init__(self):
        super().__init__(
            name="ReportingManager",
            description="Handles database queries and provides data-driven insights",
            instructions="./instructions.md",
            tools=[SQLQueryTool],
            temperature=0,
            model="gpt-4"
        )

    def _format_result_summary(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Format query results into a summary with sample data and file locations."""
        try:
            total_rows = result.get('row_count', 0)
            data = result.get('data', [])
            files = {
                "csv": result.get('csv_path'),
                "json": result.get('json_path')
            }
            
            summary = {
                "natural_response": "",
                "sample_data": [],
                "total_rows": total_rows,
                "files": files,
                "query": result.get('query'),
                "execution_time": datetime.now().isoformat()
            }
            
            # Generate natural language response based on result size
            if total_rows == 0:
                summary["natural_response"] = "No results found for your query."
            else:
                # Take first MAX_DISPLAY_ROWS for sample
                sample_data = data[:self.MAX_DISPLAY_ROWS]
                summary["sample_data"] = sample_data
                
                # Construct response based on data size
                if total_rows <= self.MAX_DISPLAY_ROWS:
                    summary["natural_response"] = f"Found {total_rows} items. Here are all the results:"
                else:
                    # Include file information in the response
                    summary["natural_response"] = (
                        f"Found {total_rows} items. Here are the first {self.MAX_DISPLAY_ROWS} items.\n"
                        f"Complete results have been saved to:\n"
                    )
                    
                    if files["csv"]:
                        summary["natural_response"] += f"- CSV file: {files['csv']}\n"
                    if files["json"]:
                        summary["natural_response"] += f"- JSON file: {files['json']}\n"
                    
                    summary["natural_response"] += "\nYou can access the full dataset using these files."
            
            # Add metadata about the query execution
            summary["metadata"] = {
                "execution_time": summary["execution_time"],
                "total_rows": total_rows,
                "displayed_rows": len(summary["sample_data"]),
                "has_more": total_rows > self.MAX_DISPLAY_ROWS,
                "files_saved": bool(files["csv"] or files["json"])
            }
            
            return summary
            
        except Exception as e:
            logger.error(f"Error formatting result summary: {str(e)}")
            return {
                "natural_response": f"Error formatting results: {str(e)}",
                "sample_data": [],
                "total_rows": 0,
                "files": {},
                "query": result.get('query'),
                "execution_time": datetime.now().isoformat()
            }

    def _validate_query_result(self, result: Dict[str, Any]) -> bool:
        """Validate that the query result has the expected structure."""
        required_fields = ['type', 'data', 'row_count']
        return all(field in result for field in required_fields)

    def handle_message(self, message: str) -> Dict[str, Any]:
        """Handle incoming messages and return structured responses."""
        try:
            logger.info(f"Processing query: {message}")
            
            # Execute query with proper initialization check
            tool = SQLQueryTool(query=message)
            
            if not hasattr(tool, '_agent_executor') or tool._agent_executor is None:
                raise ValueError("SQL agent failed to initialize. Please check database connection parameters.")
                
            result = tool.run()
            logger.info(f"Received query result: {result}")
            
            # Validate result
            if not self._validate_query_result(result):
                if isinstance(result, dict) and 'error' in result:
                    raise ValueError(f"Query execution failed: {result['error']}")
                raise ValueError("Invalid query result structure")
            
            # Format the response
            summary = self._format_result_summary(result)
            
            logger.info(f"Generated response summary with {summary['total_rows']} total rows")
            return summary
            
        except ValueError as ve:
            error_msg = str(ve)
            logger.error(error_msg)
            return {
                "natural_response": f"Error: {error_msg}",
                "sample_data": [],
                "total_rows": 0,
                "files": {},
                "query": message,
                "execution_time": datetime.now().isoformat(),
                "error": error_msg
            }
        except Exception as e:
            error_msg = f"Error processing message: {str(e)}"
            logger.error(error_msg)
            return {
                "natural_response": f"Error: {error_msg}",
                "sample_data": [],
                "total_rows": 0,
                "files": {},
                "query": message,
                "execution_time": datetime.now().isoformat(),
                "error": error_msg
            }

    def __str__(self) -> str:
        return f"ReportingManager(max_display_rows={self.MAX_DISPLAY_ROWS})"

if __name__ == "__main__":
    # Test the ReportingManager
    manager = ReportingManager()
    test_query = "Get me all inventory items with stock count less than 0"
    
    try:
        result = manager.handle_message(test_query)
        
        print("\nQuery Response:")
        print(result["natural_response"])
        
        if result["sample_data"]:
            print("\nSample Data:")
            for idx, item in enumerate(result["sample_data"], 1):
                print(f"\nItem {idx}:")
                for key, value in item.items():
                    print(f"{key}: {value}")
                    
            if result["total_rows"] > len(result["sample_data"]):
                print("\nFull results saved to:")
                if result["files"].get("csv"):
                    print(f"CSV: {result['files']['csv']}")
                if result["files"].get("json"):
                    print(f"JSON: {result['files']['json']}")
        
        # Print metadata if available
        if "metadata" in result:
            print("\nQuery Metadata:")
            for key, value in result["metadata"].items():
                print(f"{key}: {value}")
            
    except Exception as e:
        print(f"Error in test execution: {str(e)}")