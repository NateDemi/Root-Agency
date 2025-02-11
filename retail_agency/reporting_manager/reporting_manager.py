from agency_swarm import Agent
from .tools.SQLQueryTool import SQLQueryTool
import logging
import json
import pandas as pd
from typing import Dict, Any, List
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ReportingManager(Agent):
    """Advanced reporting manager that handles database queries and analytics."""
    
    MAX_DISPLAY_ROWS = 10  # Maximum number of rows to display in natural language response
    
    def __init__(self):
        super().__init__(
            name="ReportingManager",
            description="Refines and rephrases incoming user questions into clear, natural language questions, passes them to the SQLQueryTool for execution, and returns actionable insights and summaries.",
            instructions="./instructions.md",
            tools=[SQLQueryTool],
            temperature=0,
            model="gpt-4"
        )

    def _read_saved_data(self, file_path: str) -> pd.DataFrame:
        """Read data from saved file (CSV or JSON)."""
        try:
            if file_path.endswith('.csv'):
                return pd.read_csv(file_path)
            elif file_path.endswith('.json'):
                return pd.read_json(file_path)
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {str(e)}")
            return pd.DataFrame()

    def _generate_data_insights(self, df: pd.DataFrame, query: str) -> Dict[str, Any]:
        """Generate dynamic insights from the data using LLM."""
        try:
            # Get dataframe info
            columns = df.columns.tolist()
            sample_data = df.head(3).to_dict('records')
            basic_stats = {
                col: {
                    'type': str(df[col].dtype),
                    'has_nulls': df[col].isnull().any(),
                    'unique_count': df[col].nunique()
                }
                for col in columns
            }

            # Create context for LLM
            context = {
                'original_query': query,
                'total_rows': len(df),
                'columns': columns,
                'sample_data': sample_data,
                'column_stats': basic_stats
            }

            # Create prompt for LLM
            prompt = f"""Given this data context from a database query:
Original Query: {query}
Total Rows: {context['total_rows']}
Available Columns: {', '.join(columns)}
Sample Data: {json.dumps(sample_data, indent=2)}

Analyze this data and provide:
1. A natural language summary of what the data shows
2. Key statistics or patterns that are relevant to the query
3. Any notable insights or recommendations based on the data

Focus on insights that are:
- Directly relevant to the original query
- Based on patterns in the numerical data (if any)
- Actionable for business decisions
- Highlight any critical patterns or outliers

Format your response as a structured list of insights that's easy to read."""

            # Get insights from LLM
            response = self.model.predict(prompt)
            
            # Return both raw stats and LLM insights
            return {
                "data_stats": context,
                "insights": response
            }

        except Exception as e:
            logger.error(f"Error generating insights: {str(e)}")
            return {
                "error": str(e),
                "total_rows": len(df) if df is not None else 0
            }

    def _format_result_summary(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Format query results into a summary with sample data and insights."""
        try:
            # Initialize summary structure
            summary = {
                "natural_response": "",
                "sample_data": [],
                "total_rows": 0,
                "files": {
                    "csv": result.get('csv_path'),
                    "json": result.get('json_path')
                },
                "query": result.get('query'),
                "execution_time": datetime.now().isoformat()
            }

            # Read the saved data
            if summary["files"]["csv"]:
                df = self._read_saved_data(summary["files"]["csv"])
                if not df.empty:
                    # Get basic stats and insights
                    total_rows = len(df)
                    sample_data = df.head(self.MAX_DISPLAY_ROWS).to_dict('records')
                    insights = self._generate_data_insights(df, result.get('query', ''))

                    # Create natural language response
                    response_parts = []
                    
                    # Add LLM-generated insights
                    if insights.get('insights'):
                        response_parts.append(insights['insights'])
                    else:
                        response_parts.append(f"Found {total_rows} records matching your query.")

                    if total_rows > self.MAX_DISPLAY_ROWS:
                        response_parts.append(f"\nShowing first {self.MAX_DISPLAY_ROWS} items as sample.")
                        response_parts.append("Complete results have been saved to:")
                        response_parts.append(f"- CSV file: {summary['files']['csv']}")
                        response_parts.append(f"- JSON file: {summary['files']['json']}")

                    summary.update({
                        "natural_response": "\n".join(response_parts),
                        "sample_data": sample_data,
                        "total_rows": total_rows,
                        "insights": insights.get('data_stats'),
                        "analysis": insights.get('insights')
                    })
                else:
                    summary["natural_response"] = "No results found for your query."
            else:
                summary["natural_response"] = "No results available."

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
        if result.get('type') == 'error':
            return False
        return bool(result.get('csv_path') or result.get('json_path'))

    def handle_message(self, message: str) -> Dict[str, Any]:
        """convert message to natural language question."""
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
                    
            if result.get("insights"):
                print("\nInsights:")
                for key, value in result["insights"].items():
                    if isinstance(value, pd.DataFrame):
                        print(f"\n{key.replace('_', ' ').title()}:")
                        print(value[['name', 'stock_count']].head().to_string())
                    else:
                        print(f"{key.replace('_', ' ').title()}: {value}")
        
    except Exception as e:
        print(f"Error in test execution: {str(e)}")