import logging
import os
from dotenv import load_dotenv
from reporting_manager.reporting_manager import ReportingManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='retail_agency_bot.log'
)

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def test_basic_queries():
    """Test basic database queries using the ReportingManager."""
    try:
        agent = ReportingManager()
        
        # Test schema listing
        response = agent.handle_message("List all available schemas in the database.")
        logger.info("Schema listing test response: %s", response)
        
        # Test table listing
        response = agent.handle_message("Show me all tables in the sales_data schema.")
        logger.info("Table listing test response: %s", response)
        
        return True
    except Exception as e:
        logger.error("Error in basic queries test: %s", str(e), exc_info=True)
        return False

def test_sales_analysis():
    """Test sales analysis queries."""
    try:
        agent = ReportingManager()
        
        # Test daily sales query
        response = agent.handle_message(
            "What are our total sales for today, broken down by product category?"
        )
        logger.info("Daily sales test response: %s", response)
        
        # Test monthly trends
        response = agent.handle_message(
            "Show me the sales trend for the past 30 days, including daily total revenue and order count."
        )
        logger.info("Monthly trends test response: %s", response)
        
        return True
    except Exception as e:
        logger.error("Error in sales analysis test: %s", str(e), exc_info=True)
        return False

def test_inventory_analysis():
    """Test inventory analysis queries."""
    try:
        agent = ReportingManager()
        
        # Test low stock items
        response = agent.handle_message(
            "Show me all inventory items with stock levels below 20 units."
        )
        logger.info("Low stock test response: %s", response)
        
        # Test inventory valuation
        response = agent.handle_message(
            "Calculate the total value of our current inventory, grouped by category."
        )
        logger.info("Inventory valuation test response: %s", response)
        
        return True
    except Exception as e:
        logger.error("Error in inventory analysis test: %s", str(e), exc_info=True)
        return False

def test_complex_analysis():
    """Test complex analytical queries."""
    try:
        agent = ReportingManager()
        
        # Test vendor performance analysis
        response = agent.handle_message("""
            Analyze vendor performance for the past 90 days:
            - Total purchase value by vendor
            - Average delivery time
            - Return rate
            - Order fulfillment rate
            Sort by total purchase value descending.
        """)
        logger.info("Vendor performance test response: %s", response)
        
        # Test customer behavior analysis
        response = agent.handle_message("""
            Analyze customer purchase patterns:
            - Average order value
            - Most common product combinations
            - Peak shopping hours
            - Customer retention rate
            For orders in the past 60 days.
        """)
        logger.info("Customer behavior test response: %s", response)
        
        return True
    except Exception as e:
        logger.error("Error in complex analysis test: %s", str(e), exc_info=True)
        return False

if __name__ == "__main__":
    logger.info("Starting ReportingManager tests...")
    
    # Run all tests
    tests = [
        ("Basic Queries", test_basic_queries),
        ("Sales Analysis", test_sales_analysis),
        ("Inventory Analysis", test_inventory_analysis),
        ("Complex Analysis", test_complex_analysis)
    ]
    
    all_passed = True
    for test_name, test_func in tests:
        logger.info("Running %s test...", test_name)
        try:
            result = test_func()
            status = "PASSED" if result else "FAILED"
            logger.info("%s test %s", test_name, status)
            if not result:
                all_passed = False
        except Exception as e:
            logger.error("%s test FAILED with error: %s", test_name, str(e), exc_info=True)
            all_passed = False
    
    final_status = "All tests PASSED" if all_passed else "Some tests FAILED"
    logger.info("Test suite completed. %s", final_status)
    print(final_status) 