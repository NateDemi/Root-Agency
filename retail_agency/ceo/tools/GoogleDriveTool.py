from agency_swarm.tools import BaseTool
from pydantic import Field, ConfigDict
import os
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import pandas as pd
import logging
from typing import Optional, Dict, Any, List, Union
from datetime import datetime
import json

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

# Add this constant at the top with other constants
SERVICE_ACCOUNT_EMAIL = "google-rr-service-account@perfect-rider-446204-h0.iam.gserviceaccount.com"
AGENT_REPORTS_FOLDER_ID = "1CaIwU3hir-TuLIdPfVMUC6zHcAz4yjhZ"

class GoogleDriveTool(BaseTool):
    """
    Tool for creating and updating Google Sheets in Google Drive.
    Supports creating new sheets, updating existing ones, and managing folder structure.
    All sheets are created in the Agent-Reports folder.
    """
    
    model_config = ConfigDict(arbitrary_types_allowed=True)  # Allow pandas DataFrame
    
    folder_id: str = Field(
        AGENT_REPORTS_FOLDER_ID,
        description="Google Drive folder ID where the sheet will be stored"
    )
    
    title: str = Field(
        ...,
        description="Title of the Google Sheet"
    )
    
    data: Union[List[List[Any]], pd.DataFrame, Dict[str, Any]] = Field(
        ...,
        description="Data to write to the sheet. Can be a list of lists, DataFrame, or dict"
    )
    
    sheet_id: Optional[str] = Field(
        None,
        description="Existing sheet ID if updating (optional)"
    )
    
    sheet_range: str = Field(
        "A1",
        description="Starting cell range for data (e.g., 'A1', 'B2')"
    )

    def run(self) -> dict:
        """Create or update a Google Sheet with the provided data."""
        try:
            # Convert data to standard format (list of lists)
            formatted_data = self._format_data(self.data)
            
            if self.sheet_id:
                # Update existing sheet
                result = self._update_sheet(formatted_data)
                logger.info(f"Updated sheet: {self.sheet_id}")
                return {
                    "status": "updated",
                    "sheet_id": self.sheet_id,
                    "url": f"https://docs.google.com/spreadsheets/d/{self.sheet_id}"
                }
            else:
                # Create new sheet
                result = self._create_sheet(formatted_data)
                logger.info(f"Created new sheet: {result['id']}")
                return {
                    "status": "created",
                    "sheet_id": result['id'],
                    "url": result['webViewLink']
                }
                
        except Exception as e:
            logger.error(f"Error with Google Sheets operation: {str(e)}")
            raise

    def _format_data(self, data: Union[List[List[Any]], pd.DataFrame, Dict[str, Any]]) -> List[List[Any]]:
        """Convert input data to list of lists format."""
        if isinstance(data, pd.DataFrame):
            # Convert DataFrame to list of lists with headers
            headers = data.columns.tolist()
            rows = data.values.tolist()
            return [headers] + rows
            
        elif isinstance(data, dict):
            # Convert dict to list of lists
            if all(isinstance(v, list) for v in data.values()):
                # If dict values are lists of equal length
                headers = list(data.keys())
                rows = list(zip(*data.values()))
                return [headers] + [list(row) for row in rows]
            else:
                # Simple key-value pairs
                return [[k, str(v)] for k, v in data.items()]
                
        elif isinstance(data, list) and all(isinstance(row, list) for row in data):
            return data
            
        else:
            raise ValueError("Data must be a DataFrame, dict, or list of lists")

    def _verify_folder_access(self) -> bool:
        """Verify and request access to the folder if needed."""
        try:
            # Try to get folder metadata
            folder = drive_service.files().get(
                fileId=self.folder_id,
                fields='id, name, permissions'
            ).execute()
            
            # Check if service account has access
            permissions = drive_service.permissions().list(
                fileId=self.folder_id
            ).execute().get('permissions', [])
            
            service_account_has_access = any(
                p.get('emailAddress') == SERVICE_ACCOUNT_EMAIL 
                for p in permissions
            )
            
            if not service_account_has_access:
                logger.warning(f"Service account {SERVICE_ACCOUNT_EMAIL} needs access to folder {self.folder_id}")
                # You could automatically request access here if needed
                
            return service_account_has_access
            
        except Exception as e:
            logger.error(f"Error verifying folder access: {str(e)}")
            return False

    def _find_agent_reports_folder(self) -> str:
        """Find or create the Agent-Reports folder."""
        try:
            # Search for existing folder
            results = drive_service.files().list(
                q="name='Agent-Reports' and mimeType='application/vnd.google-apps.folder' and trashed=false",
                spaces='drive',
                fields='files(id, name)'
            ).execute()
            
            files = results.get('files', [])
            
            if files:
                folder_id = files[0]['id']
                logger.info(f"Found existing Agent-Reports folder: {folder_id}")
                return folder_id
            
            # If folder doesn't exist, create it
            folder_metadata = {
                'name': 'Agent-Reports',
                'mimeType': 'application/vnd.google-apps.folder',  # Correct MIME type for folders
                'parents': []  # Create in root of My Drive
            }
            
            folder = drive_service.files().create(
                body=folder_metadata,
                fields='id, webViewLink',
                supportsAllDrives=True
            ).execute()
            
            folder_id = folder.get('id')
            logger.info(f"Created new Agent-Reports folder: {folder_id}")
            
            # Share with target email
            share_email = os.getenv("GOOGLE_DRIVE_EMAIL")
            if share_email:
                permission = {
                    'type': 'user',
                    'role': 'writer',
                    'emailAddress': share_email,
                    'sendNotificationEmail': False
                }
                drive_service.permissions().create(
                    fileId=folder_id,
                    body=permission,
                    sendNotificationEmails=False
                ).execute()
                logger.info(f"Shared folder with {share_email}")
            
            return folder_id
            
        except Exception as e:
            logger.error(f"Error finding/creating folder: {str(e)}")
            raise

    def _create_sheet(self, data: List[List[Any]]) -> Dict[str, Any]:
        """Create a new Google Sheet in the specified folder and share it."""
        try:
            # Get the email to share with
            share_email = os.getenv("GOOGLE_DRIVE_EMAIL")
            if not share_email:
                raise ValueError("GOOGLE_DRIVE_EMAIL environment variable is not set")

            # Create file metadata with specific folder ID
            file_metadata = {
                'name': self.title,
                'mimeType': 'application/vnd.google-apps.spreadsheet',
                'parents': ['1CaIwU3hir-TuLIdPfVMUC6zHcAz4yjhZ']  # Use specific folder ID
            }
            
            # Create empty sheet
            sheet = drive_service.files().create(
                body=file_metadata,
                fields='id, webViewLink',
                supportsAllDrives=True
            ).execute()
            
            # Share the sheet with specified email
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
            
            logger.info(f"Created sheet and shared with {share_email}")
            
            # Update sheet with data
            self.sheet_id = sheet['id']
            self._update_sheet(data)
            
            return sheet

        except Exception as e:
            logger.error(f"Error creating/sharing sheet: {str(e)}")
            raise

    def _update_sheet(self, data: List[List[Any]]) -> Dict[str, Any]:
        """Update an existing Google Sheet with new data."""
        body = {
            'values': data
        }
        
        result = sheets_service.spreadsheets().values().update(
            spreadsheetId=self.sheet_id,
            range=self.sheet_range,
            valueInputOption='RAW',
            body=body
        ).execute()
        
        return result

    def _get_sheet_metadata(self) -> Dict[str, Any]:
        """Get metadata about the sheet."""
        return sheets_service.spreadsheets().get(
            spreadsheetId=self.sheet_id
        ).execute()


if __name__ == "__main__":
    # Test the tool
    try:
        # Test data
        test_data = {
            "Product": ["MacBook Pro", "iPhone", "iPad"],
            "Stock": [5, 20, 0],
            "Status": ["Low Stock", "In Stock", "Out of Stock"]
        }
        
        # Create new sheet
        drive_tool = GoogleDriveTool(
            title="Inventory Report",
            data=test_data,
            sheet_range="A1"
        )
        
        result = drive_tool.run()
        print("\nTest Results:")
        print(f"Status: {result['status']}")
        print(f"Sheet URL: {result['url']}")
        
        # Update the same sheet with new data
        if result['sheet_id']:
            update_data = {
                "Product": ["MacBook Pro", "iPhone", "iPad"],
                "Stock": [10, 15, 5],  # Updated stock numbers
                "Status": ["In Stock", "In Stock", "Low Stock"]
            }
            
            update_tool = GoogleDriveTool(
                title="Inventory Report",
                data=update_data,
                sheet_id=result['sheet_id'],
                sheet_range="A1"
            )
            
            update_result = update_tool.run()
            print("\nUpdate Results:")
            print(f"Status: {update_result['status']}")
            print(f"Updated Sheet URL: {update_result['url']}")
            
    except Exception as e:
        print(f"Error in test: {str(e)}") 