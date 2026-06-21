from flask import Flask, render_template, request, redirect, session, send_from_directory
from werkzeug.utils import secure_filename
import mysql.connector
import os
from config import DB_CONFIG
import plotly.express as px
import pandas as pd
from flask import send_file
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer
)
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from email_service.email_sender import send_attendance_report
import joblib
from datetime import datetime

app = Flask(__name__)
app.secret_key = "attendance_secret_key"

UPLOAD_FOLDER = "uploads/students"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ---------------- DB CONNECTION ----------------
def get_connection():
    return mysql.connector.connect(**DB_CONFIG)


# ---------------- HOME (FIX FOR "NOT FOUND") ----------------
@app.route("/")
def home():
    if "user" in session:
        return redirect("/dashboard")
    return redirect("/login_page")


# ---------------- LOGIN PAGE ----------------
@app.route("/login_page")
def login_page():
    return render_template("login.html")


# ---------------- LOGIN ----------------
@app.route("/login", methods=["POST"])
def login():

    username = request.form["username"]
    password = request.form["password"]

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM faculty
        WHERE username=%s AND password=%s
    """, (username, password))

    user = cursor.fetchone()
    conn.close()

    if user:
        session["user"] = username
        return redirect("/dashboard")

    return "Invalid Login Credentials"


# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
def dashboard():

    if "user" not in session:
        return redirect("/")

    conn = get_connection()
    cursor = conn.cursor()

    # Total Students
    cursor.execute("SELECT COUNT(*) FROM students")
    total_students = cursor.fetchone()[0]

    # Present
    cursor.execute("""
    SELECT COUNT(*)
    FROM attendance
    WHERE attendance_status='Present'
    AND attendance_date = CURDATE()
""")
    present = cursor.fetchone()[0]

    # Late
    cursor.execute("""
    SELECT COUNT(*)
    FROM attendance
    WHERE attendance_status='Late'
    AND attendance_date = CURDATE()
""")
    late = cursor.fetchone()[0]

    absent = total_students - (present + late)

    # Student Attendance List
    cursor.execute("""
        SELECT
            s.name,
            s.roll_no,
            s.department,
            COALESCE(a.attendance_status,'Absent')
        FROM students s
        LEFT JOIN attendance a
        ON s.id = a.student_id
        AND a.attendance_date = CURDATE()
    """)

    student_list = cursor.fetchall()

    conn.close()

    return render_template(
        "dashboard.html",
        total_students=total_students,
        present=present,
        late=late,
        absent=absent,
        student_list=student_list
    )
# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# ---------------- STUDENTS PAGE ----------------
@app.route("/students")
def students():

    if "user" not in session:
        return redirect("/")

    search = request.args.get("search", "")

    conn = get_connection()
    cursor = conn.cursor()

    if search:

        cursor.execute("""
            SELECT *
            FROM students
            WHERE name LIKE %s
            OR roll_no LIKE %s
            OR department LIKE %s
        """,
        (
            f"%{search}%",
            f"%{search}%",
            f"%{search}%"
        ))

    else:

        cursor.execute("""
            SELECT *
            FROM students
        """)

    data = cursor.fetchall()

    conn.close()

    return render_template(
        "students.html",
        students=data
    )

# ---------------- ADD STUDENT ----------------
@app.route("/add_student", methods=["POST"])
def add_student():

    name = request.form["name"]
    roll_no = request.form["roll_no"]
    department = request.form["department"]

    photo = request.files["photo"]
    filename = secure_filename(photo.filename)

    photo_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    photo.save(photo_path)

    image_path = f"uploads/students/{filename}"

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO students (name, roll_no, department, image_path)
        VALUES (%s,%s,%s,%s)
    """, (name, roll_no, department, image_path))

    conn.commit()
    conn.close()

    return redirect("/students")


# ---------------- DELETE STUDENT ----------------
@app.route("/delete_student/<int:id>")
def delete_student(id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM students WHERE id=%s", (id,))

    conn.commit()
    conn.close()

    return redirect("/students")


# ---------------- EDIT STUDENT ----------------
@app.route("/edit_student/<int:id>")
def edit_student(id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM students WHERE id=%s", (id,))
    student = cursor.fetchone()

    conn.close()

    return render_template("edit_student.html", student=student)


# ---------------- UPDATE STUDENT ----------------
@app.route("/update_student/<int:id>", methods=["POST"])
def update_student(id):

    name = request.form["name"]
    roll_no = request.form["roll_no"]
    department = request.form["department"]

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE students
        SET name=%s, roll_no=%s, department=%s
        WHERE id=%s
    """, (name, roll_no, department, id))

    conn.commit()
    conn.close()

    return redirect("/students")


# ---------------- IMAGE SERVING ----------------
@app.route('/uploads/students/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


# ---------------- STUDENT ANALYTICS ----------------
@app.route("/student_analytics")
def student_analytics():

    if "user" not in session:
        return redirect("/")

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT s.name, a.attendance_status
        FROM attendance a
        JOIN students s ON s.id = a.student_id
    """)

    data = cursor.fetchall()
    conn.close()

    # SAFE CHECK (important fix)
    if not data:
        return "No attendance data found"

    df = pd.DataFrame(data, columns=["name", "status"])

    summary = df.groupby(["name", "status"]).size().reset_index(name="count")

    pivot = summary.pivot(index="name", columns="status", values="count").fillna(0)

    pivot["Total"] = pivot.sum(axis=1)

    pivot["Attendance %"] = (pivot.get("Present", 0) / pivot["Total"]) * 100

    pivot = pivot.reset_index()

    pivot = pivot.sort_values(by="Attendance %", ascending=False)

    fig = px.bar(
        pivot,
        x="name",
        y="Attendance %",
        title="Student Performance Ranking",
        color="Attendance %"
    )

    graph_html = fig.to_html(full_html=False)

    return render_template(
        "student_analytics.html",
        graph_html=graph_html,
        table_data=pivot.to_dict(orient="records")
    )

@app.route("/analytics")
def analytics():

    if "user" not in session:
        return redirect("/")

    conn = get_connection()

    # ---------------- DAILY ----------------
    daily_query = """
    SELECT attendance_date,
           COUNT(*) as total
    FROM attendance
    GROUP BY attendance_date
    ORDER BY attendance_date
    """

    daily_df = pd.read_sql(daily_query, conn)

    daily_fig = px.line(
        daily_df,
        x="attendance_date",
        y="total",
        title="Daily Attendance Trend",
        markers=True
    )

    daily_graph = daily_fig.to_html(
        full_html=False
    )

    # ---------------- WEEKLY ----------------
    weekly_query = """
    SELECT WEEK(attendance_date) as week_no,
           COUNT(*) as total
    FROM attendance
    GROUP BY WEEK(attendance_date)
    ORDER BY WEEK(attendance_date)
    """

    weekly_df = pd.read_sql(
        weekly_query,
        conn
    )

    weekly_fig = px.bar(
        weekly_df,
        x="week_no",
        y="total",
        title="Weekly Attendance"
    )

    weekly_graph = weekly_fig.to_html(
        full_html=False
    )

    # ---------------- MONTHLY ----------------
    monthly_query = """
    SELECT MONTH(attendance_date) as month_no,
           COUNT(*) as total
    FROM attendance
    GROUP BY MONTH(attendance_date)
    ORDER BY MONTH(attendance_date)
    """

    monthly_df = pd.read_sql(
        monthly_query,
        conn
    )

    monthly_fig = px.bar(
        monthly_df,
        x="month_no",
        y="total",
        title="Monthly Attendance"
    )

    monthly_graph = monthly_fig.to_html(
        full_html=False
    )

    conn.close()

    return render_template(
        "analytics.html",
        daily_graph=daily_graph,
        weekly_graph=weekly_graph,
        monthly_graph=monthly_graph
    )

@app.route("/download_report")
def download_report():
    

    if "user" not in session:
        return redirect("/")

    os.makedirs("reports", exist_ok=True)

    pdf_path = "reports/attendance_report.pdf"

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT
        s.name,
        s.roll_no,
        a.attendance_date,
        a.attendance_status
    FROM attendance a
    JOIN students s
    ON s.id = a.student_id
    WHERE a.attendance_date = CURDATE()
    ORDER BY a.attendance_time ASC
""")

    data = cursor.fetchall()
    cursor.execute("""
    SELECT COUNT(*)
    FROM attendance
    WHERE attendance_date = CURDATE()
    AND attendance_status='Present'
""")

    present_count = cursor.fetchone()[0]

    cursor.execute("""
    SELECT COUNT(*)
    FROM attendance
    WHERE attendance_date = CURDATE()
    AND attendance_status='Late'
""")

    late_count = cursor.fetchone()[0]

    conn.close()

    doc = SimpleDocTemplate(pdf_path)

    styles = getSampleStyleSheet()

    elements = []
    today = datetime.now().strftime("%d-%m-%Y")
    title = Paragraph(
        f"Smart Attendance System Report - {today}",
        styles["Title"]
    )

    elements.append(title)

    elements.append(Spacer(1, 20))

    summary = Paragraph(
    f"Today's Attendance Summary<br/>"
    f"Present: {present_count}<br/>"
    f"Late: {late_count}",
    styles["Normal"]
)

    elements.append(summary)

    elements.append(Spacer(1, 20))

    table_data = [
        [
            "Name",
            "Roll No",
            "Date",
            "Status"
        ]
    ]

    for row in data:
        table_data.append(list(row))

    table = Table(table_data)

    table.setStyle(
        TableStyle([
            ('BACKGROUND',(0,0),(-1,0),colors.grey),
            ('TEXTCOLOR',(0,0),(-1,0),colors.whitesmoke),
            ('GRID',(0,0),(-1,-1),1,colors.black),
            ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold')
        ])
    )

    elements.append(table)

    doc.build(elements)

    return send_file(
        pdf_path,
        as_attachment=True
    )

@app.route("/send_report")
def send_report():

    send_attendance_report()

    return "Attendance Report Sent"

@app.route("/unknown_faces")
def unknown_faces():

    if "user" not in session:
        return redirect("/")

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM unknown_faces
        ORDER BY id DESC
    """)

    alerts = cursor.fetchall()

    conn.close()

    return render_template(
        "unknown_faces.html",
        alerts=alerts
    )

@app.route("/student/<int:id>")
def student_profile(id):

    if "user" not in session:
        return redirect("/")

    conn = get_connection()
    cursor = conn.cursor()

    # Student Details
    cursor.execute("""
        SELECT *
        FROM students
        WHERE id=%s
    """, (id,))

    student = cursor.fetchone()

    # Present Count
    cursor.execute("""
        SELECT COUNT(*)
        FROM attendance
        WHERE student_id=%s
        AND attendance_status='Present'
    """, (id,))

    present_count = cursor.fetchone()[0]

    # Late Count
    cursor.execute("""
        SELECT COUNT(*)
        FROM attendance
        WHERE student_id=%s
        AND attendance_status='Late'
    """, (id,))

    late_count = cursor.fetchone()[0]

    total_count = present_count + late_count

    attendance_percentage = 0

    if total_count > 0:
        attendance_percentage = round(
            (present_count / total_count) * 100,
            2
        )
    
    pie_fig = px.pie(
    names=["Present", "Late"],
    values=[present_count, late_count],
    title="Attendance Distribution"
    )   

    pie_graph = pie_fig.to_html(
        full_html=False
    )

    # Attendance History
    query = """
    SELECT attendance_date,
           attendance_status
    FROM attendance
    WHERE student_id=%s
    ORDER BY attendance_date
    """

    df = pd.read_sql(
        query,
        conn,
        params=[id]
    )

    graph_html = ""

    if not df.empty:

        df["value"] = 1

        daily_df = df.groupby(
            "attendance_date"
        ).sum().reset_index()

        fig = px.line(
            daily_df,
            x="attendance_date",
            y="value",
            markers=True,
            title=f"{student[1]} Attendance Trend"
        )

        graph_html = fig.to_html(
            full_html=False
        )

    conn.close()

    return render_template(
        "student_profile.html",
        student=student,
        present_count=present_count,
        late_count=late_count,
        total_count=total_count,
        attendance_percentage=attendance_percentage,
        graph_html=graph_html,
        pie_graph=pie_graph
    )

@app.route("/attendance_prediction")
def attendance_prediction():

    if "user" not in session:
        return redirect("/")

    model = joblib.load(
        "prediction/attendance_model.pkl"
    )

    conn = get_connection()

    query = """
    SELECT
        s.name,

        SUM(
            CASE
                WHEN a.attendance_status='Present'
                THEN 1 ELSE 0
            END
        ) AS present_days,

        SUM(
            CASE
                WHEN a.attendance_status='Late'
                THEN 1 ELSE 0
            END
        ) AS late_days,

        COUNT(*) AS total_days

    FROM students s

    LEFT JOIN attendance a
    ON s.id = a.student_id

    GROUP BY s.id
    """

    df = pd.read_sql(query, conn)

    conn.close()

    predictions = []

    for _, row in df.iterrows():

        total = row["total_days"]

        if total == 0:
            percentage = 0
        else:
            percentage = round(
                (
                    row["present_days"]
                    /
                    total
                ) * 100,
                2
            )

        prediction = model.predict(
            [[
                row["present_days"],
                row["late_days"],
                percentage
            ]]
        )[0]

        predictions.append({
            "name": row["name"],
            "present_days": row["present_days"],
            "late_days": row["late_days"],
            "attendance_percentage": percentage,
            "risk": prediction
        })

    return render_template(
        "attendance_prediction.html",
        predictions=predictions
    )
# ---------------- RUN APP ----------------
if __name__ == "__main__":
    app.run(debug=True)