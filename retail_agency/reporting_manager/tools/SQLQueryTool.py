import re
import os
import logging
import pandas as pd
import json
from datetime import datetime
from typing import Any, Optional, List, Dict, Tuple
from ast import literal_eval
from decimal import Decimal

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
    
    # Class fields
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

    sql_query: Optional[str] = Field(
        default=None,
        description="The SQL query generated from the natural language query"
    )
    
    _db: Optional[SQLDatabase] = None
    _agent_executor: Optional[Any] = None

    def __init__(self, **data):
        super().__init__(**data)
        os.makedirs(self.save_path, exist_ok=True)
        self.sql_query = None
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

    def _extract_sql_and_results(self, response: Dict[str, Any]) -> Tuple[str, List[Tuple], List[str]]:
        """Extract SQL query, results, and columns from agent response."""
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
            columns = parsed_output.get('columns', [])

            # If results are a string representation of a list of tuples
            if isinstance(raw_results, str):
                results = self._parse_tuple_string(raw_results)
            else:
                results = raw_results

            return sql_query, results, columns

        except json.JSONDecodeError:
            # Fallback to regex extraction if JSON parsing fails
            output = str(response.get('output', ''))
            sql_match = re.search(r'"sql_query":\s*"([^"]+)"', output)
            results_match = re.search(r'"sql_result":\s*(\[.*?\])', output, re.DOTALL)
            
            sql_query = sql_match.group(1) if sql_match else ''
            results = self._parse_tuple_string(results_match.group(1)) if results_match else []
            
            # Try to extract columns
            columns_match = re.search(r'"columns":\s*(\[.*?\])', output, re.DOTALL)
            try:
                columns = json.loads(columns_match.group(1)) if columns_match else []
            except:
                columns = []
            
            return sql_query, results, columns

        except Exception as e:
            logger.error(f"Error extracting SQL and results: {str(e)}")
            return '', [], []

    def _convert_to_dataframe(self, results: Any, provided_columns: List[str] = None) -> pd.DataFrame:
        """Convert SQL query results to DataFrame."""
        try:
            # Handle empty results
            if not results:
                logger.info("No results to convert to DataFrame")
                return pd.DataFrame()

            # Convert Decimal objects to float
            def convert_value(val):
                if isinstance(val, Decimal):
                    return float(val)
                if val == '':  # Handle empty strings
                    return None
                return val

            # If we have results, create a list of dictionaries
            data = []
            if isinstance(results, list):
                # Get columns, either provided or generated
                if provided_columns:
                    columns = provided_columns
                elif results and isinstance(results[0], (tuple, list)):
                    columns = [f"column_{i}" for i in range(len(results[0]))]
                else:
                    columns = [f"column_{i}" for i in range(1)]

                # Convert results to list of dictionaries
                for row in results:
                    if isinstance(row, (tuple, list)):
                        row_data = {col: convert_value(val) for col, val in zip(columns, row)}
                    else:
                        row_data = {columns[0]: convert_value(row)}
                    data.append(row_data)

                logger.info(f"Creating DataFrame with {len(data)} rows and columns: {columns}")
                return pd.DataFrame(data)
            else:
                # Single value result
                logger.info("Converting single value to DataFrame")
                return pd.DataFrame([{provided_columns[0] if provided_columns else 'value': convert_value(results)}])

        except Exception as e:
            logger.error(f"Error in _convert_to_dataframe: {str(e)}", exc_info=True)
            # Create empty DataFrame with correct columns as fallback
            return pd.DataFrame(columns=provided_columns if provided_columns else None)

    def _save_results(self, df: pd.DataFrame, base_path: str) -> Dict[str, str]:
        """Save results to both CSV and JSON files with proper column names."""
        if df.empty:
            logger.warning("No data to save")
            return {}

        paths = {}
        try:
            # Save CSV
            csv_path = f"{base_path}.csv"
            df.to_csv(csv_path, index=False)
            paths['csv'] = csv_path
            logger.info(f"Saved results to CSV: {csv_path}")

            # Save JSON with proper structure
            json_path = f"{base_path}.json"
            json_data = {
                "columns": df.columns.tolist(),
                "data": df.to_dict(orient='records')
            }
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(json_data, indent=2, ensure_ascii=False)
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
            
            # Extract data from response
            sql_query = ''
            raw_results = []
            columns = []
            
            # Parse the JSON response
            if isinstance(agent_response, dict) and 'output' in agent_response:
                try:
                    # Parse the response
                    response_data = json.loads(agent_response['output'])
                    sql_query = response_data.get('sql_query', '')
                    raw_results = response_data.get('sql_result', [])
                    columns = response_data.get('columns', [])
                    logger.info(f"Extracted columns from response: {columns}")
                    
                except json.JSONDecodeError:
                    # Fallback to regex if JSON parsing fails
                    output = str(agent_response['output'])
                    sql_match = re.search(r'"sql_query":\s*"([^"]+)"', output)
                    sql_query = sql_match.group(1) if sql_match else ''
                    
                    # Extract results
                    results_match = re.search(r'"sql_result":\s*(\[.*?\])', output, re.DOTALL)
                    if results_match:
                        try:
                            raw_results = json.loads(results_match.group(1))
                        except:
                            raw_results = self._parse_tuple_string(results_match.group(1))
                    
                    # Extract columns
                    columns_match = re.search(r'"columns":\s*(\[.*?\])', output, re.DOTALL)
                    if columns_match:
                        try:
                            columns = json.loads(columns_match.group(1))
                            logger.info(f"Extracted columns from regex: {columns}")
                        except:
                            columns = []
            else:
                raise ValueError("Invalid response format from agent")

            if not sql_query:
                raise ValueError("Failed to extract SQL query from response")
            
            # Clean and store SQL query
            self.sql_query = re.sub(r"\s+LIMIT\s+\d+", "", sql_query, flags=re.IGNORECASE).strip()
            logger.info(f"Executing query: {self.sql_query}")
            
            # Execute the query
            db_results = self._db.run(self.sql_query)
            logger.info(f"Received results type: {type(db_results)}")
            if db_results:
                logger.info(f"First result type: {type(db_results[0]) if isinstance(db_results, list) else 'not a list'}")
            
            # Convert results to DataFrame with columns
            df = self._convert_to_dataframe(db_results, columns)
            
            # Save results
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            base_path = os.path.join(self.save_path, f"query_results_{timestamp}")
            
            # Save results and get file paths
            file_paths = self._save_results(df, base_path)
            
            return {
                "type": "tabular",
                "data": {
                    "columns": df.columns.tolist() if not df.empty else [],
                    "rows": df.to_dict(orient='records') if not df.empty else []
                },
                "row_count": len(df),
                "csv_path": file_paths.get('csv', ''),
                "json_path": file_paths.get('json', ''),
                "query": self.query,
                "sql_query": self.sql_query
            }
            
        except Exception as e:
            error_msg = f"Error executing SQL query: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"type": "error", "error": error_msg}
            
        except Exception as e:
            error_msg = f"Error executing SQL query: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"type": "error", "error": error_msg}
            
        except Exception as e:
            error_msg = f"Error executing SQL query: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"type": "error", "error": error_msg}
            
        except Exception as e:
            error_msg = f"Error executing SQL query: {str(e)}"
            logger.error(error_msg)
            return {"type": "error", "error": error_msg}

    async def arun(self, *args, **kwargs) -> dict:
        """Asynchronous version of run."""
        return self.run()