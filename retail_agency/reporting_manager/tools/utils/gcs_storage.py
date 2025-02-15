from google.cloud import storage
import os
import json
from datetime import datetime
from typing import Dict, Any, Tuple
import logging
from dotenv import load_dotenv
import pandas as pd

logger = logging.getLogger(__name__)

class GCSStorage:
    """Utility class for Google Cloud Storage operations"""
    
    def __init__(self):
        """Initialize the GCS client"""
        load_dotenv()
        
        self.bucket_name = "agent-memory"
        self.header_path = "query-generator/header"
        self.response_path = "query-generator/response"
        
        # Get credentials path from environment
        credentials_path = os.getenv('DB_CREDENTIALS_PATH')
        if not credentials_path:
            # Try to find credentials in the project directory
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            credentials_path = os.path.join(project_root, 'google-credentials.json')
        
        if not os.path.exists(credentials_path):
            raise ValueError(f"Google credentials file not found at {credentials_path}")
        
        try:
            # Initialize with explicit credentials
            self.client = storage.Client.from_service_account_json(credentials_path)
            self.bucket = self.client.bucket(self.bucket_name)
            logger.info(f"Successfully initialized GCS client with credentials from {credentials_path}")
        except Exception as e:
            logger.error(f"Failed to initialize GCS client: {str(e)}")
            raise
    
    def upload_query_result(self, query_result: Dict[str, Any]) -> Dict[str, str]:
        """
        Upload query result to GCS, splitting header and response data
        
        Args:
            query_result: Dictionary containing query results
            
        Returns:
            Dict[str, str]: GCS URIs of the uploaded files
        """
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            # Prepare header data (metadata without results)
            header_data = {
                "question": query_result.get("question"),
                "sql_query": query_result.get("sql_query"),
                "columns": query_result.get("columns"),
                "limit_requested": query_result.get("limit_requested", False),
                "total_records": query_result.get("total_records", 0),
                "timestamp": timestamp
            }
            
            # Upload header JSON
            header_filename = f"{self.header_path}/query_header_{timestamp}.json"
            header_blob = self.bucket.blob(header_filename)
            header_blob.upload_from_string(
                json.dumps(header_data, indent=2),
                content_type='application/json'
            )
            
            # Prepare response data (just the results)
            response_filename = f"{self.response_path}/query_response_{timestamp}.csv"
            response_blob = self.bucket.blob(response_filename)
            
            # Create CSV string from results
            if not query_result.get("sql_result"):
                logger.warning("No SQL results found in query_result")
                csv_data = ""
            else:
                import io
                import csv
                output = io.StringIO()
                writer = csv.writer(output)
                
                # Write headers
                if query_result.get("columns"):
                    writer.writerow(query_result["columns"])
                
                # Write data rows
                writer.writerows(query_result["sql_result"])
                csv_data = output.getvalue()
                output.close()
            
            # Upload CSV response
            response_blob.upload_from_string(
                csv_data,
                content_type='text/csv'
            )
            
            return {
                "header_uri": f"gs://{self.bucket_name}/{header_filename}",
                "response_uri": f"gs://{self.bucket_name}/{response_filename}"
            }
            
        except Exception as e:
            logger.error(f"Failed to upload query result to GCS: {str(e)}")
            raise
    
    def upload_file(self, file_path: str, is_header: bool = True) -> str:
        """
        Upload a local file to GCS
        
        Args:
            file_path: Path to the local file
            is_header: If True, upload to header path, else to response path
            
        Returns:
            str: GCS URI of the uploaded file
        """
        try:
            base_path = self.header_path if is_header else self.response_path
            destination_blob_name = os.path.join(
                base_path,
                os.path.basename(file_path)
            )
            
            blob = self.bucket.blob(destination_blob_name)
            blob.upload_from_filename(file_path)
            
            gcs_uri = f"gs://{self.bucket_name}/{destination_blob_name}"
            logger.info(f"Successfully uploaded file to {gcs_uri}")
            return gcs_uri
            
        except Exception as e:
            logger.error(f"Failed to upload file to GCS: {str(e)}")
            raise
    
    def save_json(self, data: Dict[str, Any], destination: str) -> None:
        """
        Save JSON data to GCS
        
        Args:
            data: Dictionary to save as JSON
            destination: Full GCS path (gs://bucket/path/to/file.json)
        """
        try:
            # Remove bucket name from destination
            if destination.startswith('gs://'):
                destination = destination.replace(f'gs://{self.bucket_name}/', '')
            
            # Create blob and upload
            blob = self.bucket.blob(destination)
            blob.upload_from_string(
                json.dumps(data, indent=2),
                content_type='application/json'
            )
            logger.info(f"Successfully saved JSON to {destination}")
            
        except Exception as e:
            logger.error(f"Failed to save JSON to GCS: {str(e)}")
            raise
    
    def save_dataframe(self, df: pd.DataFrame, destination: str) -> None:
        """
        Save DataFrame to GCS as CSV
        
        Args:
            df: pandas DataFrame to save
            destination: Full GCS path (gs://bucket/path/to/file.csv)
        """
        try:
            # Remove bucket name from destination
            if destination.startswith('gs://'):
                destination = destination.replace(f'gs://{self.bucket_name}/', '')
            
            # Convert DataFrame to CSV string
            csv_data = df.to_csv(index=False)
            
            # Create blob and upload
            blob = self.bucket.blob(destination)
            blob.upload_from_string(
                csv_data,
                content_type='text/csv'
            )
            logger.info(f"Successfully saved DataFrame to {destination}")
            
        except Exception as e:
            logger.error(f"Failed to save DataFrame to GCS: {str(e)}")
            raise

    def _read_json(self, uri: str) -> Dict:
        """Read a JSON file from GCS.
        
        Args:
            uri (str): The GCS URI of the JSON file to read.
            
        Returns:
            Dict: The contents of the JSON file.
        """
        try:
            # Extract bucket and blob name from URI
            bucket_name, blob_name = self._parse_uri(uri)
            
            # Get the bucket and blob
            bucket = self.client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            
            # Download and parse JSON
            json_content = blob.download_as_text()
            return json.loads(json_content)
            
        except Exception as e:
            logger.error(f"Error reading JSON from GCS: {str(e)}")
            return {}

    def _parse_uri(self, uri: str) -> Tuple[str, str]:
        """Parse a GCS URI into bucket and blob names.
        
        Args:
            uri (str): The GCS URI to parse (e.g., 'gs://bucket-name/path/to/file.txt')
            
        Returns:
            Tuple[str, str]: A tuple of (bucket_name, blob_name)
            
        Raises:
            ValueError: If the URI is not a valid GCS URI
        """
        if not uri.startswith('gs://'):
            raise ValueError(f"Invalid GCS URI: {uri}")
        
        # Remove 'gs://' prefix
        path = uri[5:]
        
        # Split into bucket and blob names
        parts = path.split('/', 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid GCS URI format: {uri}")
        
        bucket_name, blob_name = parts
        return bucket_name, blob_name

if __name__ == "__main__":
    # Test the GCS storage utility
    try:
        gcs = GCSStorage()
        
        # Test saving JSON
        test_json = {
            "question": "Test query",
            "sql_query": "SELECT * FROM test",
            "columns": ["col1", "col2"],
            "total_records": 2
        }
        json_uri = "gs://agent-memory/query-generator/header/test_header.json"
        gcs.save_json(test_json, json_uri)
        print(f"Successfully saved JSON to {json_uri}")
        
        # Test saving DataFrame
        test_df = pd.DataFrame({
            "col1": [1, 2],
            "col2": ["test1", "test2"]
        })
        csv_uri = "gs://agent-memory/query-generator/response/test_response.csv"
        gcs.save_dataframe(test_df, csv_uri)
        print(f"Successfully saved DataFrame to {csv_uri}")
        
    except Exception as e:
        print(f"Test failed: {str(e)}") 