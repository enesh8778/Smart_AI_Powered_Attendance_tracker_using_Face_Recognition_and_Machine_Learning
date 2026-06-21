import cv2
import mediapipe as mp
import math

mp_face_mesh = mp.solutions.face_mesh


def euclidean_distance(p1, p2):

    return math.sqrt(
        (p1[0] - p2[0]) ** 2 +
        (p1[1] - p2[1]) ** 2
    )


def eye_aspect_ratio(landmarks, eye_points):

    p1 = landmarks[eye_points[0]]
    p2 = landmarks[eye_points[1]]
    p3 = landmarks[eye_points[2]]
    p4 = landmarks[eye_points[3]]
    p5 = landmarks[eye_points[4]]
    p6 = landmarks[eye_points[5]]

    vertical_1 = euclidean_distance(p2, p6)
    vertical_2 = euclidean_distance(p3, p5)

    horizontal = euclidean_distance(p1, p4)

    ear = (
        vertical_1 + vertical_2
    ) / (2.0 * horizontal)

    return ear


def verify_liveness():

    LEFT_EYE = [33, 160, 158, 133, 153, 144]
    RIGHT_EYE = [362, 385, 387, 263, 373, 380]

    cap = cv2.VideoCapture(0)

    blink_count = 0
    blink_detected = False

    with mp_face_mesh.FaceMesh(
        static_image_mode=False,
        max_num_faces=1,
        refine_landmarks=True
    ) as face_mesh:

        while True:

            success, frame = cap.read()

            if not success:
                break

            rgb = cv2.cvtColor(
                frame,
                cv2.COLOR_BGR2RGB
            )

            results = face_mesh.process(rgb)

            if results.multi_face_landmarks:

                for face_landmarks in results.multi_face_landmarks:

                    h, w, _ = frame.shape

                    landmarks = []

                    for lm in face_landmarks.landmark:

                        x = int(lm.x * w)
                        y = int(lm.y * h)

                        landmarks.append((x, y))

                    left_ear = eye_aspect_ratio(
                        landmarks,
                        LEFT_EYE
                    )

                    right_ear = eye_aspect_ratio(
                        landmarks,
                        RIGHT_EYE
                    )

                    avg_ear = (
                        left_ear + right_ear
                    ) / 2

                    cv2.putText(
                        frame,
                        "Blink Once",
                        (20, 40),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        1,
                        (0, 255, 0),
                        2
                    )

                    if avg_ear < 0.20:

                        blink_count += 1

                    if blink_count > 2:

                        blink_detected = True

                        cv2.putText(
                            frame,
                            "Liveness Verified",
                            (20, 80),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            1,
                            (0, 255, 0),
                            2
                        )

                        cap.release()
                        cv2.destroyAllWindows()

                        return True

            cv2.imshow(
                "Liveness Detection",
                frame
            )

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    cap.release()
    cv2.destroyAllWindows()

    return False