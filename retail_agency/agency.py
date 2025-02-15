import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from pathlib import Path
from agency_swarm import Agency, set_openai_key, set_openai_client
from ceo.ceo import CEO
from retail_agency.reporting_manager.reporting_manager import ReportingManager
import openai

# Load environment variables
load_dotenv(Path(__file__).parent / ".env")

# Configure OpenAI
set_openai_key(os.environ["OPENAI_API_KEY"])

# Initialize OpenAI client with project API key configuration

# Initialize agents
ceo = CEO()
reporting_manager = ReportingManager()

# Create agency with proper communication flows
agency = Agency(
    [
        reporting_manager,  # ReportingManager is the entry point for user communication
    ],
    shared_instructions='./agency_manifesto.md'
)

if __name__ == "__main__":
    # Run the agency demo using the framework's built-in functionality
    agency.run_demo() 