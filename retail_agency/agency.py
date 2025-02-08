import os
import logging
from datetime import datetime
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from agency_swarm import Agency
from ceo.ceo import CEO
from reporting_manager.reporting_manager import ReportingManager
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger(__name__)

def create_agency():
    """Create and return a new instance of the Agency."""
    logging.info("Creating new agency instance...")
    
    # Initialize agents
    ceo = CEO()
    reporting_manager = ReportingManager()
    
    # Create agency with communication flows
    agency = Agency(
        agency_chart=[
            ceo,  # CEO is the entry point
            [ceo, reporting_manager],  # CEO can communicate with Reporting Manager
        ],
        shared_instructions="""# Retail Management Agency

## Communication Protocol

1. **CEO Role**
   - Primary point of contact for all requests
   - Analyzes and delegates data-related requests to ReportingManager
   - Creates Notion reports for complex data analysis
   - Provides clear summaries and insights

2. **ReportingManager Role**
   - Handles all data analysis and reporting
   - Executes SQL queries and analyzes results
   - Returns structured data with insights
   - Supports CEO in data interpretation

3. **Data Request Flow**
   - CEO receives and analyzes request
   - If data-related, CEO delegates to ReportingManager
   - ReportingManager processes and returns results
   - CEO formats and presents results:
     * Small datasets: Direct response
     * Large/complex data: Notion report
     * Always includes key insights

4. **Quality Standards**
   - Clear communication
   - Accurate data analysis
   - Proper data formatting
   - Comprehensive insights
   - Professional presentation""",
        temperature=0.5,
        max_prompt_tokens=25000
    )
    
    logging.info("Agency created successfully")
    return agency

def main():
    """Initialize and start the agency in interactive mode."""
    agency = create_agency()
    agency.run_demo()

if __name__ == "__main__":
    main() 