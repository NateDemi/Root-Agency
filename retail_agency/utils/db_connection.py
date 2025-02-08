"""Database connection utilities for Cloud SQL PostgreSQL database.

This module provides utilities for connecting to a Cloud SQL PostgreSQL database
using either the Cloud SQL Python Connector or direct connection via pg8000.
It includes connection pooling, retry logic, and comprehensive error handling.
"""

import os
import logging
import time
from contextlib import contextmanager
from typing import Any, Generator, Optional, Dict, Callable
from dataclasses import dataclass

import pg8000
from google.cloud.sql.connector import Connector, IPTypes
from google.oauth2 import service_account
from sqlalchemy import create_engine, URL, Engine, text
from sqlalchemy.pool import QueuePool
from tenacity import retry, stop_after_attempt, wait_exponential

# Configure logging
logger = logging.getLogger(__name__)

# Database Configuration Constants
DB_CONFIG = {
    "INSTANCE_CONNECTION_NAME": "perfect-rider-446204-h0:us-central1:prod-7rivermart",
    "DB_USER": "postgres",
    "DB_PASS": "Jz7c[[AMBi9j5yS)",
    "DB_NAME": "postgres",
    "DB_HOST": "34.57.51.199",
    "CREDENTIALS_PATH": "credentials.json",
    "MAX_CONNECTIONS": 10,
    "POOL_TIMEOUT": 30,
    "RETRY_ATTEMPTS": 3,
    "RETRY_MIN_WAIT": 1,  # seconds
    "RETRY_MAX_WAIT": 10  # seconds
}

@dataclass
class DatabaseConfig:
    """Database configuration container."""
    instance_connection_name: str
    user: str
    password: str
    database: str
    host: str
    credentials_path: str
    max_connections: int = 10
    pool_timeout: int = 30

    @classmethod
    def from_env(cls) -> 'DatabaseConfig':
        """Create configuration from environment variables."""
        return cls(
            instance_connection_name=os.getenv('DB_INSTANCE_CONNECTION_NAME', DB_CONFIG['INSTANCE_CONNECTION_NAME']),
            user=os.getenv('DB_USER', DB_CONFIG['DB_USER']),
            password=os.getenv('DB_PASS', DB_CONFIG['DB_PASS']),
            database=os.getenv('DB_NAME', DB_CONFIG['DB_NAME']),
            host=os.getenv('DB_HOST', DB_CONFIG['DB_HOST']),
            credentials_path=os.getenv('DB_CREDENTIALS_PATH', DB_CONFIG['CREDENTIALS_PATH']),
            max_connections=int(os.getenv('DB_MAX_CONNECTIONS', DB_CONFIG['MAX_CONNECTIONS'])),
            pool_timeout=int(os.getenv('DB_POOL_TIMEOUT', DB_CONFIG['POOL_TIMEOUT']))
        )

class DatabaseError(Exception):
    """Base class for database-related exceptions."""
    pass

class CredentialsError(DatabaseError):
    """Raised when there are issues with database credentials."""
    pass

class ConnectionError(DatabaseError):
    """Raised when database connection fails."""
    pass

def get_credentials(credentials_path: str) -> service_account.Credentials:
    """
    Load service account credentials from file.
    
    Args:
        credentials_path: Path to the service account credentials JSON file.
        
    Returns:
        service_account.Credentials: The loaded credentials.
        
    Raises:
        CredentialsError: If credentials cannot be loaded.
    """
    try:
        if not os.path.exists(credentials_path):
            raise FileNotFoundError(f"Credentials file not found at {credentials_path}")
        
        return service_account.Credentials.from_service_account_file(
            credentials_path,
            scopes=["https://www.googleapis.com/auth/sqlservice.admin"]
        )
    except Exception as e:
        raise CredentialsError(f"Failed to load credentials: {str(e)}") from e

@retry(
    stop=stop_after_attempt(DB_CONFIG['RETRY_ATTEMPTS']),
    wait=wait_exponential(
        multiplier=DB_CONFIG['RETRY_MIN_WAIT'],
        max=DB_CONFIG['RETRY_MAX_WAIT']
    ),
    reraise=True
)
def create_connector_connection(config: DatabaseConfig) -> Any:
    """
    Create a database connection using Cloud SQL Connector.
    
    Args:
        config: Database configuration object.
        
    Returns:
        Connection object.
        
    Raises:
        ConnectionError: If connection cannot be established.
    """
    try:
        credentials = get_credentials(config.credentials_path)
        connector = Connector(credentials=credentials)
        
        return connector.connect(
            instance_connection_string=config.instance_connection_name,
            driver="pg8000",
            db=config.database,
            user=config.user,
            password=config.password,
            enable_iam_auth=False
        )
    except Exception as e:
        raise ConnectionError(f"Failed to create connector connection: {str(e)}") from e

@retry(
    stop=stop_after_attempt(DB_CONFIG['RETRY_ATTEMPTS']),
    wait=wait_exponential(
        multiplier=DB_CONFIG['RETRY_MIN_WAIT'],
        max=DB_CONFIG['RETRY_MAX_WAIT']
    ),
    reraise=True
)
def create_direct_connection(config: DatabaseConfig) -> Any:
    """
    Create a direct database connection using pg8000.
    
    Args:
        config: Database configuration object.
        
    Returns:
        Connection object.
        
    Raises:
        ConnectionError: If connection cannot be established.
    """
    try:
        return pg8000.connect(
            database=config.database,
            user=config.user,
            password=config.password,
            host=config.host
        )
    except Exception as e:
        raise ConnectionError(f"Failed to create direct connection: {str(e)}") from e

def get_connection_factory(config: DatabaseConfig) -> Callable[[], Any]:
    """
    Create a connection factory function.
    
    Args:
        config: Database configuration object.
        
    Returns:
        Callable that creates database connections.
    """
    def get_conn() -> Any:
        try:
            return create_connector_connection(config)
        except Exception as e:
            logger.warning(f"Cloud SQL Connector connection failed: {str(e)}")
            logger.info("Falling back to direct connection...")
            return create_direct_connection(config)
    
    return get_conn

def get_db_engine(config: Optional[DatabaseConfig] = None) -> Engine:
    """
    Create and configure a SQLAlchemy engine with connection pooling.
    
    Args:
        config: Optional database configuration object. If not provided,
               configuration will be loaded from environment.
               
    Returns:
        SQLAlchemy Engine instance.
        
    Raises:
        DatabaseError: If engine creation fails.
    """
    try:
        if config is None:
            config = DatabaseConfig.from_env()
        
        # Create the connection factory
        creator = get_connection_factory(config)
        
        # Create SQLAlchemy engine with connection pooling
        engine = create_engine(
            "postgresql+pg8000://",
            creator=creator,
            poolclass=QueuePool,
            pool_size=config.max_connections,
            max_overflow=2,
            pool_timeout=config.pool_timeout,
            pool_pre_ping=True
        )
        
        # Test the connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        
        logger.info("SQLAlchemy engine created successfully")
        return engine
        
    except Exception as e:
        raise DatabaseError(f"Failed to create database engine: {str(e)}") from e

@contextmanager
def get_db_connection(config: Optional[DatabaseConfig] = None) -> Generator[Any, None, None]:
    """
    Context manager for database connections.
    
    Args:
        config: Optional database configuration object.
        
    Yields:
        Database connection object.
    """
    if config is None:
        config = DatabaseConfig.from_env()
    
    conn = None
    try:
        creator = get_connection_factory(config)
        conn = creator()
        yield conn
    finally:
        if conn:
            try:
                conn.close()
            except Exception as e:
                logger.warning(f"Error closing connection: {str(e)}")

@contextmanager
def get_db_cursor(config: Optional[DatabaseConfig] = None) -> Generator[Any, None, None]:
    """
    Context manager for database cursors.
    
    Args:
        config: Optional database configuration object.
        
    Yields:
        Database cursor object.
    """
    with get_db_connection(config) as conn:
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        finally:
            cursor.close()

def test_connection(config: Optional[DatabaseConfig] = None) -> bool:
    """
    Test database connection and schema access.
    
    Args:
        config: Optional database configuration object.
        
    Returns:
        bool: True if connection test passes, False otherwise.
    """
    try:
        with get_db_cursor(config) as cursor:
            # Test schema query
            cursor.execute("""
                SELECT schema_name 
                FROM information_schema.schemata 
                WHERE schema_name NOT IN ('information_schema', 'pg_catalog')
            """)
            schemas = cursor.fetchall()
            
            logger.info("Available schemas:")
            for schema in schemas:
                logger.info(f"- {schema[0]}")
                
                # Test table access in each schema
                cursor.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = %s
                """, (schema[0],))
                tables = cursor.fetchall()
                
                if tables:
                    logger.info(f"\nTables in {schema[0]} schema:")
                    for table in tables:
                        logger.info(f"- {schema[0]}.{table[0]}")
            
            logger.info("Connection test successful!")
            return True
            
    except Exception as e:
        logger.error(f"Connection test failed: {str(e)}")
        return False

if __name__ == "__main__":
    # Set up logging for the test
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger.info("Starting database connection tests...")
    try:
        # Test the connection
        if test_connection():
            logger.info("All database connection tests passed!")
        else:
            logger.error("Database connection tests failed!")
    except Exception as e:
        logger.error(f"Error during testing: {str(e)}", exc_info=True) 