import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from retail_agency.reporting_manager.reporting_manager import ReportingManager
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_reporting_manager():
    try:
        # Initialize ReportingManager
        manager = ReportingManager()
        logger.info("ReportingManager initialized")

        # Test queries
        test_queries = [
            "get all items with 0 stock",
            "show items with negative inventory",
            "what are our top 10 items by stock count"
        ]

        for query in test_queries:
            logger.info("=" * 80)
            logger.info(f"Testing query: {query}")
            logger.info("=" * 80)

            # Process query
            result = manager.handle_message(query)
            
            # Log result structure
            logger.info("Result Structure:")
            logger.info(f"Keys: {list(result.keys())}")
            
            if 'error' in result:
                logger.error(f"Error in response: {result['error']}")
                continue

            # Log response details
            logger.info(f"Total rows: {result.get('total_rows', 0)}")
            logger.info("Natural Response:")
            logger.info("-" * 40)
            logger.info(result.get('natural_response', 'No response'))
            logger.info("-" * 40)

            # Log sample data
            if result.get('sample_data'):
                logger.info("Sample Data (first 3 rows):")
                for idx, item in enumerate(result['sample_data'][:3], 1):
                    logger.info(f"Row {idx}: {item}")

            # Log file paths
            if 'files' in result:
                logger.info("Generated Files:")
                for file_type, path in result['files'].items():
                    if path:
                        logger.info(f"{file_type.upper()}: {path}")

            logger.info("\n")

    except Exception as e:
        logger.error(f"Error in test execution: {str(e)}", exc_info=True)

if __name__ == "__main__":
    test_reporting_manager() 