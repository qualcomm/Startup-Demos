#===--clear_db.py.py----------------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//
import sqlite3
import os

def clear_tables():
    db_path = 'data/attendance.db'
    if not os.path.exists(db_path):
        print(f"Database file not found at {db_path}. Please ensure the database is initialized.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        cursor.execute("DELETE FROM students;")
        cursor.execute("DELETE FROM unknown_faces;")
        conn.commit()
        print("Successfully cleared 'students' and 'unknown_faces' tables.")
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    clear_tables()
