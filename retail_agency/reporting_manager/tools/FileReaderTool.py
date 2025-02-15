from agency_swarm.tools import BaseTool
from pydantic import Field, PrivateAttr
import os
import logging
import pandas as pd
import json
from datetime import datetime
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
import sys
import gcsfs
from retail_agency.reporting_manager.tools.utils.gcs_storage import GCSStorage

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FileReaderTool(BaseTool):
    """
    A tool for querying and analyzing data stored in Google Cloud Storage.
    This tool can read CSV files directly from GCS URLs into pandas DataFrames
    and use an LLM to analyze the data and answer questions about it.
    """
    
    # Private attributes for GCS and LLM
    _gcs: GCSStorage = PrivateAttr()
    _llm: ChatOpenAI = PrivateAttr()
    _fs: gcsfs.GCSFileSystem = PrivateAttr()
    
    # Query parameters
    question: str = Field(
        ...,
        description="Natural language question about the data"
    )
    gcs_uri: str = Field(
        ...,
        description="GCS URI of the CSV file to query (gs://bucket/path/to/file.csv)"
    )
    max_rows: int = Field(
        default=1000,
        description="Maximum number of rows to load from the CSV"
    )
    use_local_file: bool = Field(
        default=False,
        description="Whether to use a local file instead of GCS (for testing)"
    )
    
    def __init__(self, **data):
        """Initialize the tool with GCS storage and LLM."""
        super().__init__(**data)
        
        # Initialize GCS storage if not using local file
        if not self.use_local_file:
            try:
                self._gcs = GCSStorage()
                logger.info("Successfully initialized GCS storage")
                
                # Initialize gcsfs with the same credentials
                credentials_path = os.getenv('DB_CREDENTIALS_PATH')
                if not credentials_path:
                    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
                    credentials_path = os.path.join(project_root, 'google-credentials.json')
                
                self._fs = gcsfs.GCSFileSystem(token=credentials_path)
                logger.info("Successfully initialized gcsfs")
                
            except Exception as e:
                logger.error(f"Failed to initialize GCS storage: {str(e)}")
                raise
        
        # Initialize LLM
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        
        self._llm = ChatOpenAI(
            model="gpt-4",
            temperature=0,
            api_key=api_key
        )
        logger.info("Successfully initialized LLM")
    
    def _read_local_csv(self) -> pd.DataFrame:
        """Read a local CSV file for testing."""
        try:
            # For testing, interpret gcs_uri as local path
            if not os.path.exists(self.gcs_uri):
                raise ValueError(f"Local file not found: {self.gcs_uri}")
            
            df = pd.read_csv(self.gcs_uri)
            
            # Limit rows if specified
            if len(df) > self.max_rows:
                logger.info(f"Limiting DataFrame to {self.max_rows} rows")
                df = df.head(self.max_rows)
            
            logger.info(f"Successfully read {len(df)} rows from {self.gcs_uri}")
            return df
            
        except Exception as e:
            logger.error(f"Failed to read local CSV: {str(e)}")
            raise
    
    def _read_csv_from_gcs(self) -> pd.DataFrame:
        """Read CSV file directly from GCS into pandas DataFrame using gcsfs."""
        try:
            # Validate GCS URI format
            if not self.gcs_uri.startswith('gs://'):
                raise ValueError("Invalid GCS URI format. Must start with 'gs://'")
            
            # Read CSV directly from GCS using gcsfs
            logger.info(f"Reading CSV directly from GCS: {self.gcs_uri}")
            with self._fs.open(self.gcs_uri) as f:
                df = pd.read_csv(f)
            
            # Limit rows if specified
            if len(df) > self.max_rows:
                logger.info(f"Limiting DataFrame to {self.max_rows} rows")
                df = df.head(self.max_rows)
            
            logger.info(f"Successfully read {len(df)} rows from {self.gcs_uri}")
            return df
            
        except FileNotFoundError:
            logger.error(f"File not found in GCS: {self.gcs_uri}")
            raise
        except Exception as e:
            logger.error(f"Failed to read CSV from GCS: {str(e)}")
            raise
    
    def _get_data_insights(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Generate statistical insights about the DataFrame."""
        insights = {
            "total_rows": len(df),
            "total_columns": len(df.columns),
            "column_names": list(df.columns),
            "numeric_columns": list(df.select_dtypes(include=['int64', 'float64']).columns),
            "categorical_columns": list(df.select_dtypes(include=['object', 'category']).columns),
            "missing_values": df.isnull().sum().to_dict(),
            "numeric_stats": {}
        }
        
        # Calculate statistics for numeric columns
        for col in insights["numeric_columns"]:
            insights["numeric_stats"][col] = {
                "mean": float(df[col].mean()),
                "median": float(df[col].median()),
                "std": float(df[col].std()),
                "min": float(df[col].min()),
                "max": float(df[col].max())
            }
        
        return insights
    
    def _analyze_data(self, df: pd.DataFrame) -> str:
        """Use LLM to analyze the data and answer the question."""
        try:
            # Get data insights
            insights = self._get_data_insights(df)
            logger.info(f"[DEBUG] Data insights: {json.dumps(insights, indent=2)}")
            
            # Create prompt
            prompt = f"""You are analyzing inventory data with the following structure and statistics:

Total Rows: {insights['total_rows']}
Total Columns: {insights['total_columns']}
Columns: {', '.join(insights['column_names'])}

Data Preview:
{df.head().to_string()}

Statistical Summary:
"""
            # Add numeric statistics
            for col, stats in insights['numeric_stats'].items():
                prompt += f"\n{col}:"
                for stat_name, value in stats.items():
                    prompt += f"\n  - {stat_name}: {value:.2f}"
            
            # Add specific analysis guidance for inventory data
            if 'stock_count' in df.columns:
                prompt += "\n\nStock Level Analysis:"
                critical_items = len(df[df['stock_count'] <= 0])
                low_stock = len(df[df['stock_count'] > 0][df['stock_count'] < 5])
                prompt += f"\n- Critical (Out of Stock): {critical_items} items"
                prompt += f"\n- Low Stock (1-4 units): {low_stock} items"
            
            prompt += f"\n\nQuestion: {self.question}\n"
            prompt += """
Please provide a clear, detailed analysis that:
1. Directly answers the question
2. Highlights critical inventory issues (if stock data is present)
3. Provides specific item details and their stock levels
4. Groups items by urgency:
   - Critical (0 or negative stock)
   - Low Stock (1-4 units)
5. Suggests immediate actions needed
6. Notes any data quality issues or limitations

Format your response in a clear, structured way using markdown."""

            logger.info(f"[DEBUG] Analysis prompt: {prompt}")
            
            # Get response from LLM
            response = self._llm.invoke(prompt)
            logger.info(f"[DEBUG] LLM response: {response.content}")
            return response.content
            
        except Exception as e:
            logger.error(f"Failed to analyze data: {str(e)}")
            raise
    
    def run(self) -> str:
        """Execute the tool's functionality."""
        try:
            # Read data from file
            logger.info(f"[DEBUG] Reading data from {self.gcs_uri}")
            if self.use_local_file:
                df = self._read_local_csv()
            else:
                df = self._read_csv_from_gcs()
            
            logger.info(f"[DEBUG] DataFrame shape: {df.shape}")
            logger.info(f"[DEBUG] DataFrame columns: {list(df.columns)}")
            logger.info(f"[DEBUG] First few rows: \n{df.head().to_string()}")
            
            # Analyze data using LLM
            logger.info("[DEBUG] Starting data analysis with LLM")
            analysis = self._analyze_data(df)
            
            logger.info(f"[DEBUG] Analysis result: {analysis[:500]}...")  # Log first 500 chars
            return analysis
            
        except Exception as e:
            error_msg = f"Error executing FileReaderTool: {str(e)}"
            logger.error(error_msg)
            return f"Error: {error_msg}"

if __name__ == "__main__":
    # Test the tool
    load_dotenv()
    
    # Example usage with GCS file
    tool = FileReaderTool(
        question="What are the items with the lowest stock count, and what patterns do you notice in their categories and prices?",
        gcs_uri="gs://agent-memory/query-generator/response/query_response_20250214_155836.csv",  # Using actual GCS file
        max_rows=100,
        use_local_file=False  # Use GCS instead of local file
    )
    
    try:
        result = tool.run()
        print("\nAnalysis Result:")
        print("=" * 50)
        print(result)
        
    except Exception as e:
        print(f"Test failed: {str(e)}")
        logger.error("Test failed", exc_info=True) 