from agency_swarm.tools import BaseTool
from pydantic import Field, ConfigDict
import os
import logging
import pandas as pd
import json
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from retail_agency.reporting_manager.tools.utils.QueryGenerator import QueryGenerator
from retail_agency.reporting_manager.tools.utils.gcs_storage import GCSStorage
import re

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SQLQueryTool(BaseTool):
    """
    A tool for executing natural language queries against a SQL database.
    This tool converts natural language to SQL, executes the query, and saves results 
    to GCS. It returns only the GCS URIs, question, and query for further processing
    by other tools.
    """
    
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    # Input fields
    question: str = Field(
        ..., 
        description="Natural language question to be converted to SQL query"
    )
    db_schema: str = Field(
        default=os.getenv('CLOUD_SCHEMA'),
        description="Database schema to query against"
    )
    top_k: int = Field(
        default=10,
        description="Maximum number of results to return before requiring full query"
    )
    
    def __init__(self, **data):
        super().__init__(**data)
        
        # Initialize database connection
        db_uri = f"postgresql+psycopg2://{os.getenv('CLOUD_DB_USER')}:{os.getenv('CLOUD_DB_PASS')}@{os.getenv('CLOUD_DB_HOST')}:{os.getenv('CLOUD_DB_PORT')}/{os.getenv('CLOUD_DB_NAME')}"
        
        # Initialize QueryGenerator as a private attribute
        self._query_generator = QueryGenerator(db_uri, schema=self.db_schema)
        
        # Initialize GCS storage
        self._gcs = GCSStorage()
    
    def _save_to_gcs(self, data: pd.DataFrame, query_result: Dict[str, Any], timestamp: str) -> Dict[str, str]:
        """Save results to GCS and return URIs."""
        header_uri = f"gs://agent-memory/query-generator/header/query_header_{timestamp}.json"
        response_uri = f"gs://agent-memory/query-generator/response/query_response_{timestamp}.csv"
        
        # Save metadata to header file
        self._gcs.save_json({
            "question": self.question,
            "sql_query": query_result['sql_query'],
            "columns": list(data.columns),
            "total_records": len(data),
            "timestamp": timestamp,
            "metadata": {
                "has_stock_data": "stock_count" in data.columns,
                "has_sales_data": any(col for col in data.columns if 'sales' in col.lower()),
                "required_columns": ["item_id", "name", "stock_count"]  # Ensure these columns are always included
            }
        }, header_uri)
        
        # Save results to response file
        self._gcs.save_dataframe(data, response_uri)
        
        return {
            "header_uri": header_uri,
            "response_uri": response_uri
        }
    
    def _convert_to_dataframe(self, query_result: Dict[str, Any]) -> pd.DataFrame:
        """Convert query result to pandas DataFrame."""
        if not query_result.get('sql_result') or not query_result.get('columns'):
            return pd.DataFrame()
            
        return pd.DataFrame(query_result['sql_result'], columns=query_result['columns'])

    def _execute_traditional_query(self, base_query: str) -> pd.DataFrame:
        """Execute a SQL query directly using SQLAlchemy, without token limits."""
        try:
            # Remove any existing LIMIT/OFFSET clauses
            clean_query = re.sub(r'\bLIMIT\s+\d+\s*', '', base_query, flags=re.IGNORECASE)
            clean_query = re.sub(r'\bOFFSET\s+\d+\s*', '', clean_query, flags=re.IGNORECASE)
            
            logger.info(f"Executing traditional query: {clean_query}")
            
            with self._query_generator.engine.connect() as conn:
                result = conn.execute(text(clean_query))
                columns = result.keys()
                rows = result.fetchall()
                
                return pd.DataFrame(rows, columns=columns)
                
        except Exception as e:
            logger.error(f"Error executing traditional query: {str(e)}")
            raise
    
    def run(self):
        """Execute the SQL query and return GCS URIs."""
        try:
            # Step 1: Generate SQL query from natural language using QueryGenerator
            logger.info(f"[DEBUG] Generating SQL query for: {self.question}")
            query_result = self._query_generator.generate_query(self.question)
            
            if not query_result or not query_result.get('sql_query'):
                logger.error("[DEBUG] Failed to generate SQL query")
                return json.dumps({"error": "Failed to generate SQL query"})
            
            # Log the generated query
            logger.info(f"[DEBUG] Generated query: {query_result['sql_query']}")
            logger.info(f"[DEBUG] Initial query result: {json.dumps(query_result, indent=2)}")
            
            # Step 2: Check initial results from the query generator
            sql_result = query_result.get('sql_result', [])
            result_length = len(sql_result)
            logger.info(f"[DEBUG] Initial result length: {result_length}")
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            if result_length > 0 and result_length < self.top_k:
                # If we have results and they're less than top_k, use them directly
                logger.info(f"[DEBUG] Using existing results (count: {result_length})")
                df = self._convert_to_dataframe(query_result)
            else:
                # If we have no results or have hit/exceeded the limit, use traditional query
                logger.info("[DEBUG] Result size >= top_k, executing traditional query")
                df = self._execute_traditional_query(query_result['sql_query'])
            
            logger.info(f"[DEBUG] DataFrame shape: {df.shape}")
            logger.info(f"[DEBUG] DataFrame columns: {list(df.columns)}")
            logger.info(f"[DEBUG] First few rows: \n{df.head().to_string()}")
            
            # Step 3: Store results in GCS
            gcs_uris = self._save_to_gcs(df, query_result, timestamp)
            logger.info(f"[DEBUG] GCS URIs: {json.dumps(gcs_uris, indent=2)}")
            
            # Return minimal response with URIs and metadata
            response = {
                "question": self.question,
                "sql_query": query_result['sql_query'],
                "gcs_uris": gcs_uris,
                "metadata": {
                    "has_stock_data": "stock_count" in df.columns,
                    "total_records": len(df),
                    "columns": list(df.columns)
                }
            }
            
            logger.info(f"[DEBUG] Final response: {json.dumps(response, indent=2)}")
            return json.dumps(response)
                
        except Exception as e:
            error_msg = f"Error executing query: {str(e)}"
            logger.error(error_msg)
            return json.dumps({"error": error_msg})


if __name__ == "__main__":
    # Test the SQLQueryTool
    tool = SQLQueryTool(
        question="Show me inventory items with stock count below 5"
    )
    
    try:
        result = tool.run()
        result_dict = json.loads(result)
        
        print("\nQuery Results:")
        print("=" * 50)
        print(f"Question: {result_dict.get('question')}")
        print(f"SQL Query: {result_dict.get('sql_query')}")
        print("\nStored Results:")
        print("=" * 50)
        for key, uri in result_dict.get('gcs_uris', {}).items():
            print(f"{key}: {uri}")
                
    except Exception as e:
        print(f"\nError running test: {str(e)}")
        logger.error(f"Test error details: {str(e)}", exc_info=True)