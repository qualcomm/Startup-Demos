#===--dashboard.py---------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

import streamlit as st
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO
from pathlib import Path

# Resolve base directory and DB path
BASE_DIR = Path(__file__).resolve().parents[2]
DB_PATH = BASE_DIR / 'modules' / 'db' / 'tickets.db'

def load_data():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM tickets ORDER BY timestamp DESC", conn)
    conn.close()

    # Add a summary column replacing transcription
    df['summary'] = df.apply(
        lambda row: f"{row['source_station']} → {row['destination_station']} ({row['ticket_count']} tickets)", axis=1
    )
    return df

def convert_df_to_csv(df):
    export_df = df[[
        'id', 'username', 'source_station', 'destination_station',
        'ticket_count', 'timestamp', 'summary', 'fare', 'platform'
    ]]
    return export_df.to_csv(index=False).encode('utf-8')

def dashboard_page():
    st.title("📊 Ticket Dashboard")
    df = load_data()

    # 📅 Date Range Filter
    st.subheader("📅 Filter by Date Range")
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    min_date = df['timestamp'].min().date()
    max_date = df['timestamp'].max().date()
    start_date = st.date_input("Start Date", min_value=min_date, max_value=max_date, value=min_date)
    end_date = st.date_input("End Date", min_value=min_date, max_value=max_date, value=max_date)

    filtered_df = df[(df['timestamp'].dt.date >= start_date) & (df['timestamp'].dt.date <= end_date)]

    # 📋 Display Filtered Data
    st.dataframe(filtered_df[[
        'id', 'username', 'source_station', 'destination_station',
        'ticket_count', 'timestamp', 'summary', 'fare', 'platform'
    ]])

    # 📤 Export to CSV
    st.subheader("📤 Export Filtered Data")
    csv = convert_df_to_csv(filtered_df)
    st.download_button("Download CSV", csv, "filtered_tickets.csv", "text/csv")

    # 📊 Most Popular Destinations
    st.subheader("📊 Most Popular Destinations")
    if not filtered_df.empty:
        dest_counts = filtered_df['destination_station'].value_counts()
        fig, ax = plt.subplots()
        dest_counts.plot(kind='bar', ax=ax, color='skyblue')
        ax.set_xlabel("Destination")
        ax.set_ylabel("Tickets Sold")
        ax.set_title("Top Destinations")
        st.pyplot(fig)
    else:
        st.info("No data available for the selected date range.")

    # 📝 Ticket Cancellation or Editing
    st.subheader("📝 Edit or Cancel Ticket")
    if not filtered_df.empty:
        ticket_ids = filtered_df['id'].tolist()
        selected_id = st.selectbox("Select Ticket ID", ticket_ids)
        action = st.radio("Action", ["Cancel Ticket", "Edit Ticket Count"])

        if action == "Cancel Ticket":
            if st.button("Confirm Cancellation"):
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                cursor.execute("DELETE FROM tickets WHERE id=?", (selected_id,))
                conn.commit()
                conn.close()
                st.success(f"✅ Ticket ID {selected_id} cancelled.")

        elif action == "Edit Ticket Count":
            new_count = st.number_input("New Ticket Count", min_value=1, max_value=10, value=1)
            if st.button("Update Ticket"):
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()

                # Fetch original fare and ticket count
                cursor.execute("SELECT fare, ticket_count FROM tickets WHERE id=?", (selected_id,))
                result = cursor.fetchone()

                if result:
                    original_total_fare, old_count = result
                    if old_count > 0:
                        fare_per_ticket = original_total_fare / old_count
                        new_total_fare = fare_per_ticket * new_count

                        # Update ticket count and fare
                        cursor.execute("UPDATE tickets SET ticket_count=?, fare=? WHERE id=?", (new_count, new_total_fare, selected_id))
                        conn.commit()
                        st.success(f"✅ Ticket ID {selected_id} updated to {new_count} tickets. New fare: ₹{int(new_total_fare)}")
                    else:
                        st.error("⚠️ Original ticket count is zero. Cannot compute fare per ticket.")
                else:
                    st.error("❌ Ticket ID not found.")

                conn.close()
    else:
        st.info("No tickets available to edit or cancel.")

