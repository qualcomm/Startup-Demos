#===--database.py----------------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//
import os
import sqlite3
import datetime
import pandas as pd
import numpy as np

def create_directories():
    os.makedirs('data/known_faces', exist_ok=True)
    os.makedirs('data/unknown_faces', exist_ok=True)


def init_db():
    create_directories()
    conn = sqlite3.connect('data/attendance.db')
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        face_embedding BLOB,
        registration_date TEXT
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY,
        student_id INTEGER,
        date TEXT,
        time TEXT,
        FOREIGN KEY (student_id) REFERENCES students (id)
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS unknown_faces (
        id INTEGER PRIMARY KEY,
        image_path TEXT,
        date TEXT,
        time TEXT
    )
    ''')
    
    conn.commit()
    conn.close()

def add_student(name, face_embedding):
    conn = sqlite3.connect('data/attendance.db')
    cursor = conn.cursor()
    
    registration_date = datetime.datetime.now().strftime("%Y-%m-%d")
    cursor.execute(
        "INSERT INTO students (name, face_embedding, registration_date) VALUES (?, ?, ?)",
        (name, face_embedding.tobytes(), registration_date)
    )
    
    student_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return student_id

def get_all_students():
    conn = sqlite3.connect('data/attendance.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, name, face_embedding FROM students")
    students = cursor.fetchall()
    
    result = []
    for student in students:
        student_id, name, face_embedding_bytes = student
        face_embedding = np.frombuffer(face_embedding_bytes, dtype=np.float32)
        result.append((student_id, name, face_embedding))
    
    conn.close()
    return result

def mark_attendance(student_id):
    conn = sqlite3.connect('data/attendance.db')
    cursor = conn.cursor()
    
    now = datetime.datetime.now()
    today = now.strftime("%Y-%m-%d")
    current_hour = now.hour
    
    cursor.execute(
        "SELECT * FROM attendance WHERE student_id = ? AND date = ? AND CAST(SUBSTR(time, 1, 2) AS INTEGER) = ?",
        (student_id, today, current_hour)
    )
    
    if cursor.fetchone() is None:
        current_time = now.strftime("%H:%M:%S")
        cursor.execute(
            "INSERT INTO attendance (student_id, date, time) VALUES (?, ?, ?)",
            (student_id, today, current_time)
        )
        conn.commit()
        conn.close()
        return True
    
    conn.close()
    return False

def record_unknown_face(image_path):
    conn = sqlite3.connect('data/attendance.db')
    cursor = conn.cursor()
    
    current_date = datetime.datetime.now().strftime("%Y-%m-%d")
    current_time = datetime.datetime.now().strftime("%H:%M:%S")
    
    cursor.execute(
        "INSERT INTO unknown_faces (image_path, date, time) VALUES (?, ?, ?)",
        (image_path, current_date, current_time)
    )
    
    conn.commit()
    conn.close()


def get_attendance_records(date=None):
    conn = sqlite3.connect('data/attendance.db')
    
    if date is None:
        date = datetime.datetime.now().strftime("%Y-%m-%d")
    
    query = '''
    SELECT s.name, a.date, a.time 
    FROM attendance a 
    JOIN students s ON a.student_id = s.id 
    WHERE a.date = ? 
    ORDER BY a.time
    '''
    
    df = pd.read_sql_query(query, conn, params=(date,))
    conn.close()
    return df

def get_unknown_faces(date=None):
    conn = sqlite3.connect('data/attendance.db')
    
    if date is None:
        date = datetime.datetime.now().strftime("%Y-%m-%d")
    
    query = '''
    SELECT image_path, date, time 
    FROM unknown_faces 
    WHERE date = ? 
    ORDER BY time
    '''
    
    df = pd.read_sql_query(query, conn, params=(date,))
    conn.close()
    return df

def get_known_face_images():
    conn = sqlite3.connect('data/attendance.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM students ORDER BY name")
    student_names = cursor.fetchall()
    
    known_face_data = []
    known_faces_dir = 'data/known_faces'
    
    for (name,) in student_names:
        matching_files = [f for f in os.listdir(known_faces_dir) if f.startswith(name + "_")]
        
        if matching_files:
            latest_file = sorted(matching_files, reverse=True)[0]
            image_path = os.path.join(known_faces_dir, latest_file)
            known_face_data.append({'name': name, 'image_path': image_path})
            
    conn.close()
    return pd.DataFrame(known_face_data)

def delete_student(student_id):
    conn = sqlite3.connect('data/attendance.db')
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM attendance WHERE student_id = ?", (student_id,))
    cursor.execute("DELETE FROM students WHERE id = ?", (student_id,))
    
    conn.commit()
    conn.close()

def get_student_list():
    conn = sqlite3.connect('data/attendance.db')
    query = "SELECT id, name, registration_date FROM students ORDER BY name"
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df
