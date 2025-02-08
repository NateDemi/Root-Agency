from ceo.tools.NotionPoster import NotionPoster
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_notion_integration():
    """Test the Notion integration by creating a simple test page."""
    print("Testing Notion integration...")
    
    # Create a test page
    poster = NotionPoster(
        title="Test Page",
        content="This is a test page created at " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        tags=["test"]
    )
    
    # Try to post to Notion
    result = poster.run()
    print("\nResult:", result)

if __name__ == "__main__":
    from datetime import datetime
    test_notion_integration() 