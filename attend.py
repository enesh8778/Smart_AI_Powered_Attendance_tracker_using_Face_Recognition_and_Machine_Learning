import face_recognition
import cv2
import numpy as np
import csv
from datetime import datetime

webcam = cv2.VideoCapture(0)

enesh_image = face_recognition.load_image_file( r"C:\Users\Enesh\Desktop\CV_projects\Attendance_tracket\images\enesh.jpeg")
enesh_encoding = face_recognition.face_encodings(enesh_image)[0]

vasanth_image = face_recognition.load_image_file(r"C:\Users\Enesh\Desktop\CV_projects\Attendance_tracket\images\vasanth.jpeg")
vasanth_encoding = face_recognition.face_encodings(vasanth_image)[0]

rupika_image = face_recognition.load_image_file( r"C:\Users\Enesh\Desktop\CV_projects\Attendance_tracket\images\rupika.jpeg")
rupika_encoding = face_recognition.face_encodings(rupika_image)[0]

balachandar_image = face_recognition.load_image_file( r"C:\Users\Enesh\Desktop\CV_projects\Attendance_tracket\images\balachandar.jpeg")
balachandar_encoding = face_recognition.face_encodings(balachandar_image)[0]


known_face_encodings = [
    enesh_encoding,
    vasanth_encoding,
    rupika_encoding,
    balachandar_encoding
]

known_face_names = [
    "Enesh",
    "Vasanth",
    "Rupika",
    "Balachandar"
]


students = known_face_names.copy()

now = datetime.now()
current_date = now.strftime("%Y-%m-%d")

csvf = open(f"{current_date}.csv", "w", newline="")
lnwriter = csv.writer(csvf)

lnwriter.writerow(["Name", "Time"])

print(f"Attendance sheet created: {current_date}.csv")

while True:

    success, frame = webcam.read()

    if not success:
        print("Could not access webcam")
        break

    small_frame = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)

    rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
    face_locations = face_recognition.face_locations(rgb_small_frame, model="hog")

    face_encodings = face_recognition.face_encodings(rgb_small_frame,face_locations )

    face_names = []

    for face_encoding in face_encodings:

        matches = face_recognition.compare_faces(known_face_encodings,face_encoding)

        name = "Unknown"

        face_distances = face_recognition.face_distance(
            known_face_encodings,
            face_encoding
        )

        best_match_index = np.argmin(face_distances)

        if matches[best_match_index]:
            name = known_face_names[best_match_index]

        face_names.append(name)

        if name != "Unknown" and name in students:
            students.remove(name)
            current_time = datetime.now().strftime("%H:%M:%S")
            lnwriter.writerow([name, current_time])
            print(f"{name} marked present at {current_time}")


    for (top, right, bottom, left), name in zip(face_locations,face_names):
        top *= 2
        right *= 2
        bottom *= 2
        left *= 2

        cv2.rectangle(
            frame,
            (left, top),
            (right, bottom),
            (0, 255, 0),
            2
        )
        cv2.rectangle(
            frame,
            (left, bottom - 35),
            (right, bottom),
            (0, 255, 0),
            cv2.FILLED
        )
        cv2.putText(
            frame,
            name,
            (left + 6, bottom - 6),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 255, 255),
            2
        )
    cv2.imshow("Attendance Tracker", frame)

    if cv2.waitKey(1) & 0xFF == ord("a"):
        break

webcam.release()
cv2.destroyAllWindows()
csvf.close()

print("Attendance saved successfully.")