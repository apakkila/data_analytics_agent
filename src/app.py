import streamlit as st
import pandas as pd
import plotly.express as px
import re # Import for robust SQL extraction
from agent import setup_sql_agent, run_sql_query # Import core agent and DB execution functions

# --- 1. VISUALIZATION ORCHESTRATOR ---

def get_chart_type(df):
    """
    Determines the best chart type based on the returned DataFrame structure 
    following the rules:
    - Single Numeric      -> Histogram (if more than one unique value)
    - Timestamp + Numeric -> Line Chart
    - Text + Numeric      -> Bar Chart
    - Others              -> Data Table
    """
    
    if df.empty or len(df) == 0:
        return 'table'
    
    cols = df.columns
    
    # Rule 1: Single Column Numeric -> Histogram
    if len(cols) == 1 and pd.api.types.is_numeric_dtype(df[cols[0]]):
        # Only check if there's more than one unique value; otherwise, it's just a single AVG/SUM result.
        if df[cols[0]].nunique() > 1:
            return 'histogram'

    # Rule 2: Two Columns
    if len(cols) == 2:
        # Get column names for explicit checks
        col1, col2 = cols[0], cols[1]

        col2_is_numeric = pd.api.types.is_numeric_dtype(df[col2])
        
        # Rule 2a: Timestamp (or Date) + Numeric -> Line Chart (Uses robust Pandas check)
        if pd.api.types.is_datetime64_any_dtype(df[col1]) and col2_is_numeric:
            return 'line'
        
        # Rule 2b: Text (Category) + Numeric -> Bar Chart (Uses robust Pandas check)
        # Note: Must also check if the number of unique categories is manageable for a bar chart
        if pd.api.types.is_string_dtype(df[col1]) and col2_is_numeric and df[col1].nunique() < 50:
            return 'bar'
        
        # Fallback to bar if string type is not strictly inferred but is object/text
        if pd.api.types.infer_dtype(df[col1], skipna=True) in ['object', 'string'] and col2_is_numeric and df[col1].nunique() < 50:
             return 'bar'
            
    # Rule 3: More than two columns OR single aggregate number -> Data Table
    return 'table'

def create_visualization(df, user_query):
    """Creates a Plotly visualization based on the data and query context."""
    chart_type = get_chart_type(df)
    
    # Define user-friendly titles
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
        'ride_date': 'Ride Date' # Add ride_date to map
    }
    
    # Get column names for axes
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
                # --- FIRST ATTEMPT ---
                agent_output = agent.invoke({"input": prompt})
                
                # --- Robust Output Extraction (First Attempt) ---
                output = agent_output.get('output')
                raw_output = ""

                if isinstance(output, str):
                    raw_output = output
                elif isinstance(output, dict) and 'text' in output:
                    raw_output = output['text']
                elif isinstance(output, list) and output:
                    if isinstance(output[0], dict) and 'text' in output[0]:
                        raw_output = output[0]['text']
                
                try:
                    # Attempt to extract SQL from the potentially chatty raw_output
                    sql_query = extract_sql_or_raise(raw_output)
                except ValueError:
                    # 🔁 RETRY: If extraction failed due to chatter, try again with a strict, direct prompt
                    
                    st.warning("Agent's initial output was chatty. Retrying with stricter instructions...")

                    retry_prompt = (
                        "SQL_START: ONLY output a valid PostgreSQL SELECT query.\n"
                        "Do NOT explain anything.\n"
                        f"Question: {prompt}"
                    )
                    agent_output = agent.invoke({"input": retry_prompt})

                    # --- Robust Output Extraction (Second Attempt - MUST BE DUPLICATED) ---
                    output = agent_output.get('output')
                    raw_output = "" # Reset raw_output for the second attempt

                    if isinstance(output, str):
                        raw_output = output
                    elif isinstance(output, dict) and 'text' in output:
                        raw_output = output['text']
                    elif isinstance(output, list) and output:
                        if isinstance(output[0], dict) and 'text' in output[0]:
                            raw_output = output[0]['text']
                    
                    # FINAL ATTEMPT to extract the clean SQL from the second, strict output
                    sql_query = extract_sql_or_raise(raw_output)
                    
                st.info(f"Generated SQL Query: `{sql_query}`")

                # 2. Execute the Extracted SQL Query and convert to DataFrame
                df_result = run_sql_query(sql_query)
                
                if isinstance(df_result, str):
                    # Database execution failed (run_sql_query returned an error string)
                    st.error(df_result) 
                    final_text_output = f"Error executing SQL: {df_result}"
                else:
                    # 3. Create Visualization and Display
                    # CRITICAL: If the query returned a time-based column (like ride_date), convert it manually
                    # to ensure create_visualization detects the 'line' chart type correctly.
                    # We check for common date/time column names used by the LLM
                    date_cols = [col for col in df_result.columns if 'date' in col.lower() or 'time' in col.lower()]
                    if date_cols:
                         try:
                             df_result[date_cols[0]] = pd.to_datetime(df_result[date_cols[0]])
                         except Exception:
                             # Ignore if conversion fails (e.g., if column is just a string 'Completed')
                             pass
                         
                    create_visualization(df_result, prompt)
                    
                    final_text_output = "Analysis complete. See the generated visualization above."
                    st.success(final_text_output)

            except ValueError as ve:
                # Catches error from extract_sql_or_raise (No SQL found after two attempts)
                error_message = f"The agent failed to generate a valid SQL query. Output: {raw_output[:100]}... Error: {ve}"
                st.error(error_message)
                final_text_output = error_message

            except Exception as e:
                # Catches general LangChain/LLM errors
                error_message = f"An agent error occurred. Check your API key, database connection, or prompt. Error: {e}"
                st.error(error_message)
                final_text_output = error_message
                
    # Update chat history (MUST BE HERE, INSIDE the 'if prompt' block)
    st.session_state.messages.append({"role": "assistant", "content": final_text_output})


# --- TEMPORARY VISUALIZATION TEST ---
# This block runs every time the app loads to verify the database connection and visualization stack.
with st.expander("📊 Test Visualization Output"):
    st.subheader("Time Series Test: Ride Volume by Day")
    
    # This query tests the connection and the Line Chart logic
    df_test = run_sql_query("""
        SELECT DATE_TRUNC('day', ride_timestamp) AS ride_day,
               COUNT(booking_id) AS ride_volume
        FROM cleaned_uber_rides
        GROUP BY ride_day
        ORDER BY ride_day
        LIMIT 10
    """)

    if isinstance(df_test, pd.DataFrame) and not df_test.empty:
        
        # CRITICAL FIX: Explicitly convert the date column to datetime type
        df_test['ride_day'] = pd.to_datetime(df_test['ride_day']) 
        
        create_visualization(df_test, "Ride Volume over 10 Days")
        st.success("Test Plot Generated Successfully: Connection and Visualization Stack OK.")
    elif isinstance(df_test, str):
        st.error(f"Test Failed: Database Connection/Execution Error: {df_test}")
    else:
         st.warning("Test Plot Generated, but DataFrame was empty.")

# --- END OF TEMPORARY TEST ---