import pandas as pd
from geopy.geocoders import Nominatim
from time import sleep
import os
import time

pwd = os.getcwd()
csv_path = os.path.join(pwd, '..', 'data', 'ncr_ride_bookings.csv')

# Load your CSV
df = pd.read_csv(csv_path)
print(len(df))
df = df[df['Booking Status'] == 'Completed']
print(len(df))
df = df[df['Pickup Location'] != 'NaN']
df = df[df['Drop Location'] != 'NaN']

df = df[:5000]
print(len(df))

df['Pickup Location'] = df['Pickup Location'].astype(str) + ', New Delhi, India'
df['Drop Location'] = df['Drop Location'].astype(str) + ', New Delhi, India'



# Initialize geocoder
geolocator = Nominatim(user_agent="geo_mapper")

# Define a function to fetch coordinates
def get_coords(location):
    try:
        loc = geolocator.geocode(location)
        if loc:
            return pd.Series([loc.latitude, loc.longitude])
    except Exception as e:
        print(f"Error fetching coordinates for {location}: {e}")
    return pd.Series([None, None])  # Ensure a valid Series is always returned

tic = time.time()
print(f'Start time: {tic}')

# Converting pickup locations to coordinates
df[['pickup_latitude', 'pickup_longitude']] = df['Pickup Location'].apply(get_coords)

# Converting drop-off locations to coordinates
df[['dropoff_latitude', 'dropoff_longitude']] = df['Drop Location'].apply(get_coords)

# Save the new CSV
df.to_csv('locations_with_coords.csv', index=False)

print(f'Finished in {time.time() - tic} seconds')
