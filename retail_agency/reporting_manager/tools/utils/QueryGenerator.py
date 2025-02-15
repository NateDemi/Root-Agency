from langchain_openai import ChatOpenAI
from langchain_community.agent_toolkits.sql.base import create_sql_agent
from langchain_community.agent_toolkits.sql.toolkit import SQLDatabaseToolkit
from langchain_community.utilities import SQLDatabase
from langchain_core.prompts.chat import (
    ChatPromptTemplate,
    MessagesPlaceholder,
    HumanMessagePromptTemplate,
    SystemMessagePromptTemplate,
)
from typing import Optional, Dict, Any
from dotenv import load_dotenv
import os
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Custom prompt that enforces structured output
QUERY_GENERATOR_PREFIX = """You are an agent designed to convert natural language questions into SQL queries.
Given an input question, create a syntactically correct {dialect} query.

Unless the user specifies a specific number of examples they wish to obtain, always limit your query to at most {top_k} results.
You can order the results by a relevant column to return the most interesting examples in the database.

Key Requirements:
1. Use ONLY the exact table names that exist in the database
2. Never use SELECT * - always list specific columns
3. DO NOT make any DML statements (INSERT, UPDATE, DELETE, DROP etc.)
4. Order results by relevant columns when it makes sense
5. Include proper joins when needed
6. Use appropriate aggregations and grouping

You have access to tools for interacting with the database.
Only use the below tools. Only use the information returned by the below tools to construct your final answer.
You MUST double-check your query before executing it.

IMPORTANT: When the sql_db_query tool returns results, you must include those exact results in your response.
Your final response MUST be valid JSON in the following format:
**JSON Structure:**
{{
    "question": "<the original question asked>",
    "sql_query": "<the SQL query you generated>",
    "limit_requested": <boolean indicating if LIMIT was explicitly requested in the question>,
    "columns": ["column1", "column2", ...],
    "sql_result": [ 
        [row1_value1, row1_value2, ...], 
        [row2_value1, row2_value2, ...] 
    ]
}}

**Guidelines:**
- Never change the structure.
- Always return `"columns"` as a list.
- Always return `"sql_result"` as a list of lists (rows).
- If there's an error, return: 
{{
    "question": "<the original question>",
    "sql_query": null,
    "limit_requested": false,
    "columns": [],
    "sql_result": []
}}"""

class QueryGenerator:
    """
    A class for generating SQL queries from natural language questions.
    This class focuses solely on query generation without execution.
    """
    
    def __init__(self, db_uri: str, schema: Optional[str] = None, dialect: str = "postgresql", top_k: int = 10):
        """Initialize the QueryGenerator with database connection and parameters."""
        self.dialect = dialect
        self.top_k = top_k
        self.llm = ChatOpenAI(temperature=0, model="gpt-4")
        
        # Initialize database connection
        self.db = SQLDatabase.from_uri(db_uri, schema=schema)
        
        # Create SQL toolkit and agent
        self.toolkit = SQLDatabaseToolkit(db=self.db, llm=self.llm)
        
        # Store the engine for direct query execution
        self.engine = self.db._engine
        
        # Create messages for the prompt
        messages = [
            SystemMessagePromptTemplate.from_template(QUERY_GENERATOR_PREFIX),
            HumanMessagePromptTemplate.from_template("{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
        
        # Create prompt
        prompt = ChatPromptTemplate.from_messages(messages).partial(
            dialect=self.dialect,
            top_k=self.top_k
        )
        
        # Create the SQL agent
        self.agent = create_sql_agent(
            llm=self.llm,
            toolkit=self.toolkit,
            agent_type="openai-tools",
            verbose=True,
            prompt=prompt
        )

    def generate_query(self, question: str) -> Dict[str, Any]:
        """Generate a SQL query from a natural language question."""
        try:
            # Run the agent with the question
            result = self.agent.invoke({"input": question})
            
            # Extract the agent's response
            if isinstance(result, dict) and "output" in result:
                try:
                    # Parse the JSON response
                    response = json.loads(result["output"])
                    return response
                except json.JSONDecodeError:
                    # If JSON parsing fails, return error format
                    return {
                        "question": question,
                        "sql_query": None,
                        "limit_requested": False,
                        "columns": [],
                        "sql_result": []
                    }
            else:
                # If response format is unexpected, return error format
                return {
                    "question": question,
                    "sql_query": None,
                    "limit_requested": False,
                    "columns": [],
                    "sql_result": []
                }
                
        except Exception as e:
            logger.error(f"Error generating query: {str(e)}")
            return {
                "question": question,
                "sql_query": None,
                "limit_requested": False,
                "columns": [],
                "sql_result": []
            }

if __name__ == "__main__":
    # Load environment variables
    load_dotenv()
    
    # Create database URI
    db_uri = f"postgresql+psycopg2://{os.getenv('CLOUD_DB_USER')}:{os.getenv('CLOUD_DB_PASS')}@{os.getenv('CLOUD_DB_HOST')}:{os.getenv('CLOUD_DB_PORT')}/{os.getenv('CLOUD_DB_NAME')}"
    
    # Initialize the QueryGenerator
    query_gen = QueryGenerator(
        db_uri=db_uri,
        schema=os.getenv('CLOUD_SCHEMA')
    )
    
    # Test questions
    test_questions = [
        "Show me inventory items with stock count below 5",
        "Get the top 10 items with lowest stock count",
        "List all items with price above 100 dollars",
        "Show me items that need restocking (stock count below 5) ordered by price"
    ]
    
    # Test each question
    for question in test_questions:
        print(f"\nTesting question: {question}")
        result = query_gen.generate_query(question)
        print(f"Result: {json.dumps(result, indent=2)}") 