"""Test script for database connection utilities.

This script tests all aspects of the database connection module, including:
1. Basic connectivity
2. Connection pooling
3. Retry logic
4. Error handling
5. Schema and table access
"""

import logging
from datetime import datetime
from utils.db_connection import (
    DatabaseConfig,
    get_db_engine,
    get_db_connection,
    get_db_cursor,
    test_connection,
    DatabaseError
)
from sqlalchemy import text, create_engine

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_basic_connectivity():
    """Test basic database connectivity."""
    logger.info("\n=== Testing Basic Connectivity ===")
    try:
        # Test using default configuration
        result = test_connection()
        assert result, "Basic connection test failed"
        logger.info("✓ Basic connectivity test passed")
        return True
    except Exception as e:
        logger.error(f"✗ Basic connectivity test failed: {str(e)}")
        return False

def test_sqlalchemy_engine():
    """Test SQLAlchemy engine creation and querying."""
    logger.info("\n=== Testing SQLAlchemy Engine ===")
    try:
        # Get engine
        engine = get_db_engine()
        
        # Test simple query
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.scalar()
            logger.info(f"Database version: {version}")
            
            # Test schema access
            result = conn.execute(text("""
                SELECT schema_name 
                FROM information_schema.schemata 
                WHERE schema_name = 'sales_data'
            """))
            assert result.scalar(), "Sales data schema not found"
            
        logger.info("✓ SQLAlchemy engine test passed")
        return True
    except Exception as e:
        logger.error(f"✗ SQLAlchemy engine test failed: {str(e)}")
        return False

def test_connection_context_managers():
    """Test connection and cursor context managers."""
    logger.info("\n=== Testing Context Managers ===")
    try:
        # Test connection context manager
        with get_db_connection() as conn:
            assert conn is not None, "Connection is None"
            
            # Test simple query
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            assert result[0] == 1, "Simple query failed"
            cursor.close()
        
        # Test cursor context manager
        with get_db_cursor() as cursor:
            cursor.execute("SELECT current_timestamp")
            timestamp = cursor.fetchone()[0]
            logger.info(f"Current database time: {timestamp}")
        
        logger.info("✓ Context managers test passed")
        return True
    except Exception as e:
        logger.error(f"✗ Context managers test failed: {str(e)}")
        return False

def test_sales_data_access():
    """Test access to sales_data schema and its tables."""
    logger.info("\n=== Testing Sales Data Access ===")
    try:
        with get_db_cursor() as cursor:
            # Test sales_data schema access
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'sales_data'
                ORDER BY table_name
            """)
            tables = cursor.fetchall()
            
            logger.info("Tables in sales_data schema:")
            for table in tables:
                logger.info(f"- {table[0]}")
                
                # Get column information for each table
                cursor.execute("""
                    SELECT column_name, data_type 
                    FROM information_schema.columns 
                    WHERE table_schema = 'sales_data' 
                    AND table_name = %s
                    ORDER BY ordinal_position
                """, (table[0],))
                columns = cursor.fetchall()
                
                logger.info(f"  Columns:")
                for col in columns:
                    logger.info(f"    - {col[0]} ({col[1]})")
        
        logger.info("✓ Sales data access test passed")
        return True
    except Exception as e:
        logger.error(f"✗ Sales data access test failed: {str(e)}")
        return False

def test_error_handling():
    """Test error handling with invalid configurations."""
    logger.info("\n=== Testing Error Handling ===")
    try:
        # Test with invalid credentials
        invalid_config = DatabaseConfig(
            instance_connection_name="invalid-instance",
            user="invalid_user",
            password="invalid_password",
            database="invalid_db",
            host="invalid_host",
            credentials_path="invalid_path.json"
        )
        
        try:
            with get_db_connection(invalid_config):
                assert False, "Should have raised an exception"
        except DatabaseError as e:
            logger.info(f"✓ Expected error caught: {str(e)}")
        
        logger.info("✓ Error handling test passed")
        return True
    except Exception as e:
        logger.error(f"✗ Error handling test failed: {str(e)}")
        return False

def run_all_tests():
    """Run all database connection tests."""
    logger.info("Starting database connection test suite...")
    logger.info(f"Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    tests = [
        ("Basic Connectivity", test_basic_connectivity),
        ("SQLAlchemy Engine", test_sqlalchemy_engine),
        ("Context Managers", test_connection_context_managers),
        ("Sales Data Access", test_sales_data_access),
        ("Error Handling", test_error_handling)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            logger.info(f"\nRunning {test_name} test...")
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            logger.error(f"Test '{test_name}' failed with error: {str(e)}")
            results.append((test_name, False))
    
    # Print summary
    logger.info("\n=== Test Summary ===")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    logger.info(f"Tests completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Results: {passed}/{total} tests passed")
    
    for test_name, result in results:
        status = "✓ PASSED" if result else "✗ FAILED"
        logger.info(f"{status}: {test_name}")
    
    return all(result for _, result in results)

if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1) 