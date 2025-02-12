import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from .tools.SQLQueryTool import SQLQueryTool
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_sql_query():
    try:
        # Initialize the tool
        tool = SQLQueryTool(
            query="get all items with 0 stock",
            save_path="zero_inventory_items"
        )
        
        # Execute query
        result = tool.run()
        
        # Log the result structure
        logger.info("Query Result Structure:")
        logger.info(f"Result type: {type(result)}")
        logger.info(f"Result keys: {result.keys() if isinstance(result, dict) else 'Not a dict'}")
        
        if isinstance(result, dict):
            if 'data' in result:
                logger.info(f"Data structure: {result['data'].keys() if isinstance(result['data'], dict) else 'Not a dict'}")
                logger.info(f"Row count: {result.get('row_count', 'Not available')}")
                logger.info(f"First few rows: {result['data'].get('rows', [])[:3] if isinstance(result['data'], dict) else 'No rows'}")
            
            if 'error' in result:
                logger.error(f"Error in result: {result['error']}")

        return result
        
    except Exception as e:
        logger.error(f"Error in test_sql_query: {str(e)}")
        return {"type": "error", "error": str(e)}

if __name__ == "__main__":
    result = test_sql_query()
    print("\nTest Results:")
    print("=" * 50)
    print(f"Success: {'error' not in result if isinstance(result, dict) else False}")
    if isinstance(result, dict) and 'data' in result:
        print(f"Total rows: {result.get('row_count', 0)}")
        print("\nSample Data:")
        if isinstance(result['data'], dict) and 'rows' in result['data']:
            for row in result['data']['rows'][:3]:
                print(row) 