To set up the project, do the following steps:
1. Install PostgreSQL to your computer
2. Set up the PostgreSQL database with the following commands:
   
``
cd scripts
``

``
python3 db_loading.py
``

3. After loading the database, run the following SQL command in pgAdmin:

``
CREATE OR REPLACE VIEW cleaned_uber_rides AS
SELECT
    booking_id,
    customer_id,
    ride_timestamp,
    booking_status,
    pickup_location,
    drop_location,
    -- Metrics must be greater than zero to be considered a valid event
    CASE WHEN avg_waiting_time > 0 THEN avg_waiting_time ELSE NULL END AS avg_waiting_time,
    CASE WHEN avg_ride_time > 0 THEN avg_ride_time ELSE NULL END AS avg_ride_time,
    CASE WHEN booking_value > 0 THEN booking_value ELSE NULL END AS booking_value,
    CASE WHEN ride_distance > 0 THEN ride_distance ELSE NULL END AS ride_distance,
    payment_method,
    customer_cancellation_reason,
    driver_cancellation_reason,
    incomplete_rides_reason,
    -- Ratings must be greater than zero to be considered a valid rating
    CASE WHEN driver_ratings > 0 THEN driver_ratings ELSE NULL END AS driver_ratings,
    CASE WHEN customer_rating > 0 THEN customer_rating ELSE NULL END AS customer_rating
FROM uber_rides_data
WHERE
    -- Filter out records where ALL metrics are zero (non-rides)
    (avg_waiting_time > 0 OR avg_ride_time > 0 OR booking_value > 0 OR ride_distance > 0 OR booking_status = 'Completed');
``


4. Change the directory to src:

``
cd ..
``

``
cd src
``

5. Run the data analytics application with the command:

``
streamlit run app.py
``

6. Ask the agent, e.g., some of the following questions:
- Give a distribution of booking values
- Sort the data by date and give the distribution of ride volumes by day
- Give the distribution of customer ratings
- Give the statistics of ride distances
- Give the distribution of ride volumes by hour of the day
- Give the distribution of ride volumes by hour of the day in July
   
