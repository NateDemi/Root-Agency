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
client = openai.OpenAI(
    api_key=os.environ["OPENAI_API_KEY"],
    max_retries=10,
    default_headers={"OpenAI-Beta": "assistants=v2"}
)
set_openai_client(client)

# Initialize agents
ceo = CEO()
reporting_manager = ReportingManager()

# Create agency
agency = Agency(
    [
        ceo,  # CEO is the entry point
        [ceo, reporting_manager],  # CEO can communicate with Reporting Manager
    ],
    shared_instructions='./agency_manifesto.md'
)

if __name__ == "__main__":
    agency.run_demo() 