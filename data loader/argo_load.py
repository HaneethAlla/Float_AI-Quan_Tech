import psycopg2
from netCDF4 import Dataset, num2date, chartostring
import numpy as np
import os

# ✅ Connect to PostgreSQL
conn = psycopg2.connect(
    dbname="ocean_db2",   # your database name
    user="postgres",
    password="9669",   # change to your password
    host="localhost",
    port="5432"
)
cur = conn.cursor()

# ✅ Create table if not exists
cur.execute("""
CREATE TABLE IF NOT EXISTS argo_profile_data (
    id SERIAL PRIMARY KEY,
    float_id VARCHAR(50),
    cycle_number INT,
    juld TIMESTAMP,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    pressure DOUBLE PRECISION,
    temperature DOUBLE PRECISION,
    salinity DOUBLE PRECISION
);
""")
conn.commit()


# ✅ THIS IS THE FUNCTION YOU NEED TO COPY AND PASTE
def process_nc_file(nc_file):
    try:
        ds = Dataset(nc_file, "r")
        
        # Extract metadata
        float_id = chartostring(ds.variables["PLATFORM_NUMBER"][:]).tobytes().decode("utf-8").strip().replace("\x00", "")
        cycles = ds.variables["CYCLE_NUMBER"][:]
        julds = ds.variables["JULD"][:]
        latitudes = ds.variables["LATITUDE"][:]
        longitudes = ds.variables["LONGITUDE"][:]

        # Convert JULD → datetime
        time_units = ds.variables["JULD"].units
        time_calendar = getattr(ds.variables["JULD"], "calendar", "standard")
        times = num2date(julds, units=time_units, calendar=time_calendar)

        # Profile variables
        pres = ds.variables["PRES"][:]
        temp = ds.variables["TEMP"][:]
        psal = ds.variables["PSAL"][:]

        # Loop over profiles (cycles)
        for i in range(len(cycles)):
            try:
                cycle = int(cycles[i])
                time_val = times[i].isoformat() if hasattr(times[i], "isoformat") else str(times[i])
                lat = float(latitudes[i])
                lon = float(longitudes[i])

                pres_profile = pres[i, :]
                temp_profile = temp[i, :]
                psal_profile = psal[i, :]

                pres_avg = float(np.nanmean(pres_profile)) if np.any(~pres_profile.mask) else None
                temp_avg = float(np.nanmean(temp_profile)) if np.any(~temp_profile.mask) else None
                psal_avg = float(np.nanmean(psal_profile)) if np.any(~psal_profile.mask) else None

                # New debugging print statement
                print(f"Attempting to insert: ID={float_id}, Cycle={cycle}, Time={time_val}, Lat={lat}, Lon={lon}, Pres={pres_avg}, Temp={temp_avg}, Sal={psal_avg}")
                
                cur.execute("""
                    INSERT INTO argo_profile_data
                    (float_id, cycle_number, juld, latitude, longitude, pressure, temperature, salinity)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (float_id, cycle, time_val, lat, lon, pres_avg, temp_avg, psal_avg))
                
                # Commit after each successful insert
                conn.commit()

            except Exception as e:
                # If an error occurs, print it and roll back the transaction
                print(f"❌ ERROR on Cycle {cycle} in {os.path.basename(nc_file)}: {e}")
                conn.rollback() 
        
        ds.close()

    except Exception as e:
        # This will catch errors in opening the file or reading metadata
        print(f"❌ FATAL ERROR processing file {nc_file}: {e}")

# ✅ Process all .nc files in a folder
folder = "E:/sih/prototype/"   # change this to your folder path
for file in os.listdir(folder):
    if file.endswith(".nc"):
        process_nc_file(os.path.join(folder, file))
cur.close()
conn.close()