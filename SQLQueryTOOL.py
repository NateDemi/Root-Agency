import re
import os
import logging
import pandas as pd
import json
from datetime import datetime
from typing import Any, Optional, List, Dict, Tuple
from ast import literal_eval

from pydantic import Field, ConfigDict
from dotenv import load_dotenv

from langchain_community.utilities import SQLDatabase
from langchain_openai import ChatOpenAI
from agency_swarm.tools import BaseTool
from .utils.CustomSQLTool import create_structured_sql_agent

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SQLQueryTool(BaseTool):
    """Tool for executing SQL queries with improved result handling."""
    
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    query: str = Field(
        ...,
        description="The natural language query to be converted into SQL and executed"
    )
    
    chunk_size: int = Field(
        default=100,
        description="Number of rows per chunk"
    )
    
    max_tokens: int = Field(
        default=4000,
        description="Maximum tokens for GPT response"
    )
    
    save_path: str = Field(
        default="inventory_results",
        description="Path to save query results"
    )
    
    _db: Optional[SQLDatabase] = None
    _agent_executor: Optional[Any] = None

    def __init__(self, **data):
        super().__init__(**data)
        os.makedirs(self.save_path, exist_ok=True)
        self._initialize_agent()

    def _initialize_agent(self):
        """Initialize SQL agent with database connection."""
        try:
            # Get database connection parameters
            db_host = os.getenv('CLOUD_DB_HOST')
            db_port = os.getenv('CLOUD_DB_PORT')
            db_user = os.getenv('CLOUD_DB_USER')
            db_pass = os.getenv('CLOUD_DB_PASS')
            db_name = os.getenv('CLOUD_DB_NAME')
            db_schema = os.getenv('CLOUD_SCHEMA')
            
            if not all([db_host, db_port, db_user, db_pass, db_name]):
                raise ValueError("Missing required database environment variables")
            
            database_url = f"postgresql+psycopg2://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
            logger.info(f"Connecting to database at {db_host}")
            
            self._db = SQLDatabase.from_uri(
                database_url,
                schema=db_schema,
                sample_rows_in_table_info=5
            )
            
            llm = ChatOpenAI(
                temperature=0,
                model="gpt-4",
                max_tokens=self.max_tokens
            )
            
            self._agent_executor = create_structured_sql_agent(
                llm=llm,
                db=self._db,
                verbose=True
            )
            
            logger.info("Successfully initialized SQL agent")
            
        except Exception as e:
            logger.error(f"Error initializing SQL agent: {str(e)}")
            raise

    def _parse_tuple_string(self, tuple_string: str) -> List[Tuple]:
        """Parse a string representation of a list of tuples into actual tuples."""
        try:
            # Using literal_eval to safely evaluate the string
            return literal_eval(tuple_string)
        except Exception as e:
            logger.error(f"Error parsing tuple string: {str(e)}")
            return []

    def _extract_sql_and_results(self, response: Dict[str, Any]) -> Tuple[str, List[Tuple]]:
        """Extract SQL query and results from agent response."""
        try:
            if not isinstance(response, dict) or 'output' not in response:
                raise ValueError("Invalid response format")

            # Try to parse the JSON output
            if isinstance(response['output'], str):
                parsed_output = json.loads(response['output'])
            else:
                parsed_output = response['output']

            sql_query = parsed_output.get('sql_query', '')
            raw_results = parsed_output.get('sql_result', [])

            # If results are a string representation of a list of tuples
            if isinstance(raw_results, str):
                results = self._parse_tuple_string(raw_results)
            else:
                results = raw_results

            return sql_query, results

        except json.JSONDecodeError:
            # Fallback to regex extraction if JSON parsing fails
            output = str(response.get('output', ''))
            sql_match = re.search(r'"sql_query":\s*"([^"]+)"', output)
            results_match = re.search(r'"sql_result":\s*(\[.*?\])', output, re.DOTALL)
            
            sql_query = sql_match.group(1) if sql_match else ''
            results = self._parse_tuple_string(results_match.group(1)) if results_match else []
            
            return sql_query, results

        except Exception as e:
            logger.error(f"Error extracting SQL and results: {str(e)}")
            return '', []

    def _infer_columns_from_query(self, query: str) -> List[str]:
        """Dynamically infer column names from the query."""
        # Try to extract columns from SQL query if present in the response
        sql_match = re.search(r"SELECT\s+(.*?)\s+FROM", query, re.IGNORECASE)
        if sql_match:
            # Clean up column names from SQL
            columns = [
                col.strip().split(' AS ')[-1].split('.')[-1].strip('"`') 
                for col in sql_match.group(1).split(',')
            ]
            return columns
            
        # Analyze natural language query for column hints
        query_lower = query.lower()
        keywords = {
            'stock_count': ['stock', 'inventory', 'quantity'],
            'price': ['price', 'cost', 'amount'],
            'name': ['name', 'item', 'product'],
            'date': ['when', 'date', 'time'],
            'vendor': ['vendor', 'supplier'],
            'category': ['category', 'type'],
            'sales': ['sales', 'revenue', 'sold'],
            'id': ['id', 'identifier', 'code']
        }
        
        detected_columns = []
        for col_name, indicators in keywords.items():
            if any(indicator in query_lower for indicator in indicators):
                detected_columns.append(col_name)
                
        return detected_columns

    def _convert_to_dataframe(self, results: Any) -> pd.DataFrame:
        """Convert SQL query results to DataFrame with dynamic column detection."""
        try:
            # If results is already a DataFrame
            if isinstance(results, pd.DataFrame):
                return results

            # Extract data from response if it's in the structured format
            if isinstance(results, dict) and 'sql_result' in results:
                data = results['sql_result']
                sql_query = results.get('sql_query', '')
            else:
                data = results
                sql_query = ''

            # Handle tuple data
            if isinstance(data, list) and data and isinstance(data[0], tuple):
                # Try multiple strategies to determine columns
                columns = []
                
                # 1. Try SQL query if available
                if sql_query:
                    columns = self._infer_columns_from_query(sql_query)
                
                # 2. Try natural language query if no columns yet
                if not columns:
                    columns = self._infer_columns_from_query(self.query)
                
                # 3. Analyze data structure if still no columns or length mismatch
                if not columns or len(columns) != len(data[0]):
                    # Try to infer from data content
                    sample_row = data[0]
                    inferred_columns = []
                    for i, value in enumerate(sample_row):
                        if isinstance(value, (int, float)) and value < 0:
                            inferred_columns.append('quantity')
                        elif isinstance(value, str) and len(value) > 20:
                            inferred_columns.append('name')
                        elif isinstance(value, str) and len(value) < 20:
                            inferred_columns.append('id' if value.isupper() else 'category')
                        else:
                            inferred_columns.append(f'column_{i}')
                    columns = inferred_columns
                
                # Ensure we have the right number of columns
                if len(columns) != len(data[0]):
                    columns = [f'column_{i}' for i in range(len(data[0]))]
                
                logger.info(f"Using columns: {columns}")
                
                # Convert tuples to list of dicts
                records = [dict(zip(columns, row)) for row in data]
                df = pd.DataFrame(records)
                logger.info(f"Created DataFrame with shape: {df.shape}")
                return df

            # Handle list of dicts
            if isinstance(data, list) and data and isinstance(data[0], dict):
                df = pd.DataFrame(data)
                logger.info(f"Created DataFrame from dicts with shape: {df.shape}")
                return df

            # Handle empty results
            logger.warning("No data to convert to DataFrame")
            return pd.DataFrame()

        except Exception as e:
            logger.error(f"Error converting to DataFrame: {str(e)}")
            # Return a DataFrame with the raw data as a fallback
            if isinstance(results, dict) and 'sql_result' in results:
                return pd.DataFrame({'raw_data': [str(results['sql_result'])]})
            return pd.DataFrame()

    def _save_results(self, df: pd.DataFrame, base_name: str) -> Dict[str, str]:
        """Save results to both CSV and JSON files."""
        if df.empty:
            logger.warning("No data to save")
            return {}

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        paths = {}

        try:
            # Save CSV
            csv_filename = f"{base_name}_{timestamp}.csv"
            csv_path = os.path.join(self.save_path, csv_filename)
            df.to_csv(csv_path, index=False)
            paths['csv'] = csv_path
            logger.info(f"Saved results to CSV: {csv_path}")

            # Save JSON
            json_filename = f"{base_name}_{timestamp}.json"
            json_path = os.path.join(self.save_path, json_filename)
            df.to_json(json_path, orient='records', indent=2)
            paths['json'] = json_path
            logger.info(f"Saved results to JSON: {json_path}")

            return paths

        except Exception as e:
            logger.error(f"Error saving results: {str(e)}")
            return paths

    def run(self) -> dict:
        """Execute query and return structured results."""
        try:
            if not self._agent_executor:
                raise ValueError("SQL agent not properly initialized")
            
            # Get the response from the agent
            agent_response = self._agent_executor.invoke({"input": self.query})
            logger.info("Received response from agent")
            
            # Parse the response more carefully
            try:
                # First try to get the output
                if isinstance(agent_response, dict):
                    output = agent_response.get('output', '')
                else:
                    output = str(agent_response)

                # Try different methods to extract SQL and results
                sql_query = ''
                raw_results = []

                # Method 1: Try direct JSON parsing
                try:
                    if isinstance(output, str):
                        response_data = json.loads(output)
                    else:
                        response_data = output
                    sql_query = response_data.get('sql_query', '')
                    raw_results = response_data.get('sql_result', [])
                except json.JSONDecodeError:
                    logger.info("Direct JSON parsing failed, trying regex")
                    # Method 2: Try regex extraction
                    sql_match = re.search(r'"sql_query":\s*"([^"]+)"', output)
                    results_match = re.search(r'"sql_result":\s*(\[.*?\])', output, re.DOTALL)
                    
                    if sql_match:
                        sql_query = sql_match.group(1)
                    if results_match:
                        try:
                            raw_results = json.loads(results_match.group(1))
                        except:
                            raw_results = self._parse_tuple_string(results_match.group(1))

                # If we still don't have results, try one more method
                if not raw_results and isinstance(output, str):
                    # Method 3: Look for any list-like structure in the output
                    list_match = re.search(r'\[(.*?)\]', output, re.DOTALL)
                    if list_match:
                        try:
                            raw_results = json.loads(f"[{list_match.group(1)}]")
                        except:
                            raw_results = self._parse_tuple_string(list_match.group(1))

                if not sql_query or not raw_results:
                    logger.error("Could not extract SQL query or results")
                    return {
                        "type": "error",
                        "error": "Could not parse agent response",
                        "raw_response": output,
                        "query": self.query
                    }

                # Remove LIMIT clause for complete results
                base_query = re.sub(r"\s+LIMIT\s+\d+", "", sql_query, flags=re.IGNORECASE).strip()
                logger.info(f"Executing query: {base_query}")
                
                # Convert results to DataFrame
                df = self._convert_to_dataframe(raw_results)
                if df.empty:
                    return {
                        "type": "error",
                        "error": "No data found in response",
                        "query": self.query
                    }
                
                # Save results
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                base_path = os.path.join(self.save_path, f"query_results_{timestamp}")
                
                # Save as CSV
                csv_path = f"{base_path}.csv"
                df.to_csv(csv_path, index=False)
                logger.info(f"Saved results to CSV: {csv_path}")
                
                # Save as JSON
                json_path = f"{base_path}.json"
                df.to_json(json_path, orient='records', indent=2)
                logger.info(f"Saved results to JSON: {json_path}")
                
                return {
                    "type": "tabular",
                    "data": df.to_dict(orient='records'),
                    "row_count": len(df),
                    "columns": df.columns.tolist(),
                    "csv_path": csv_path,
                    "json_path": json_path,
                    "query": self.query,
                    "sql_query": base_query
                }
                
            except Exception as e:
                logger.error(f"Error processing response: {str(e)}")
                return {
                    "type": "error",
                    "error": f"Error processing response: {str(e)}",
                    "raw_response": str(agent_response),
                    "query": self.query
                }
            
        except Exception as e:
            error_msg = f"Error executing SQL query: {str(e)}"
            logger.error(error_msg)
            return {
                "type": "error",
                "error": error_msg,
                "query": self.query
            }

    async def arun(self, *args, **kwargs) -> dict:
        """Asynchronous version of run."""
        return self.run()