from agency_swarm.tools import BaseTool
from pydantic import Field
from google.cloud import storage
from google.oauth2 import service_account
import os
import json
import time
from datetime import datetime, timedelta
import logging
from typing import Union, Optional

logger = logging.getLogger(__name__)

class CloudStorageTool(BaseTool):
    """
    Tool for uploading data to Google Cloud Storage and generating downloadable links.
    Supports uploading JSON data and generating signed URLs for secure access.
    """
    
    data: Union[dict, str] = Field(
        ...,
        description="Data to upload to Cloud Storage. Can be a dictionary or JSON string."
    )
    
    file_name: str = Field(
        ...,
        description="Base name for the file (without extension)"
    )
    
    expiration_hours: int = Field(
        default=24,
        description="Number of hours the download link should remain valid"
    )
    
    bucket_name: str = Field(
        default="agent-memory",
        description="Name of the Cloud Storage bucket"
    )

    def run(self) -> dict:
        """Upload data and generate a signed URL for download."""
        try:
            # Get credentials path
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
            creds_path = os.path.join(project_root, os.getenv("DB_CREDENTIALS_PATH"))

            if not os.path.exists(creds_path):
                raise FileNotFoundError(f"Credentials file not found at: {creds_path}")
            
            # Initialize credentials
            credentials = service_account.Credentials.from_service_account_file(
                creds_path,
                scopes=[
                    'https://www.googleapis.com/auth/cloud-platform',
                    'https://www.googleapis.com/auth/devstorage.read_write'
                ]
            )
            
            # Initialize storage client
            storage_client = storage.Client(
                credentials=credentials,
                project=credentials.project_id
            )
            
            # Get bucket
            bucket = storage_client.bucket(self.bucket_name)
            
            # Create timestamped filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            blob_name = f"shared_files/{timestamp}_{self.file_name}.json"
            blob = bucket.blob(blob_name)
            
            # Convert data to JSON string if needed
            json_data = json.dumps(self.data, default=str) if isinstance(self.data, dict) else self.data
            
            # Upload with retry
            retry_count = 0
            max_retries = 3
            while retry_count < max_retries:
                try:
                    # Upload file
                    blob.upload_from_string(
                        json_data,
                        content_type='application/json'
                    )
                    
                    # Generate signed URL
                    expiration = datetime.now() + timedelta(hours=self.expiration_hours)
                    signed_url = blob.generate_signed_url(
                        version="v4",
                        expiration=expiration,
                        method="GET"
                    )
                    
                    logger.info(f"Successfully uploaded and generated signed URL: {blob_name}")
                    
                    return {
                        "status": "success",
                        "file_path": f"gs://{self.bucket_name}/{blob_name}",
                        "download_url": signed_url,
                        "expires_at": expiration.isoformat(),
                        "file_name": blob_name
                    }
                    
                except Exception as e:
                    retry_count += 1
                    if retry_count == max_retries:
                        logger.error(f"Failed to upload after {max_retries} attempts: {str(e)}")
                        raise
                    logger.warning(f"Upload attempt {retry_count} failed: {str(e)}")
                    time.sleep(1)
            
        except Exception as e:
            logger.error(f"Error in Cloud Storage operation: {str(e)}")
            return {
                "status": "error",
                "error": str(e)
            }

if __name__ == "__main__":
    # Test the tool
    test_data = {
        "test": "data",
        "timestamp": datetime.now().isoformat()
    }
    
    tool = CloudStorageTool(
        data=test_data,
        file_name="test_upload"
    )
    
    result = tool.run()
    print("Result:", result) 