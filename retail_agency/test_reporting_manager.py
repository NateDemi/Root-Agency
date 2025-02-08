from reporting_manager.reporting_manager import ReportingManager
from reporting_manager.tools.SQLQueryTool import SQLQueryTool
from reporting_manager.tools.DataAnalyzer import DataAnalyzer
from reporting_manager.tools.ReportGenerator import ReportGenerator
from dotenv import load_dotenv
import pandas as pd
import logging
from datetime import datetime, timedelta
import numpy as np

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def test_sql_queries():
    """Test SQL querying capabilities."""
    print("\n=== Testing SQL Queries ===")
    
    # Test basic sales query
    print("\nTesting basic sales query...")
    sql_tool = SQLQueryTool(
        query="Show me total sales by product for today, including quantity sold and total revenue"
    )
    print(sql_tool.run())
    
    # Test customer segmentation query
    print("\nTesting customer segmentation query...")
    sql_tool = SQLQueryTool(
        query="Show me customer segments based on total purchase amount, " +
              "categorizing them as 'High Value' (>$1000), 'Medium Value' ($500-$1000), " +
              "and 'Low Value' (<$500)"
    )
    print(sql_tool.run())
    
    # Test inventory analysis query
    print("\nTesting inventory analysis query...")
    sql_tool = SQLQueryTool(
        query="Show me products with low inventory (less than 20 units) " +
              "and their sales velocity over the last 30 days"
    )
    print(sql_tool.run())

def test_data_analysis():
    """Test data analysis capabilities."""
    print("\n=== Testing Data Analysis ===")
    
    # Create sample data
    dates = pd.date_range(start='2024-01-01', end='2024-03-31', freq='D')
    np.random.seed(42)
    
    # Generate sample sales data
    sales = np.random.normal(1000, 100, len(dates))
    sales = sales + np.sin(np.arange(len(dates)) * 2 * np.pi / 7) * 100  # Weekly seasonality
    sales = sales + np.sin(np.arange(len(dates)) * 2 * np.pi / 30) * 200  # Monthly seasonality
    sales = sales + np.arange(len(dates)) * 0.5  # Upward trend
    
    test_data = pd.DataFrame({
        'date': dates,
        'sales': sales,
        'customers': np.random.normal(500, 50, len(dates)),
        'items_per_order': np.random.normal(3, 0.5, len(dates)),
        'average_price': np.random.normal(50, 5, len(dates))
    })
    
    # Test trend analysis
    print("\nTesting trend analysis...")
    analyzer = DataAnalyzer(
        data=test_data,
        analysis_type="trend",
        time_column="date",
        target_column="sales"
    )
    print(analyzer.run())
    
    # Test forecasting
    print("\nTesting forecasting...")
    analyzer = DataAnalyzer(
        data=test_data,
        analysis_type="forecast",
        time_column="date",
        target_column="sales",
        params={'forecast_periods': 30, 'seasonal_periods': 7}
    )
    print(analyzer.run())

def test_report_generation():
    """Test report generation capabilities."""
    print("\n=== Testing Report Generation ===")
    
    # Prepare sample data for report
    test_data = {
        "total_sales": {
            "value": 150000,
            "trend": "increasing",
            "highlight": "15% increase from previous quarter"
        },
        "average_order": {
            "value": 75.50,
            "trend": "stable",
            "highlight": "Consistent with last quarter"
        },
        "customer_satisfaction": {
            "value": 4.2,
            "trend": "improving",
            "recommendation": "Focus on maintaining high service levels"
        },
        "top_products": [
            "Product A - 1200 units",
            "Product B - 950 units",
            "Product C - 875 units"
        ],
        "key_insights": [
            "Customer retention rate improved by 5%",
            "New product line contributing 15% of revenue",
            "Online sales growing faster than in-store"
        ]
    }
    
    # Generate executive summary
    print("\nGenerating executive summary...")
    generator = ReportGenerator(
        report_type="executive_summary",
        title="Q1 2024 Retail Performance Report",
        data=test_data,
        tags=["quarterly", "performance", "executive"]
    )
    print(generator.run())

def test_end_to_end():
    """Test end-to-end workflow with ReportingManager."""
    print("\n=== Testing End-to-End Workflow ===")
    
    # Initialize ReportingManager
    manager = ReportingManager()
    
    # Test queries and analysis
    queries = [
        "Show me our top 5 selling products for Q1 2024",
        "What is our current inventory status for these top products?",
        "Can you analyze the sales trends for these products and forecast next month's sales?",
        "Generate a comprehensive report with these insights and save it to Notion"
    ]
    
    for query in queries:
        print(f"\nProcessing query: {query}")
        response = manager.handle_message(query)
        print(f"Response: {response}")

if __name__ == "__main__":
    print("Starting ReportingManager Tests...")
    
    try:
        # Run individual component tests
        test_sql_queries()
        test_data_analysis()
        test_report_generation()
        
        # Run end-to-end test
        test_end_to_end()
        
        print("\nAll tests completed successfully!")
        
    except Exception as e:
        logger.error(f"Error during testing: {str(e)}", exc_info=True)
        print(f"\nError during testing: {str(e)}") 