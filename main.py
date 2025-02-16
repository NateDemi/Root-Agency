from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, Dict, Any
import os
from dotenv import load_dotenv
from retail_agency.reporting_manager.tools.NotionPosterTool import NotionPosterTool
from retail_agency.reporting_manager.tools.utils.gcs_storage import GCSStorage
from google.cloud import secretmanager
import firebase_admin
from firebase_admin import credentials
from sqlalchemy import create_engine
import google.auth
import google.auth.transport.requests
import json

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(title="Retail Assistant API")

# Get project ID from Google Cloud metadata
_, PROJECT_ID = google.auth.default()

def get_secret(secret_id: str) -> str:
    """Retrieve secret from Secret Manager."""
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{PROJECT_ID}/secrets/{secret_id}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")

def initialize_firebase():
    """Initialize Firebase with default credentials."""
    try:
        # Use default credentials for Firebase
        cred = credentials.ApplicationDefault()
        firebase_admin.initialize_app(cred, {
            'projectId': PROJECT_ID,
        })
    except Exception as e:
        print(f"Error initializing Firebase: {str(e)}")
        raise

def get_cloud_sql_connection():
    """Create SQLAlchemy engine for Cloud SQL with native authentication."""
    try:
        # Get Cloud SQL connection details from environment or metadata
        db_user = get_secret("CLOUD_DB_USER")
        db_pass = get_secret("CLOUD_DB_PASS")
        db_name = get_secret("CLOUD_DB_NAME")
        instance_connection_name = f"{PROJECT_ID}:{os.getenv('CLOUD_DB_REGION', 'us-central1')}:{os.getenv('CLOUD_DB_INSTANCE')}"
        
        # Create database URI for Cloud SQL
        db_uri = f"postgresql+pg8000://{db_user}:{db_pass}@/{db_name}?unix_sock=/cloudsql/{instance_connection_name}/.s.PGSQL.5432"
        
        # Create SQLAlchemy engine
        return create_engine(db_uri, pool_size=5, max_overflow=2)
    except Exception as e:
        print(f"Error creating Cloud SQL connection: {str(e)}")
        raise

# Initialize services at startup
@app.on_event("startup")
async def startup_event():
    """Initialize all required services on startup."""
    try:
        # Initialize Firebase
        initialize_firebase()
        
        # Initialize Cloud SQL connection
        app.state.db_engine = get_cloud_sql_connection()
        
        # Initialize GCS with default credentials
        app.state.gcs = GCSStorage()
        
        print("Successfully initialized all services")
    except Exception as e:
        print(f"Error during startup: {str(e)}")
        raise

class InventoryRequest(BaseModel):
    title: str
    gcs_uri: Optional[str] = None
    data_format: str = "auto"
    query: Optional[str] = None
    analysis: Optional[str] = None

class SlackChallenge(BaseModel):
    type: str
    token: str
    challenge: Optional[str] = None

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "healthy", "message": "Retail Assistant API is running"}

@app.post("/inventory/report")
async def create_inventory_report(request: InventoryRequest) -> Dict[str, Any]:
    """
    Create an inventory report in Notion
    """
    try:
        # Get Notion credentials from Secret Manager
        notion_token = get_secret("NOTION_API_KEY")
        notion_db_id = get_secret("NOTION_INVENTORY_DB_ID")
        
        # Initialize NotionPosterTool with request parameters
        notion_tool = NotionPosterTool(
            title=request.title,
            gcs_uri=request.gcs_uri,
            data_format=request.data_format,
            query=request.query,
            analysis=request.analysis,
            database_id=notion_db_id,
            headers={
                "Authorization": f"Bearer {notion_token}",
                "Content-Type": "application/json",
                "Notion-Version": "2022-06-28"
            }
        )
        
        # Run the tool and get results
        result = notion_tool.run()
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
            
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/inventory/health")
async def check_connections():
    """
    Check connections to required services (GCS, Firebase, Cloud SQL, Notion)
    """
    try:
        # Check GCS connection
        gcs_status = "connected" if app.state.gcs.client else "error"
        
        # Check Cloud SQL connection
        try:
            with app.state.db_engine.connect() as conn:
                conn.execute("SELECT 1")
            db_status = "connected"
        except Exception as e:
            db_status = f"error: {str(e)}"
        
        # Check Firebase connection
        firebase_status = "connected" if firebase_admin._apps else "error"
        
        # Check Notion credentials
        try:
            notion_token = get_secret("NOTION_API_KEY")
            notion_db_id = get_secret("NOTION_INVENTORY_DB_ID")
            notion_status = "configured" if notion_token and notion_db_id else "missing credentials"
        except Exception as e:
            notion_status = f"error: {str(e)}"
        
        return {
            "gcs_status": gcs_status,
            "cloud_sql_status": db_status,
            "firebase_status": firebase_status,
            "notion_status": notion_status
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/slack/events")
async def slack_events(request: Request):
    """Handle Slack events and challenges."""
    try:
        # Get the raw request body as string
        body_str = (await request.body()).decode('utf-8')
        print(f"Raw request body: {body_str}")
        
        # Parse the JSON
        payload = json.loads(body_str)
        print(f"Parsed payload: {json.dumps(payload, indent=2)}")
        
        # Handle URL verification challenge
        if payload.get("type") == "url_verification":
            challenge = payload.get("challenge")
            print(f"Challenge received: {challenge}")
            
            # Construct the exact response Slack expects
            response = {"challenge": challenge}
            print(f"Sending response: {json.dumps(response, indent=2)}")
            return response
            
        # Handle other Slack events
        if "event" in payload:
            event = payload.get("event", {})
            event_type = event.get("type")
            print(f"Received event type: {event_type}")
            
            if event_type in ["app_mention", "message"]:
                # Process the message event
                # Your existing message handling logic here
                pass
                
        return {"ok": True}
        
    except Exception as e:
        error_msg = f"Error handling Slack event: {str(e)}"
        print(error_msg)
        print(f"Exception details: {type(e).__name__}")
        return {"ok": False, "error": error_msg} 