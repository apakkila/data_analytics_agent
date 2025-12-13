from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import create_sql_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from sqlalchemy import create_engine
import pandas as pd
import os

# --- 1. CONFIGURATION ---
DB_NAME = 'uber_analytics_db'
DB_USER = 'uber_analytics_user'
DB_PASS = 'eiv2025' # WARNING: If your real password is NOT 'eiv2025', UPDATE THIS LINE
DB_HOST = 'localhost'
DB_PORT = '5432'
TABLE_NAME = 'cleaned_uber_rides'

# Global SQLAlchemy engine for manual query execution
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
try:
    ENGINE = create_engine(DATABASE_URL)
except Exception as e:
    # Handle error in case DB is down when script starts
    print(f"Warning: Database engine failed to create. Ensure PostgreSQL is running. Error: {e}")
    ENGINE = None

# --- 2. THE CUSTOM SYSTEM PROMPT (CRUCIAL for NL2SQL Accuracy) ---
# This prompt tells the LLM everything it needs to know to be a good data analyst.


CUSTOM_PROMPT = f"""
You are an expert data analyst chatbot specialized in ride-sharing data.
Your goal is to accurately translate user questions into optimized PostgreSQL queries.

CRITICAL RULE:
- You MUST ONLY query the view named "cleaned_uber_rides".
- You MUST NEVER query or reference any other table.
- If other tables exist, they are irrelevant and must be ignored.

--- CONTEXT ---
1. You are analyzing the '{TABLE_NAME}' **VIEW** in the '{DB_NAME}' PostgreSQL database.
2. The view contains ride-sharing data. **IMPORTANT:** All zero values (0 for ratings, distance, time, value) have been converted to NULL in this view.
3. The view has the following critical columns:
    - ride_timestamp: TIMESTAMP WITHOUT TIME ZONE (Use this for all time-based analysis and filtering).
    - booking_id: VARCHAR (Unique identifier for a ride. Use, e.g., for counting distinct rides).
    - customer_id: VARCHAR (Unique identifier for a customer, use for customer-based analysis).
    - pickup_location, drop_location: TEXT (Use for grouping and counting demand).
    - avg_waiting_time, avg_ride_time, booking_value, ride_distance: NUMERIC (NULL values indicate non-rides/non-data points).
    - payment_method: VARCHAR (Values are 'Unknown', 'UPI', 'Debit Card', 'Cash', 'Uber Wallet', 'Credit Card').
    - driver_ratings, customer_rating: NUMERIC (NULL values indicate unrated rides).
    - booking_status: VARCHAR (Unique values: 'Completed', 'Cancelled by Customer', 'Cancelled by Driver', 'No Driver Found', 'Incomplete').
    - customer_cancellation_reason, driver_cancellation_reason, incomplete_rides_reason: TEXT
    

--- RULES FOR SQL GENERATION ---
1. Always use PostgreSQL syntax.
2. When calculating averages (AVG) or sums (SUM) of any numeric column, the NULL values are automatically ignored by the view, so **DO NOT** add extra WHERE clauses for filtering (e.g., no 'WHERE customer_rating > 0').
3. When filtering by time, use the `ride_timestamp` column.
4. When counting rides, use `COUNT(booking_id)` to count distinct rides.
5. Always ensure your SQL queries are syntactically correct and optimized for PostgreSQL.
6. Output: Your final and ONLY answer must be the executable SQL query. START YOUR OUTPUT WITH THE EXACT STRING 'SQL_START:' AND DO NOT INCLUDE ANY INTRODUCTORY TEXT, EXPLANATION, OR MARKDOWN FORMATTING.
"""

# --- 3. AGENT SETUP FUNCTION ---
def setup_sql_agent():
    """Initializes the database connection and creates the LangChain SQL agent."""
    
    # Check for API Key
    if not os.getenv("GEMINI_API_KEY"):
        raise ValueError("GEMINI_API_KEY environment variable not set. Please set it in your terminal.")

    # 3a. Database Connection
    DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    try:
        # LangChain uses SQLAlchemy, which needs the full connection string.
        # CRITICAL: We explicitly tell it which table(s) to load AND which schema to look in.
        db = SQLDatabase.from_uri(
            database_uri=DATABASE_URL,
            include_tables=["cleaned_uber_rides"],
            sample_rows_in_table_info=5,
            schema="public",
            view_support=True
        )
    except Exception as e:
        print(f"Failed to connect to PostgreSQL: {e}")
        return None

    # 3b. Initialize the LLM (Gemini 2.5 Flash is fast and excellent for SQL)
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)

    # 3c. Create the SQL Agent
    # The agent is built with the LLM and the DB connection automatically as a tool.
    agent_executor = create_sql_agent(
        llm=llm,
        db=db,
        agent_type="openai-tools",
        verbose=True,  # IMPORTANT
        agent_executor_kwargs={
            "handle_parsing_errors": True,
            "return_intermediate_steps": False
        },
        system_message=CUSTOM_PROMPT
    )
    
    print("SQL Agent setup complete.")
    return agent_executor

def run_sql_query(sql_query):
    """Executes the final SQL query generated by the agent and returns a DataFrame."""
    if ENGINE is None:
        return "Error: Database engine not initialized."
    try:
        # Conversion happens here!
        df = pd.read_sql(sql_query, ENGINE) 
        return df
    except Exception as e:
        return f"Error executing query: {e}"
# ------------------------------------------------


if __name__ == '__main__':
    # Test case is now commented out to prevent running the agent every time the app is imported
    pass