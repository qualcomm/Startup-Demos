#===--init_db.py---------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

import json
import sqlite3
from pathlib import Path

# Get the current script directory
script_dir = Path(__file__).resolve().parent
print("script_dir",script_dir)

# Construct path to fares.json
fares_path = script_dir / 'modules' / 'config' / 'fares.json'

print("fares_path",fares_path)

# Check if fares.json exists
if not fares_path.exists():
    raise FileNotFoundError(f"fares.json not found at: {fares_path}")

# Load fares.json
with fares_path.open() as f:
    all_fares = json.load(f)

# Create DB directory
db_dir = script_dir / 'modules' / 'db'
db_dir.mkdir(exist_ok=True)

# Collect all unique cities
cities = set(all_fares.keys())
for destinations in all_fares.values():
    cities.update(destinations.keys())
cities = sorted(cities)

# Stations DB
stations_conn = sqlite3.connect(db_dir / 'stations.db')
stations_cursor = stations_conn.cursor()
stations_cursor.execute('CREATE TABLE IF NOT EXISTS stations (name TEXT)')
stations_cursor.execute('DELETE FROM stations')
stations_cursor.executemany('INSERT INTO stations (name) VALUES (?)', [(city,) for city in cities])
stations_conn.commit()
stations_conn.close()

# Fares DB
fares_conn = sqlite3.connect(db_dir / 'fares.db')
fares_cursor = fares_conn.cursor()
fares_cursor.execute('DROP TABLE IF EXISTS fares')
fares_cursor.execute('CREATE TABLE fares (source TEXT, destination TEXT, fare INTEGER, platform INTEGER)')
fare_entries = []
for source, destinations in all_fares.items():
    for destination, info in destinations.items():
        fare_entries.append((source, destination, info["fare"], info["platform"]))
fares_cursor.executemany('INSERT INTO fares (source, destination, fare, platform) VALUES (?, ?, ?, ?)', fare_entries)
fares_conn.commit()
fares_conn.close()

# Tickets DB
tickets_conn = sqlite3.connect(db_dir / 'tickets.db')
tickets_cursor = tickets_conn.cursor()
tickets_cursor.execute('''
CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    source_station TEXT,
    destination_station TEXT,
    ticket_count INTEGER,
    timestamp TEXT,
    qr_data TEXT,
    transcription TEXT,
    fare INTEGER,
    platform INTEGER
)
''')
tickets_conn.commit()
tickets_conn.close()

