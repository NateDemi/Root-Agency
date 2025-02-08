from langchain_community.utilities import SQLDatabase
from langchain_openai import ChatOpenAI
from langchain_community.agent_toolkits.sql.base import create_sql_agent
from langchain_community.agent_toolkits.sql.toolkit import SQLDatabaseToolkit
from agency_swarm.tools import BaseTool
from pydantic import Field
import os
from dotenv import load_dotenv
import logging
from utils.db_connection import get_db_engine

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SQLQueryTool(BaseTool):
    """
    A tool for executing SQL queries against a database and returning the results.
    This tool uses LangChain's SQL agent to generate and execute SQL queries based on natural language input.
    """
    
    query: str = Field(
        ...,
        description="The natural language query to be converted into SQL and executed"
    )
    
    db_type: str = Field(
        default="postgresql",
        description="The type of database to connect to (e.g., postgresql, mysql)"
    )
    
    def __init__(self, **data):
        super().__init__(**data)
        self.sql_agent = None
        
    def _initialize_sql_agent(self):
        """Initialize the SQL agent with the database connection."""
        try:
            # Create OpenAI LLM instance
            llm = ChatOpenAI(
                temperature=0,
                model="gpt-4"
            )
            
            # Get database engine
            engine = get_db_engine()
            
            # Create SQLDatabase instance
            db = SQLDatabase(
                engine=engine,
                schema="sales_data",
                sample_rows_in_table_info=3,
                include_tables=None  # Allow all tables in the schema
            )
            
            # Create SQL toolkit and agent
            self.toolkit = SQLDatabaseToolkit(db=db, llm=llm)
            self.sql_agent = create_sql_agent(
                llm=llm,
                toolkit=self.toolkit,
                verbose=True,
                agent_type="openai-tools",
            )
            
            logger.info("SQL Agent initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing SQL agent: {str(e)}")
            raise
    
    def run(self):
        """
        Execute the SQL query and return the results.
        
        Returns:
            str: The query results or error message
        """
        try:
            if not self.sql_agent:
                self._initialize_sql_agent()
            
            # Run the query through the SQL agent
            result = self.sql_agent.invoke({"input": self.query})
            
            # Extract the final answer from the result
            if isinstance(result, dict) and "output" in result:
                return result["output"]
            return str(result)
            
        except Exception as e:
            error_msg = f"Error executing SQL query: {str(e)}"
            logger.error(error_msg)
            return error_msg

if __name__ == "__main__":
    # Test the SQL query tool
    tool = SQLQueryTool(query="List all tables in the database")
    print(tool.run()) 