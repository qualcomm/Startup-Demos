#===--face_recognition.py----------------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//
import cv2
import numpy as np
import os
import datetime
import torch
import pyttsx3
import threading
from facenet_pytorch import MTCNN, InceptionResnetV1
from scipy.spatial.distance import cosine
from database import mark_attendance, record_unknown_face

class FaceRecognitionSystem:
    def __init__(self, known_face_embeddings=None, known_face_names=None, known_face_ids=None):
        self.device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')
        
        
        self.mtcnn = MTCNN(
            image_size=160, margin=0, min_face_size=20,
            thresholds=[0.6, 0.7, 0.7], factor=0.709, post_process=True,
            device=self.device
        )
        self.resnet = InceptionResnetV1(pretrained='vggface2').eval().to(self.device)
        
        self.known_face_embeddings = [] if known_face_embeddings is None else known_face_embeddings
        self.known_face_names = [] if known_face_names is None else known_face_names
        self.known_face_ids = [] if known_face_ids is None else known_face_ids
        
        self.unknown_face_count = 0
        self.similarity_threshold = 0.7 
        
        self.last_unknown_face_time = {}
        
        self.last_welcome_time = {}
        
        self.engine = pyttsx3.init()
        self.engine.setProperty('rate', 150)  # Speed of speech
        self.engine.setProperty('volume', 0.9)  # Volume (0.0 to 1.0)
    
    def speak_welcome(self, name):
        """Speak the welcome message in a separate thread to avoid blocking"""
        def speak_thread(name):
            welcome_msg = f"Welcome {name}"
            self.engine.say(welcome_msg)
            self.engine.runAndWait()
        
        threading.Thread(target=speak_thread, args=(name,)).start()
    
    def update_known_faces(self, face_embeddings, face_names, face_ids):
        self.known_face_embeddings = face_embeddings
        self.known_face_names = face_names
        self.known_face_ids = face_ids
    
    def process_frame(self, frame):

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        boxes, _ = self.mtcnn.detect(rgb_frame)
        if boxes is None:
            return frame
        
        face_names = []
        current_time = datetime.datetime.now()
        
        for box in boxes:
            x1, y1, x2, y2 = [int(i) for i in box]
          
            x1 = max(0, x1)
            y1 = max(0, y1)
            x2 = min(frame.shape[1], x2)
            y2 = min(frame.shape[0], y2)
            
            face = rgb_frame[y1:y2, x1:x2]
            
            if face.shape[0] < 20 or face.shape[1] < 20:
                face_names.append("Too Small")
                continue
            
            try:
                face_tensor = self.mtcnn(face)
                if face_tensor is None:
                    face_names.append("No Face")
                    continue
                    
                face_tensor = face_tensor.unsqueeze(0).to(self.device)
                embedding = self.resnet(face_tensor).detach().cpu().numpy()[0]
                
                name = "Unknown"
                student_id = None
                
                if len(self.known_face_embeddings) > 0:
                    similarities = [1 - cosine(embedding, known_emb) for known_emb in self.known_face_embeddings]
                    best_match_idx = np.argmax(similarities)
                    best_match_score = similarities[best_match_idx]
                    
                    if best_match_score > self.similarity_threshold:
                        original_name = self.known_face_names[best_match_idx]
                        student_id = self.known_face_ids[best_match_idx]
                        
                        mark_attendance(student_id)
                        
                        name = f"WELCOME {original_name}"
                        
                        should_welcome = True
                        if student_id in self.last_welcome_time:
                            time_diff = current_time - self.last_welcome_time[student_id]
                           
                            if time_diff.total_seconds() < 10:
                                should_welcome = False
                        
                        if should_welcome:
                         
                            self.last_welcome_time[student_id] = current_time
                          
                            self.speak_welcome(original_name)
                
                if name == "Unknown":
                    
                    face_location_hash = f"{x1}_{y1}_{x2}_{y2}"
                  
                    should_record = True
                    if face_location_hash in self.last_unknown_face_time:
                        time_diff = current_time - self.last_unknown_face_time[face_location_hash]
                       
                        if time_diff.total_seconds() < 60:
                            should_record = False
                    
                    if should_record:
                        
                        self.last_unknown_face_time[face_location_hash] = current_time
                        
                        # Save unknown face
                        timestamp = current_time.strftime("%Y%m%d_%H%M%S")
                        unknown_face_filename = f"unknown_{timestamp}_{self.unknown_face_count}.jpg"
                        self.unknown_face_count += 1
                        
                        # Save the face image
                        face_bgr = frame[y1:y2, x1:x2]
                        unknown_face_path = os.path.join('data/unknown_faces', unknown_face_filename)
                        cv2.imwrite(unknown_face_path, face_bgr)
                        
                        # Record in database
                        record_unknown_face(unknown_face_path)
                
                face_names.append(name)
            except Exception as e:
                print(f"Error processing face: {e}")
                face_names.append("Error")
        
     
        for (x1, y1, x2, y2), name in zip(boxes.astype(int), face_names):
           
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
            
            cv2.rectangle(frame, (x1, y2 - 35), (x2, y2), (0, 0, 255), cv2.FILLED)
            font = cv2.FONT_HERSHEY_DUPLEX
            cv2.putText(frame, name, (x1 + 6, y2 - 6), font, 0.8, (255, 255, 255), 1)
        
        return frame
    
    def encode_face(self, image):
     
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    
        boxes, _ = self.mtcnn.detect(rgb_image)
        
        if boxes is None or len(boxes) == 0:
            return None, "No face detected in the image."
        
        if len(boxes) > 1:
            return None, "Multiple faces detected. Please use an image with only one face."
        
        try:
            
            face_tensor = self.mtcnn(rgb_image)
            if face_tensor is None:
                return None, "Failed to align face. Please try with a clearer image."
                
            
            face_tensor = face_tensor.unsqueeze(0).to(self.device)
            embedding = self.resnet(face_tensor).detach().cpu().numpy()[0]
            
          
            x1, y1, x2, y2 = [int(i) for i in boxes[0]]
            cv2.rectangle(image, (x1, y1), (x2, y2), (0, 255, 0), 2)
            
            return embedding, image
        except Exception as e:
            return None, f"Error processing face: {e}"
