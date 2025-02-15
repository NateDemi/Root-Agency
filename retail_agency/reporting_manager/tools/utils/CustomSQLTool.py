from langchain_community.utilities import SQLDatabase
from langchain_openai import ChatOpenAI
from langchain_community.agent_toolkits import create_sql_agent
from langchain_community.agent_toolkits.sql.toolkit import SQLDatabaseToolkit
from langchain_core.prompts import PromptTemplate
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

# Custom prompt that enforces structured output
CUSTOM_SQL_PREFIX = """You are an agent designed to interact with a SQL database.
Given an input question, create a syntactically correct {dialect} query to run, then look at the results of the query and return the answer.
Unless the user specifies a specific number of examples they wish to obtain or asks for pagination, always limit your query to at most {top_k} results.
You can order the results by a relevant column to return the most interesting examples in the database.
Never query for all the columns from a specific table, only ask for the relevant columns given the question.

You have access to tools for interacting with the database.
Only use the below tools. Only use the information returned by the below tools to construct your final answer.
You MUST double-check your query before executing it. If you get an error while executing a query, rewrite the query and try again.

DO NOT make any DML statements (INSERT, UPDATE, DELETE, DROP, etc.) to the database.

If the question asks for a count, you should return a COUNT(*) query.
If the question asks for a specific page with items per page, you should ONLY add LIMIT and OFFSET to your query:
- Use LIMIT <page_size>
- Calculate OFFSET as (page_number - 1) * page_size
For example: "... LIMIT 10 OFFSET 20" for page 3 with 10 items per page.
When handling pagination, do NOT add any additional LIMIT clauses beyond what's needed for the pagination.

IMPORTANT: When the sql_db_query tool returns results, you must include those exact results in your response.
Your final response MUST be valid JSON in the following format:
**JSON Structure:**
{{
    "question": "<the original question asked>",
    "sql_query": "<the SQL query you generated and executed>",
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
    "columns": [],
    "sql_result": []
}}"""

def create_structured_sql_agent(
    llm: ChatOpenAI,
    db: SQLDatabase,
    verbose: bool = True,
    top_k: int = 10,
    **kwargs: Any
) -> Any:
    """Create a SQL agent that returns structured output."""
    
    # Create the toolkit with Langchain's standard tools
    toolkit = SQLDatabaseToolkit(db=db, llm=llm)

    # Create messages for the prompt
    messages = [
        SystemMessagePromptTemplate.from_template(CUSTOM_SQL_PREFIX),
        HumanMessagePromptTemplate.from_template("{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ]
    
    # Create prompt
    prompt = ChatPromptTemplate.from_messages(messages).partial(
        dialect=toolkit.dialect,
        top_k=top_k
    )
    
    # Create the agent using Langchain's standard SQL agent creator
    return create_sql_agent(
        llm=llm,
        toolkit=toolkit,
        verbose=verbose,
        agent_type="openai-tools",
        prompt=prompt,
        **kwargs
    )

if __name__ == "__main__":
    # Load environment variables
    load_dotenv()
    
    # Initialize database connection
    db = SQLDatabase.from_uri(
        f"postgresql+psycopg2://{os.getenv('CLOUD_DB_USER')}:{os.getenv('CLOUD_DB_PASS')}@{os.getenv('CLOUD_DB_HOST')}:{os.getenv('CLOUD_DB_PORT')}/{os.getenv('CLOUD_DB_NAME')}",
        schema=os.getenv('CLOUD_SCHEMA')
    )
    
    # Initialize LLM
    llm = ChatOpenAI(temperature=0, model="gpt-4")
    
    # Create the agent
    agent = create_structured_sql_agent(
        llm=llm,
        db=db,
        verbose=True  # This will show the agent's thought process
    )
    
    # Test query
    query = "Get me a list of all inventory with a low stock level below 5"
    
    print(f"\nExecuting query: {query}")
    response = agent.invoke({"input": query})
    
    # Try to parse and format the JSON response
    try:
        if isinstance(response, dict) and 'output' in response:
            result = json.loads(response['output'])
            print("\nFormatted Response:")
            print("==================")
            print(f"Question: {result['question']}")
            print(f"SQL Query: {result['sql_query']}")
            print("\nResults:")
            print(result['sql_result'])
        else:
            print("\nRaw Response:")
            print(response)
    except Exception as e:
        print("\nRaw Response:")
        print(response)
        print(f"\nError parsing response: {str(e)}")