import pandas as pd
from sqlalchemy import create_engine, text
import os

pwd = os.getcwd()
csv_path = os.path.join(pwd, 'data', 'ncr_ride_bookings_cleaned.csv')

# --- 1. CONFIGURATION ---
DB_NAME = 'uber_analytics_db'
DB_USER = 'uber_analytics_user' # Use your username if different
DB_PASS = 'eiv2025' # CHANGE THIS to your password
DB_HOST = 'localhost'
DB_PORT = '5432'
CLEANED_DATA_PATH = csv_path
TABLE_NAME = 'uber_rides_data'

# --- 2. DATABASE CONNECTION STRING ---
# Format: 'postgresql://user:password@host:port/database'
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(DATABASE_URL)

def load_data_to_postgres(df):
    """
    Creates the table schema and loads the DataFrame data into PostgreSQL.
    """
    print(f"Connecting to database: {DB_NAME}...")

    # The column names used here MUST match the column names in your DataFrame (df_final)
    # Define the table creation SQL with specific types
    create_table_sql = f"""
    CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
        -- Identifiers and Core Ride Info
        booking_id VARCHAR(50) PRIMARY KEY,
        customer_id VARCHAR(50), 
        ride_timestamp TIMESTAMP WITHOUT TIME ZONE,
        booking_status VARCHAR(50),
        
        -- Location and Timing
        pickup_location TEXT,
        drop_location TEXT,
        avg_waiting_time NUMERIC(10, 2), -- Updated name: Avg VTAT -> avg_waiting_time
        avg_ride_time NUMERIC(10, 2),    -- Updated name: Avg CTAT -> avg_ride_time

        -- Financial and Distance Metrics
        booking_value NUMERIC(10, 2),
        ride_distance NUMERIC(10, 2),
        payment_method VARCHAR(50),

        -- Cancellation and Ratings Details
        customer_cancellation_reason TEXT,
        driver_cancellation_reason TEXT,
        incomplete_rides_reason TEXT,
        driver_ratings NUMERIC(2, 1),
        customer_rating NUMERIC(2, 1)
    );
"""

    try:
        with engine.connect() as connection:
            # Drop the table if it exists to ensure a clean start
            print(f"Dropping existing table {TABLE_NAME} (if any)...")
            connection.execute(text(f"DROP TABLE IF EXISTS {TABLE_NAME} CASCADE;"))
            connection.commit()

            # Create the table
            print(f"Creating table {TABLE_NAME} with defined schema...")
            connection.execute(text(create_table_sql))
            connection.commit()

            # 3. USE PANDAS to_sql FOR EFFICIENT INGESTION
            print(f"Loading data into {TABLE_NAME}...")
            df.to_sql(
                TABLE_NAME, 
                engine, 
                if_exists='append', # Append data to the newly created table
                index=False,        # Don't write the DataFrame index as a column
                method='multi'      # Use multi-row insert for better performance
            )
            print("Data loading complete.")

    except Exception as e:
        print(f"\n--- DATABASE ERROR ---")
        print(f"Failed to connect or load data. Check your config and ensure PostgreSQL is running.")
        print(f"Error: {e}")
        return

# --- EXECUTION ---
# Load the cleaned data from CSV
try:
    # Load the cleaned, column-filtered data
    df_cleaned = pd.read_csv(CLEANED_DATA_PATH)
    
    # Ensure timestamp is read correctly before loading (important when reading back from CSV)
    df_cleaned['ride_timestamp'] = pd.to_datetime(df_cleaned['ride_timestamp'])

    # Load the data into the database
    load_data_to_postgres(df_cleaned)

except FileNotFoundError:
    print(f"Error: Cleaned data file not found at {CLEANED_DATA_PATH}. Run the cleaning script first.")
except Exception as e:
    print(f"An unexpected error occurred: {e}")