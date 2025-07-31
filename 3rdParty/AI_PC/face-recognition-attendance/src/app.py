#===--app.py----------------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//
import streamlit as st
import cv2
import numpy as np
import pandas as pd
import datetime
import os
import time
from database import init_db, add_student, get_all_students, get_attendance_records, get_unknown_faces, delete_student, get_student_list, get_known_face_images
from face_recognition import FaceRecognitionSystem
from utils import load_image_from_upload, save_uploaded_image, get_image_from_path
from PIL import Image

# Initialize the database
init_db()

# Set page config
st.set_page_config(page_title="Face Recognition Attendance System", layout="wide")

# Initialize session state variables
if 'face_recognition_system' not in st.session_state:
    # Load known faces from database
    students = get_all_students()
    known_face_embeddings = [student[2] for student in students]
    known_face_names = [student[1] for student in students]
    known_face_ids = [student[0] for student in students]
    
    st.session_state.face_recognition_system = FaceRecognitionSystem(
        known_face_embeddings, known_face_names, known_face_ids
    )

if 'camera_running' not in st.session_state:
    st.session_state.camera_running = False

if 'current_page' not in st.session_state:
    st.session_state.current_page = "Home"

# Main navigation buttons at the top (acting as a menu bar)
st.title("Face Recognition Attendance System")
st.write("Welcome to the Face Recognition Attendance System.")

col1, col2, col3, col4 = st.columns(4)

with col1:
    if st.button("Home", use_container_width=True):
        st.session_state.current_page = "Home"
with col2:
    if st.button("Attendance System", use_container_width=True):
        st.session_state.current_page = "Attendance System"
with col3:
    if st.button("Manage Faces", use_container_width=True):
        st.session_state.current_page = "Manage Faces"
with col4:
    if st.button("View Records", use_container_width=True):
        st.session_state.current_page = "View Records"

st.markdown("---") # Separator below the navigation

# Content for each page
if st.session_state.current_page == "Home":
    st.subheader("System Features:")
    st.write("1. Real-time face recognition for attendance tracking")
    st.write("2. Management of known faces")
    st.write("3. Recording of unknown faces")
    st.write("4. Attendance records viewing and export")
    
    st.image("https://img.freepik.com/free-vector/face-recognition-concept-illustration_114360-7941.jpg", 
             caption="Face Recognition Illustration", use_column_width=True)

elif st.session_state.current_page == "Attendance System":
    st.title("Attendance System")
    
    # Camera feed for attendance
    start_camera = st.button("Start Camera")
    stop_camera = st.button("Stop Camera")
    
    if start_camera:
        st.session_state.camera_running = True
    
    if stop_camera:
        st.session_state.camera_running = False
    
    # Display camera feed
    if st.session_state.camera_running:
        # Reload known faces from database to ensure we have the latest data
        students = get_all_students()
        known_face_embeddings = [student[2] for student in students]
        known_face_names = [student[1] for student in students]
        known_face_ids = [student[0] for student in students]
        
        st.session_state.face_recognition_system.update_known_faces(
            known_face_embeddings, known_face_names, known_face_ids
        )
        
        stframe = st.empty()
        video_capture = cv2.VideoCapture(0)
        
        # Check if camera opened successfully
        if not video_capture.isOpened():
            st.error("Could not open webcam. Please check your camera connection.")
        else:
            try:
                while st.session_state.camera_running:
                    # Capture frame-by-frame
                    ret, frame = video_capture.read()
                    
                    if not ret:
                        st.error("Failed to capture image from camera.")
                        break
                    
                    # Process the frame for face recognition
                    processed_frame = st.session_state.face_recognition_system.process_frame(frame)
                    
                    # Display the resulting frame
                    stframe.image(processed_frame, channels="BGR", use_column_width=True)
                    
                    # Add a small delay to reduce CPU usage
                    time.sleep(0.1)
            finally:
                video_capture.release()
    
    # Display today's attendance
    st.subheader("Today's Attendance")
    attendance_df = get_attendance_records()
    st.dataframe(attendance_df)

elif st.session_state.current_page == "Manage Faces":
    st.title("Manage Faces")
    
    # Add new face
    st.subheader("Add New Face")
    
    person_name = st.text_input("Enter Person's Name")
    uploaded_file = st.file_uploader("Upload a clear face image", type=["jpg", "jpeg", "png"])
    
    if uploaded_file is not None:
        # Display the uploaded image
        image = load_image_from_upload(uploaded_file)
        st.image(image, caption="Uploaded Image", use_column_width=True, channels="BGR")
        
        # Process the image to detect and encode face
        face_embedding, result_image = st.session_state.face_recognition_system.encode_face(image)
        
        if face_embedding is not None:
            st.image(result_image, caption="Face Detected", use_column_width=True, channels="BGR")
            
            if st.button("Add to Database") and person_name:
                # Save image and add to database
                file_path = save_uploaded_image(uploaded_file, person_name)
                st.success(f"Image saved to: {file_path}")
                student_id = add_student(person_name, face_embedding)
                
                # Update the face recognition system with the new face
                students = get_all_students()
                known_face_embeddings = [student[2] for student in students]
                known_face_names = [student[1] for student in students]
                known_face_ids = [student[0] for student in students]
                
                st.session_state.face_recognition_system.update_known_faces(
                    known_face_embeddings, known_face_names, known_face_ids
                )
                
                st.success(f"Added {person_name} to the database!")
        else:
            st.error(result_image)  # Display error message

elif st.session_state.current_page == "View Records":
    st.title("View Records")
    
    # Date selection for attendance records
    selected_date = st.date_input("Select Date", datetime.datetime.now())
    date_str = selected_date.strftime("%Y-%m-%d")
    
    # Display attendance records
    st.subheader(f"Attendance Records for {date_str}")
    attendance_df = get_attendance_records(date_str)
    
    if not attendance_df.empty:
        st.dataframe(attendance_df)
        
        # Export to CSV
        csv = attendance_df.to_csv(index=False)
        st.download_button(
            label="Download Attendance as CSV",
            data=csv,
            file_name=f"attendance_{date_str}.csv",
            mime="text/csv"
        )
    else:
        st.info(f"No attendance records for {date_str}")
    
    st.markdown("---")

    # Display known faces with attendance for the selected date
    st.subheader(f"Known Faces Recorded for {date_str}")
    
    # Get attendance records for the selected date
    attended_students_df = attendance_df[['name', 'time']].drop_duplicates() # Only get unique name and time for display
    
    if not attended_students_df.empty:
        st.write("Below are the images of recorded known faces for this date:")
        cols = st.columns(3)
        
        # Get all registered students to find their image paths
        all_students = get_all_students()
        student_name_to_id = {student[1]: student[0] for student in all_students}

        # Iterate through attended students and find their images
        for i, (_, row) in enumerate(attended_students_df.iterrows()):
            student_name = row['name']
            attendance_time = row['time']

            # Find the image path for this student
            known_faces_dir = 'data/known_faces'
            matching_files = [f for f in os.listdir(known_faces_dir) if f.startswith(student_name + "_")]
            
            image_path = None
            if matching_files:
                # Assuming the latest image is relevant or just pick the first one found
                latest_file = sorted(matching_files, reverse=True)[0]
                image_path = os.path.join(known_faces_dir, latest_file)
            
            if image_path:
                try:
                    image = get_image_from_path(image_path)
                    if image is not None:
                        cols[i % 3].image(image, caption=f"Name: {student_name}\nTime: {attendance_time}", use_column_width=True, channels="BGR")
                    else:
                        cols[i % 3].error(f"Error loading image for {student_name} at {image_path}")
                except Exception as e:
                    cols[i % 3].error(f"Error loading image for {student_name}: {e}")
            else:
                cols[i % 3].info(f"No image found for {student_name}")
    else:
        st.info(f"No known faces recorded for {date_str}")

    st.markdown("---")

    # Display unknown faces table (without images)
    st.subheader(f"Unknown Faces for {date_str}")
    unknown_faces_df = get_unknown_faces(date_str)
    
    if not unknown_faces_df.empty:
        st.dataframe(unknown_faces_df)
    else:
        st.info(f"No unknown faces recorded for {date_str}")
