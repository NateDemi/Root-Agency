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

    def _convert_to_dataframe(self, results: Any) -> pd.DataFrame:
        """Convert SQL query results to DataFrame."""
        try:
            # Handle empty results
            if not results:
                return pd.DataFrame()

            # Handle list of tuples format
            if isinstance(results, list) and all(isinstance(x, tuple) for x in results):
                # Extract column names from the first tuple
                columns = ['item_id', 'name', 'stock_count']  # Hardcoded for now based on our query
                df = pd.DataFrame(results, columns=columns)
                logger.info(f"Created DataFrame with shape: {df.shape}")
                return df

            # Handle string format
            if isinstance(results, str):
                # Try to evaluate string as literal Python expression
                try:
                    data = literal_eval(results)
                    if isinstance(data, list) and data and isinstance(data[0], tuple):
                        columns = ['item_id', 'name', 'stock_count']
                        df = pd.DataFrame(data, columns=columns)
                        logger.info(f"Created DataFrame from string with shape: {df.shape}")
                        return df
                except:
                    pass

            # If all else fails, try to create DataFrame directly
            df = pd.DataFrame(results)
            logger.info(f"Created DataFrame from raw data with shape: {df.shape}")
            return df

        except Exception as e:
            logger.error(f"Error converting to DataFrame: {str(e)}")
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
            
            # Parse the JSON response
            if isinstance(agent_response, dict) and 'output' in agent_response:
                try:
                    response_data = json.loads(agent_response['output'])
                    sql_query = response_data.get('sql_query', '')
                    raw_results = response_data.get('sql_result', [])
                except json.JSONDecodeError:
                    # Fallback to regex if JSON parsing fails
                    output = str(agent_response['output'])
                    sql_match = re.search(r'"sql_query":\s*"([^"]+)"', output)
                    sql_query = sql_match.group(1) if sql_match else ''
                    results_match = re.search(r'"sql_result":\s*(\[.*?\])', output, re.DOTALL)
                    raw_results = results_match.group(1) if results_match else '[]'
            else:
                raise ValueError("Invalid response format from agent")

            if not sql_query:
                raise ValueError("Failed to extract SQL query from response")
            
            # Remove LIMIT clause for complete results
            base_query = re.sub(r"\s+LIMIT\s+\d+", "", sql_query, flags=re.IGNORECASE).strip()
            logger.info(f"Executing query: {base_query}")
            
            # Execute the full query
            db_results = self._db.run(base_query)
            
            # Convert results to DataFrame
            df = self._convert_to_dataframe(db_results)
            
            # Save results to both CSV and JSON
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
                "data": df.to_dict(orient='records') if not df.empty else [],
                "row_count": len(df),
                "columns": df.columns.tolist() if not df.empty else [],
                "csv_path": csv_path,
                "json_path": json_path,
                "query": self.query,
                "sql_query": base_query
            }
            
        except Exception as e:
            error_msg = f"Error executing SQL query: {str(e)}"
            logger.error(error_msg)
            return {"type": "error", "error": error_msg}

    async def arun(self, *args, **kwargs) -> dict:
        """Asynchronous version of run."""
        return self.run()