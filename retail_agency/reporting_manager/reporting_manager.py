from langchain_community.utilities import SQLDatabase
from langchain_openai import ChatOpenAI
from langchain_community.agent_toolkits.sql.base import create_sql_agent
from langchain_community.agent_toolkits.sql.toolkit import SQLDatabaseToolkit
import logging
import os
from typing import List, Dict, Any, Union, Tuple
from utils.db_connection import get_db_engine
from agency_swarm import Agent
import pandas as pd
from sqlalchemy import text
from .tools.DataAnalyzer import DataAnalyzer
from .tools.SQLQueryTool import SQLQueryTool

logger = logging.getLogger(__name__)

class ReportingManager(Agent):
    """SQL Agent that handles database queries and reporting."""
    
    def __init__(self):
        """Initialize the ReportingManager as a SQL Agent."""
        super().__init__(
            name="ReportingManager",
            description=(
                "An advanced SQL Agent that handles database queries, reporting, and analytics. "
                "Specializes in generating insights from retail data, including sales analysis, "
                "inventory management, and vendor performance metrics."
            ),
            instructions="./instructions.md",
            tools=[DataAnalyzer, SQLQueryTool],
            temperature=0,
            model="gpt-4"
        )
        
        # Initialize SQL Agent components
        self.engine = get_db_engine()
        self._initialize_db_and_agent()
        
        logger.info("SQL Agent initialized successfully")

    def _get_schema_info(self) -> Dict[str, Any]:
        """
        Dynamically discover schema information including tables, columns, and relationships.
        """
        try:
            # Set search path to sales_data schema
            with self.engine.connect() as conn:
                conn.execute(text("SET search_path TO sales_data"))
                conn.commit()
            
            # Query to get table information
            tables_query = text("""
            SELECT 
                t.table_name,
                obj_description(pgc.oid, 'pg_class') as table_comment,
                json_agg(json_build_object(
                    'column_name', c.column_name,
                    'data_type', c.data_type,
                    'column_comment', pgd.description
                )) as columns
            FROM information_schema.tables t
            JOIN pg_class pgc ON t.table_name = pgc.relname
            JOIN information_schema.columns c ON t.table_name = c.table_name
            LEFT JOIN pg_description pgd ON 
                pgd.objoid = pgc.oid AND 
                pgd.objsubid = c.ordinal_position
            WHERE t.table_schema = 'sales_data'
            GROUP BY t.table_name, pgc.oid;
            """)
            
            # Query to get foreign key relationships
            fk_query = text("""
            SELECT
                tc.table_name as table_name,
                kcu.column_name as column_name,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
                AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
                AND tc.table_schema = 'sales_data';
            """)
            
            # Execute queries using pandas
            with self.engine.connect() as conn:
                tables_info = pd.read_sql(tables_query, conn)
                relationships = pd.read_sql(fk_query, conn)
            
            # Format the schema information
            schema_info = {
                "tables": tables_info.to_dict(orient='records'),
                "relationships": relationships.to_dict(orient='records')
            }
            
            return schema_info
            
        except Exception as e:
            logger.error(f"Error getting schema info: {str(e)}", exc_info=True)
            return {"tables": [], "relationships": []}

    def _generate_system_prompt(self, schema_info: Dict[str, Any]) -> str:
        """
        Generate a dynamic system prompt based on the discovered schema information.
        """
        # Start with base prompt
        prompt = """You are a helpful SQL agent that helps users get insights from their retail store database.
You have access to tables in the sales_data schema containing sales and customer information.

Available tables and their purposes:
"""
        
        # Add table information
        for table in schema_info["tables"]:
            prompt += f"- {table['table_name']}"
            if table['table_comment']:
                prompt += f": {table['table_comment']}"
            prompt += "\n"
            
            # Add column information
            columns = table['columns']
            if columns:
                prompt += "  Columns:\n"
                for col in columns:
                    prompt += f"  - {col['column_name']} ({col['data_type']})"
                    if col['column_comment']:
                        prompt += f": {col['column_comment']}"
                    prompt += "\n"
        
        # Add relationships
        if schema_info["relationships"]:
            prompt += "\nTable relationships:\n"
            for rel in schema_info["relationships"]:
                prompt += f"- {rel['table_name']}.{rel['column_name']} links to {rel['foreign_table_name']}.{rel['foreign_column_name']}\n"
        
        # Add query guidelines
        prompt += """
When responding to queries:
1. Write clear, efficient SQL queries
2. Format currency values with $ and 2 decimal places using CAST(... AS NUMERIC(12,2))
3. Use clear column names and aliases
4. Join relevant tables to get meaningful insights
5. For date-based queries:
   - Use CURRENT_DATE for today
   - Use INTERVAL for date ranges (e.g., CURRENT_DATE - INTERVAL '30 days')
   - Format dates using TO_CHAR(date_column, 'YYYY-MM-DD')
6. Include relevant context and insights with the data
7. Format numbers appropriately:
   - Use TO_CHAR(number, 'FM999,999,999.00') for currency
   - Use TO_CHAR(number, 'FM999,999,999') for integers
8. For sales analysis:
   - Calculate totals using SUM(price) or SUM(amount)
   - Group by relevant dimensions (date, product, category)
   - Include counts using COUNT(DISTINCT order_id)
   - Calculate averages using AVG()
   - Sort results appropriately (usually DESC for metrics)
   - Limit results to a reasonable number (e.g., TOP 10)

Important Notes:
- Always use the sales_data schema
- For date/time operations, use PostgreSQL's INTERVAL syntax
- All queries should be executed with explicit schema reference (e.g., sales_data.orders)
- Handle NULL values appropriately using COALESCE()
- Use CTEs (WITH clause) for complex queries to improve readability
"""
        
        return prompt

    def _initialize_db_and_agent(self):
        """
        Initialize the database connection and SQL agent with dynamic schema information.
        """
        try:
            # Get schema information
            schema_info = self._get_schema_info()
            
            # Initialize SQLDatabase with the engine
            self.db = SQLDatabase(
                engine=self.engine,
                schema="sales_data",
                sample_rows_in_table_info=3,
                include_tables=None  # Allow all tables in the schema
            )
            
            # Initialize LLM
            self.llm = ChatOpenAI(
                temperature=0,
                model="gpt-4",
                api_key=os.getenv("OPENAI_API_KEY")
            )
            
            # Create toolkit
            self.toolkit = SQLDatabaseToolkit(
                db=self.db,
                llm=self.llm
            )
            
            # Generate dynamic system prompt
            system_prompt = self._generate_system_prompt(schema_info)
            
            # Create SQL agent with updated configuration
            self.agent_executor = create_sql_agent(
                llm=self.llm,
                toolkit=self.toolkit,
                verbose=True,
                agent_type="openai-tools",
                handle_parsing_errors=True,
                top_k=3  # Return top 3 most relevant tables
            )
            
            logger.info("SQL Agent initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing database and agent: {str(e)}", exc_info=True)
            raise

    def handle_message(self, message: str) -> str:
        """
        Handle incoming messages by executing SQL queries and returning results.
        
        Args:
            message: The query message
            
        Returns:
            str: The query results with analysis and insights
        """
        try:
            logger.info(f"ReportingManager received query: {message}")
            
            # Execute query through SQL agent
            response = self.agent_executor.invoke({"input": message})
            
            # Format the response
            result = response["output"] if isinstance(response, dict) else str(response)
            
            # Add context and insights
            final_response = f"""Analysis Results:
{result}

Note: All currency values are in USD. Data is current as of {os.getenv('CURRENT_DATE', 'today')}.
For any specific data requirements or custom analysis, please feel free to ask."""
            
            logger.info("Query executed successfully")
            return final_response
            
        except Exception as e:
            error_msg = f"Error executing query: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return f"""I apologize, but I encountered an error while executing your query:
{str(e)}

Please try rephrasing your request or provide more specific details about what you'd like to analyze."""

if __name__ == "__main__":
    # Test the ReportingManager
    agent = ReportingManager()
    test_queries = [
        "Show me total sales by product for today, including quantity sold and total revenue",
        "What are our top 5 selling products this month?",
        "Show me inventory items with less than 20 units in stock",
        "What is our average order value for the past 30 days?"
    ]
    
    for query in test_queries:
        print(f"\nTesting query: {query}")
        print("-" * 80)
        print(agent.handle_message(query))
        print("-" * 80) 