import sys
import os

BASE_DIR = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

sys.path.append(BASE_DIR)

import cv2
import face_recognition
import mysql.connector
import numpy as np
import csv

from liveness_detector import verify_liveness
from datetime import datetime, time
from config import DB_CONFIG

# -----------------------------
# Database Connection
# -----------------------------
def get_connection():
    return mysql.connector.connect(**DB_CONFIG)


# -----------------------------
# Get Students
# -----------------------------
def get_students():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, name, image_path
        FROM students
    """)

    students = cursor.fetchall()
    conn.close()

    return students


# -----------------------------
# Load Student Encodings
# -----------------------------
known_face_encodings = []
known_face_names = []
known_student_ids = []

students = get_students()

BASE_DIR = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

for student in students:

    student_id = student[0]
    student_name = student[1]
    image_path = student[2]

    full_path = os.path.join(BASE_DIR, image_path)

    image = face_recognition.load_image_file(full_path)
    encoding = face_recognition.face_encodings(image)[0]

    known_face_encodings.append(encoding)
    known_face_names.append(student_name)
    known_student_ids.append(student_id)


print("Encodings Loaded Successfully")


# -----------------------------
# CSV Setup
# -----------------------------
today = datetime.now().strftime("%Y-%m-%d")

csv_file = open(f"attendance_{today}.csv", "w", newline="")
writer = csv.writer(csv_file)

writer.writerow(["Student ID", "Name", "Time", "Status"])


# -----------------------------
# Settings
# -----------------------------
CLASS_START = time(9, 30)
marked_students = set()

video = cv2.VideoCapture(0)


# -----------------------------
# Main Loop
# -----------------------------
while True:

    ret, frame = video.read()

    if not ret:
        break

    small_frame = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
    rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

    face_locations = face_recognition.face_locations(rgb_small_frame)
    face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)

    for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):

        matches = face_recognition.compare_faces(known_face_encodings, face_encoding)
        face_distances = face_recognition.face_distance(known_face_encodings, face_encoding)

        name = "Unknown"
        student_id = None

        best_match_index = np.argmin(face_distances)

        if matches[best_match_index]:
            name = known_face_names[best_match_index]
            student_id = known_student_ids[best_match_index]

        current_time = datetime.now().time()

        if current_time > CLASS_START:
            status = "Late"
        else:
            status = "Present"


        # -----------------------------
        # Attendance Marking + Liveness
        # -----------------------------
        if student_id is not None:

            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT id
                FROM attendance
                WHERE student_id=%s
                AND attendance_date=%s
            """,
            (
                student_id,
                datetime.now().date()
            ))

            already_marked = cursor.fetchone()

            if already_marked:

                print(f"{name} already present today")

                cv2.putText(
                    frame,
                    f"{name} - Already Present",
                    (50, 50),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,
                    (0, 0, 255),
                    2
                )

            else:

                if verify_liveness():

                    cursor.execute("""
                        INSERT INTO attendance
                        (
                            student_id,
                            attendance_date,
                            attendance_time,
                            attendance_status
                        )
                        VALUES(%s,%s,%s,%s)
                    """,
                    (
                        student_id,
                        datetime.now().date(),
                        datetime.now().time(),
                        status
                    ))

                    conn.commit()

                    writer.writerow([
                        student_id,
                        name,
                        datetime.now().strftime("%H:%M:%S"),
                        status
                    ])

                    print(
                        f"{name} marked {status}"
                    )

            conn.close()

            # Liveness Check
            if verify_liveness():

                marked_students.add(student_id)

                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute("""
                    INSERT INTO attendance
                    (student_id, attendance_date, attendance_time, attendance_status)
                    VALUES (%s, %s, %s, %s)
                """,
                (
                    student_id,
                    datetime.now().date(),
                    datetime.now().time(),
                    status
                ))

                conn.commit()
                conn.close()

                writer.writerow([
                    student_id,
                    name,
                    datetime.now().strftime("%H:%M:%S"),
                    status
                ])

                print(f"{name} marked {status}")


        # -----------------------------
        # Unknown Face Detection
        # -----------------------------
        if name == "Unknown":

            os.makedirs(
            "unknown_faces",
            exist_ok=True
        )

        filename = os.path.join(
            "unknown_faces",
            f"unknown_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        )

        cv2.imwrite(
            filename,
            frame
        )

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO unknown_faces
            (
                image_path,
                detected_date,
                detected_time
            )
            VALUES(%s,%s,%s)
        """,
        (
            filename,
            datetime.now().date(),
            datetime.now().time()
        ))

        conn.commit()
        conn.close()

        print("Unknown person detected")


        # -----------------------------
        # Draw Box
        # -----------------------------
        top *= 2
        right *= 2
        bottom *= 2
        left *= 2

        cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)

        cv2.putText(
            frame,
            name,
            (left, bottom + 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 255, 255),
            2
        )
        if student_id is not None and already_marked:

            cv2.putText(
                frame,
                "Already Present",
                (left, top - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 0, 255),
                2
            )


    # -----------------------------
    # Show Frame
    # -----------------------------
    cv2.imshow("Attendance System", frame)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break


# -----------------------------
# Cleanup
# -----------------------------
csv_file.close()
video.release()
cv2.destroyAllWindows()