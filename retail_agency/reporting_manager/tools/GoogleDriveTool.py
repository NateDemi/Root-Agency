from agency_swarm.tools import BaseTool
from pydantic import Field, ConfigDict
import os
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build
import pandas as pd
import logging
from typing import Optional, Dict, Any, List, Union
from datetime import datetime
from retail_agency.reporting_manager.tools.FileReaderTool import FileReaderTool

load_dotenv()

logger = logging.getLogger(__name__)

# Load Google credentials
GOOGLE_CREDS_PATH = os.getenv("DB_CREDENTIALS_PATH")
if not GOOGLE_CREDS_PATH:
    raise ValueError("DB_CREDENTIALS_PATH environment variable is not set")

# Get absolute path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
creds_path = os.path.join(project_root, GOOGLE_CREDS_PATH)

if not os.path.exists(creds_path):
    raise FileNotFoundError(f"Credentials file not found at: {creds_path}")

try:
    # Initialize credentials with required scopes
    credentials = service_account.Credentials.from_service_account_file(
        creds_path,
        scopes=[
            'https://www.googleapis.com/auth/drive.file',
            'https://www.googleapis.com/auth/spreadsheets'
        ]
    )
    
    # Build services
    drive_service = build('drive', 'v3', credentials=credentials)
    sheets_service = build('sheets', 'v4', credentials=credentials)
    logger.info("Google services initialized successfully")
except Exception as e:
    logger.error(f"Error initializing Google services: {str(e)}")
    raise

# Constants
SERVICE_ACCOUNT_EMAIL = "google-rr-service-account@perfect-rider-446204-h0.iam.gserviceaccount.com"
REPORTS_FOLDER_ID = "1CaIwU3hir-TuLIdPfVMUC6zHcAz4yjhZ"  # Agent-Reports folder ID

class GoogleDriveTool(BaseTool):
    """
    Tool for posting data directly to Google Sheets.
    Creates a simple spreadsheet with just the data, no extra formatting or metadata.
    """
    
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    folder_id: str = Field(
        REPORTS_FOLDER_ID,
        description="Google Drive folder ID where sheets will be stored"
    )
    
    title: str = Field(
        ...,
        description="Title of the sheet"
    )
    
    gcs_uri: str = Field(
        ...,
        description="GCS URI of the CSV file to read data from"
    )
    
    def run(self) -> dict:
        """Create a Google Sheet with data from the GCS URI."""
        try:
            # First read data from GCS using FileReader
            file_reader = FileReaderTool(
                question="Get raw data for Google Sheets export",
                gcs_uri=self.gcs_uri,
                max_rows=1000
            )
            
            # Load the data
            file_reader.run()
            df = file_reader._read_csv_from_gcs()
            
            # Format data
            formatted_data = self._format_data(df)
            
            # Create and populate sheet
            result = self._create_sheet(formatted_data)
            logger.info(f"Created sheet: {result['id']}")
            return {
                "status": "created",
                "sheet_id": result['id'],
                "url": result['webViewLink']
            }
                
        except Exception as e:
            logger.error(f"Error with Google Sheets operation: {str(e)}")
            raise

    def _format_data(self, data: Union[List[List[Any]], pd.DataFrame, Dict[str, Any]]) -> List[List[Any]]:
        """Convert data to list format for sheets."""
        if isinstance(data, pd.DataFrame):
            # Fill NaN values with empty string
            df_clean = data.fillna('')
            # Convert to list format
            return [df_clean.columns.tolist()] + df_clean.values.tolist()
        elif isinstance(data, dict):
            if all(isinstance(v, list) for v in data.values()):
                headers = list(data.keys())
                rows = list(zip(*data.values()))
                return [headers] + [list(row) for row in rows]
            else:
                return [[k, str(v)] for k, v in data.items()]
        return data

    def _create_sheet(self, data: List[List[Any]]) -> Dict[str, Any]:
        """Create a new Google Sheet with the data."""
        try:
            # Get the email to share with
            share_email = os.getenv("GOOGLE_DRIVE_EMAIL")
            if not share_email:
                raise ValueError("GOOGLE_DRIVE_EMAIL environment variable is not set")

            # Create file metadata
            file_metadata = {
                'name': self.title,
                'mimeType': 'application/vnd.google-apps.spreadsheet',
                'parents': [self.folder_id]
            }
            
            # Create sheet
            sheet = drive_service.files().create(
                body=file_metadata,
                fields='id, webViewLink',
                supportsAllDrives=True
            ).execute()
            
            # Share the sheet
            permission = {
                'type': 'user',
                'role': 'writer',
                'emailAddress': share_email
            }
            
            drive_service.permissions().create(
                fileId=sheet['id'],
                body=permission,
                sendNotificationEmail=False
            ).execute()
            
            # Update with data
            body = {'values': data}
            sheets_service.spreadsheets().values().update(
                spreadsheetId=sheet['id'],
                range='A1',
                valueInputOption='RAW',
                body=body
            ).execute()
            
            return sheet

        except Exception as e:
            logger.error(f"Error creating sheet: {str(e)}")
            raise


if __name__ == "__main__":
    # Test the tool
    try:
        # Test data
        test_data = pd.DataFrame({
            "Product": ["MacBook Pro", "iPhone", "iPad"],
            "Stock": [5, 20, 0],
            "Status": ["Low Stock", "In Stock", "Out of Stock"]
        })
        
        # Create sheet
        drive_tool = GoogleDriveTool(
            title="Inventory Status",
            gcs_uri="gs://your-bucket/inventory_status.csv"
        )
        
        result = drive_tool.run()
        print("\nTest Results:")
        print(f"Status: {result['status']}")
        print(f"Sheet URL: {result['url']}")
        
    except Exception as e:
        print(f"Error in test: {str(e)}") 