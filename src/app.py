import streamlit as st
import pandas as pd
import plotly.express as px
import re # Import for robust SQL extraction
from agent import setup_sql_agent, run_sql_query # Import core agent and DB execution functions

# --- 1. VISUALIZATION ORCHESTRATOR (No Changes Needed Here) ---

def get_chart_type(df):
    """
    Determines the best chart type based on the returned DataFrame structure 
    following the rules:
    ... (All functions: get_chart_type, create_visualization are kept as is)
    """
    
    if df.empty or len(df) == 0:
        return 'table'
    
    cols = df.columns
    
    # Rule 1: Single Column Numeric -> Histogram
    if len(cols) == 1 and pd.api.types.is_numeric_dtype(df[cols[0]]):
        if df[cols[0]].nunique() > 1:
            return 'histogram'

    # Rule 2: Two Columns
    if len(cols) == 2:
        col1, col2 = cols[0], cols[1]
        col2_is_numeric = pd.api.types.is_numeric_dtype(df[col2])
        
        # Rule 2a: Timestamp (or Date) + Numeric -> Line Chart
        if pd.api.types.is_datetime64_any_dtype(df[col1]) and col2_is_numeric:
            return 'line'
        
        # Rule 2b: Text (Category) + Numeric -> Bar Chart
        if pd.api.types.is_string_dtype(df[col1]) and col2_is_numeric and df[col1].nunique() < 50:
            return 'bar'
        
        if pd.api.types.is_numeric_dtype(df[col1]) and col2_is_numeric:
            return 'bar'
        
        # Fallback to bar
        if pd.api.types.infer_dtype(df[col1], skipna=True) in ['object', 'string'] and col2_is_numeric and df[col1].nunique() < 50:
             return 'bar'
            
    # Rule 3: Data Table
    return 'table'

def create_visualization(df, user_query):
    # ... (Visualization logic is correct)
    chart_type = get_chart_type(df)
    
    col_map = {
        'count': 'Total Number of Bookings',
        'avg': 'Average Value',
        'sum': 'Total Revenue',
        'customer_rating': 'Customer Rating (Avg)',
        'driver_ratings': 'Driver Rating (Avg)',
        'pickup_location': 'Pickup Location',
        'drop_location': 'Drop Location',
        'booking_value': 'Booking Value',
        'ride_distance': 'Ride Distance (km)',
        'ride_day': 'Ride Day',
        'ride_date': 'Ride Date'
    }
    
    cols = df.columns
    
    if chart_type == 'bar' and len(cols) == 2:
        x_col, y_col = cols[0], cols[1]
        fig = px.bar(df, 
                     x=x_col, 
                     y=y_col, 
                     title=f"Results for: {user_query}",
                     labels={x_col: col_map.get(x_col, x_col.replace('_', ' ').title()),
                             y_col: col_map.get(y_col, y_col.replace('_', ' ').title())},
                     template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)

    elif chart_type == 'line' and len(cols) == 2:
        x_col, y_col = cols[0], cols[1]
        fig = px.line(df, 
                      x=x_col, 
                      y=y_col, 
                      title=f"Time Series: {user_query}",
                      labels={x_col: col_map.get(x_col, "Time/Date"),
                              y_col: col_map.get(y_col, y_col.replace('_', ' ').title())},
                      template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)
    
    elif chart_type == 'histogram' and len(cols) == 1:
        x_col = cols[0]
        fig = px.histogram(df, x=x_col, 
                           title=f"Distribution for: {user_query}",
                           labels={x_col: col_map.get(x_col, x_col.replace('_', ' ').title())},
                           template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)
    
    else:
        st.subheader("Query Result")
        st.dataframe(df, use_container_width=True)


def extract_sql_or_raise(raw_output: str) -> str:
    """Aggressively finds the first valid SQL query in a potentially messy string."""
    
    # Aggressively remove common LLM chat headers and markdown blocks
    cleaned_output = raw_output.strip()
    
    # Use the SQL_START marker for robust extraction (from agent.py prompt rule)
    if 'sql_start:' in cleaned_output.lower():
        cleaned_output = cleaned_output[cleaned_output.lower().find('sql_start:') + len('sql_start:'):]
        
    cleaned_output = cleaned_output.replace('```sql', '').replace('```', '')
    
    # 3. Use regex to find the query starting with SELECT or WITH
    sql_match = re.search(
        r'\b(SELECT|WITH)\b[\s\S]*',
        cleaned_output,
        re.IGNORECASE | re.DOTALL  # DOTALL allows it to span multiple lines
    )
    if not sql_match:
        # If the direct output is failing, raise a clear error
        raise ValueError(f"Agent failed to provide executable SQL. Raw output: {raw_output}")
    
    # Return the matched query, stripping trailing semicolon and whitespace
    return sql_match.group(0).strip().rstrip(';')

# --- 2. STREAMLIT APP CORE ---

# Initialize the agent once
@st.cache_resource
def get_agent():
    return setup_sql_agent()

# The agent is now a Generator Chain
agent = get_agent()

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.messages.append({"role": "assistant", "content": "Hello! I am your Uber Ride Data Analyst. Ask me anything about the ride data (e.g., 'Show top 5 pickup locations' or 'What was the average ride distance for Cash payments?')."})

st.title("🚗 Uber Ride Data Analyst")

# Display chat messages from history on app rerun
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# React to user input (Main Logic)
if prompt := st.chat_input("Ask a question about the ride data..."):
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    final_text_output = "" # Initialize here for safety
    
    with st.chat_message("assistant"):
        with st.spinner("Analyzing data and generating query..."):
            
            try:
                # 1. Invoke the Generator Chain
                # The input to the chain MUST be a dictionary matching the prompt template keys.
                # The output is expected to be a clean SQL string.
                sql_raw_output = agent.invoke({"question": prompt})
                
                # 2. Extract and Validate SQL (Simplest extraction, no nested dict/list checks)
                # We still use the robust extractor just in case the LLM adds markdown.
                sql_query = extract_sql_or_raise(sql_raw_output)
                    
                st.info(f"Generated SQL Query: `{sql_query}`")

                # 3. Execute the Extracted SQL Query and convert to DataFrame
                df_result = run_sql_query(sql_query)
                
                if isinstance(df_result, str):
                    # Database execution failed (run_sql_query returned an error string)
                    st.error(df_result) 
                    final_text_output = f"Error executing SQL: {df_result}"
                else:
                    # 4. Create Visualization and Display
                    
                    # CRITICAL: If the query returned a time-based column (like ride_date), convert it manually
                    date_cols = [col for col in df_result.columns if 'date' in col.lower() or 'time' in col.lower()]
                    if date_cols:
                         try:
                             df_result[date_cols[0]] = pd.to_datetime(df_result[date_cols[0]])
                         except Exception:
                             pass
                         
                    create_visualization(df_result, prompt)
                    
                    final_text_output = "Analysis complete. See the generated visualization above."
                    st.success(final_text_output)

            except ValueError as ve:
                # Catches error from extract_sql_or_raise (The chain did not output valid SQL)
                error_message = f"The Generator Chain failed to produce valid SQL. Output: {sql_raw_output[:100]}... Error: {ve}"
                st.error(error_message)
                final_text_output = error_message

            except Exception as e:
                # Catches general LangChain/LLM errors
                error_message = f"An agent error occurred. Check your API key, database connection, or prompt. Error: {e}"
                st.error(error_message)
                final_text_output = error_message
                
    # Update chat history (MUST BE HERE, INSIDE the 'if prompt' block)
    st.session_state.messages.append({"role": "assistant", "content": final_text_output})


# --- TEMPORARY VISUALIZATION TEST (No Changes Needed Here) ---
with st.expander("📊 Test Visualization Output"):
    st.subheader("Time Series Test: Ride Volume by Day")
    
    df_test = run_sql_query("""
        SELECT DATE_TRUNC('day', ride_timestamp) AS ride_day,
               COUNT(booking_id) AS ride_volume
        FROM cleaned_uber_rides
        GROUP BY ride_day
        ORDER BY ride_day
        LIMIT 10
    """)

    if isinstance(df_test, pd.DataFrame) and not df_test.empty:
        df_test['ride_day'] = pd.to_datetime(df_test['ride_day']) 
        create_visualization(df_test, "Ride Volume over 10 Days")
        st.success("Test Plot Generated Successfully: Connection and Visualization Stack OK.")
    elif isinstance(df_test, str):
        st.error(f"Test Failed: Database Connection/Execution Error: {df_test}")
    else:
         st.warning("Test Plot Generated, but DataFrame was empty.")
# --- END OF TEMPORARY TEST ---