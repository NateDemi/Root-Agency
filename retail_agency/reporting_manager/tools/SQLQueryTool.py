import re
import os
import logging
import pandas as pd
import json
from datetime import datetime
from typing import Any, Optional, List, Dict, Tuple
from ast import literal_eval
from decimal import Decimal
import csv
from sqlalchemy import text
import traceback

from pydantic import Field, ConfigDict
from dotenv import load_dotenv
from langchain_community.utilities import SQLDatabase
from langchain_openai import ChatOpenAI
from agency_swarm.tools import BaseTool
from pydantic import Field
from retail_agency.reporting_manager.tools.utils.CustomSQLTool import create_structured_sql_agent

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SQLQueryTool(BaseTool):
    """
    A tool for executing SQL queries with pagination support.
    This tool converts natural language queries to SQL, executes them with pagination,
    and returns structured results.
    """
    
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    # Query parameters
    query: str = Field(
        ...,
        description="Natural language query to be converted to SQL"
    )
    page: int = Field(
        default=1,
        description="Page number for pagination"
    )
    page_size: int = Field(
        default=10,
        description="Number of records per page"
    )
    max_tokens: int = Field(
        default=4000,
        description="Maximum tokens for OpenAI API"
    )
    save_path: str = Field(
        default="inventory_results",
        description="Path to save query results"
    )
    
    # Database and agent fields
    db: Optional[SQLDatabase] = None
    agent: Optional[Any] = None
    
    def __init__(self, **data):
        super().__init__(**data)
        os.makedirs(self.save_path, exist_ok=True)
        
        # Initialize database connection
        db_host = os.getenv('CLOUD_DB_HOST')
        db_port = os.getenv('CLOUD_DB_PORT')
        db_user = os.getenv('CLOUD_DB_USER')
        db_pass = os.getenv('CLOUD_DB_PASS')
        db_name = os.getenv('CLOUD_DB_NAME')
        db_schema = os.getenv('CLOUD_SCHEMA')
        
        if not all([db_host, db_port, db_user, db_pass, db_name]):
            raise ValueError("Missing required database environment variables")
            
        # Initialize database connection
        self.db = SQLDatabase.from_uri(
            f"postgresql+psycopg2://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}",
            schema=db_schema
        )
        
        # Initialize the SQL agent
        self.agent = create_structured_sql_agent(
            llm=ChatOpenAI(temperature=0, model="gpt-4"),
            db=self.db,
            verbose=True
        )

    def _get_paginated_query(self, base_query: str) -> str:
        """Add pagination to the SQL query."""
        # Remove any existing LIMIT/OFFSET
        clean_query = re.sub(r'\bLIMIT\s+\d+\s*', '', base_query, re.IGNORECASE)
        clean_query = re.sub(r'\bOFFSET\s+\d+\s*', '', clean_query, re.IGNORECASE)
        
        # Calculate offset
        offset = (self.page - 1) * self.page_size
        
        # Add pagination
        return f"""WITH base_query AS ({clean_query})
                SELECT * FROM base_query
                LIMIT {self.page_size} OFFSET {offset}"""

    def run(self):
        """Execute the SQL query and return the results."""
        try:
            print(f"\nExecuting query: {self.query}")
            print(f"Page: {self.page}, Page Size: {self.page_size}")
            
            # First get the total count
            count_response = self.agent.invoke({
                "input": f"Count how many items match this query: {self.query}"
            })
            logger.info("Received count response from agent")
            
            # Parse the count response
            if isinstance(count_response, dict) and 'output' in count_response:
                count_result = json.loads(count_response['output'])
                total_rows = int(count_result['sql_result'][0][0]) if count_result.get('sql_result') else 0
            else:
                raise ValueError("Unexpected response format from SQL agent for count query")
            
            # Calculate total pages
            total_pages = (total_rows + self.page_size - 1) // self.page_size
            
            # Now get the paginated data
            base_query = f"{self.query}"
            response = self.agent.invoke({"input": base_query})
            logger.info("Received base query response from agent")
            
            # Parse the response
            if isinstance(response, dict) and 'output' in response:
                parsed_response = json.loads(response['output'])
            else:
                raise ValueError("Unexpected response format from SQL agent")
            
            # Get the SQL query and add pagination
            sql_query = parsed_response.get('sql_query')
            if not sql_query:
                raise ValueError("No SQL query generated")
            
            # Add pagination to the query
            paginated_sql = self._get_paginated_query(sql_query)
            
            # Execute the paginated query
            with self.db.get_connection() as conn:
                result = conn.execute(text(paginated_sql))
                columns = result.keys()
                rows = result.fetchall()
                
                # Convert rows to list format and handle special types
                formatted_rows = []
                for row in rows:
                    formatted_row = []
                    for value in row:
                        if isinstance(value, Decimal):
                            formatted_row.append(float(value))
                        else:
                            formatted_row.append(str(value))
                    formatted_rows.append(formatted_row)
            
            # Save results to CSV
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            csv_filename = f"{self.save_path}/query_results_{timestamp}.csv"
            
            with open(csv_filename, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(columns)
                writer.writerows(formatted_rows)
            
            # Prepare the response
            response = {
                'query': self.query,
                'sql_query': paginated_sql,  # Use the paginated query here
                'page': self.page,
                'page_size': self.page_size,
                'total_rows': total_rows,
                'total_pages': total_pages,
                'columns': list(columns),  # Convert columns to list
                'rows': formatted_rows,
                'csv_file': csv_filename
            }
            
            # Format the output for display
            output = "\n" + "="*50 + "\n"
            output += "INVENTORY REPORT - LOW STOCK ITEMS\n"
            output += "="*50 + "\n"
            output += f"Total Items Below 5: {total_rows:,}\n"
            output += f"Items Per Page: {self.page_size}\n"
            output += f"Current Page: {self.page} of {total_pages}\n"
            output += "="*50 + "\n\n"
            
            # Display column headers
            output += "Items:\n"
            output += "-"*50 + "\n"
            
            # Display rows in a more readable format
            for row in formatted_rows:
                for col, val in zip(columns, row):
                    output += f"{col}: {val}\n"
                output += "-"*50 + "\n"
            
            output += f"\nResults saved to: {csv_filename}\n"
            
            # Log the formatted output and return the JSON response
            print(output)
            return json.dumps(response, indent=2)
            
        except Exception as e:
            error_msg = f"Error executing SQL query: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            return f"Error: {error_msg}"


if __name__ == "__main__":
    # Test the SQLQueryTool
    tool = SQLQueryTool(
        query="Get me a list of all inventory with stock_count below 5",
        page=1,
        page_size=50  # Increased from 5 to 50 items per page
    )
    
    try:
        result = tool.run()
        result_dict = json.loads(result)
        
        if isinstance(result_dict, dict):
            print("\n" + "="*50)
            print("INVENTORY REPORT - LOW STOCK ITEMS")
            print("="*50)
            print(f"Total Items Below 5: {result_dict.get('total_rows'):,}")
            print(f"Items Per Page: {result_dict.get('page_size')}")
            print(f"Current Page: {result_dict.get('page')} of {result_dict.get('total_pages')}")
            print("="*50)
            print(f"\nColumns: {', '.join(result_dict.get('columns', []))}")
            print("\nItems:")
            print("-"*50)
            for row in result_dict.get('rows', []):
                print(f"ID: {row[0]}")
                print(f"Name: {row[1]}")
                print(f"Stock Count: {row[2]}")
                print("-"*50)
            
            print(f"\nResults saved to: {result_dict.get('csv_file')}")
        else:
            print(f"\nError: {result}")
            
    except Exception as e:
        print(f"Error executing test: {str(e)}")
        print(traceback.format_exc())

