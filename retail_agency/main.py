import os
import logging
from pathlib import Path
from dotenv import load_dotenv
from utils.slack_handler import SlackEventHandler

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    # Load environment variables
    load_dotenv(Path(__file__).parent / ".env")
    
    # Required environment variables
    required_env_vars = [
        "SLACK_BOT_TOKEN",
        "SLACK_APP_TOKEN",
        "OPENAI_API_KEY"
    ]
    
    # Check for required environment variables
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
    
    try:
        # Initialize and start Slack handler
        handler = SlackEventHandler()
        logger.info("Starting Slack bot...")
        handler.start()
        
    except Exception as e:
        logger.error(f"Failed to start application: {str(e)}", exc_info=True)
        raise

if __name__ == "__main__":
    main() 