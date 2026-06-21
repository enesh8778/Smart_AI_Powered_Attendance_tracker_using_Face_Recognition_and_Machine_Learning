import smtplib
from email.message import EmailMessage

def send_attendance_report():

    sender_email = "enesh8778@gmail.com"
    app_password = "yahj mhhg cskq ejed"

    receiver_email = "eneshtech@gmail.com"

    msg = EmailMessage()

    msg["Subject"] = "Daily Attendance Report"
    msg["From"] = sender_email
    msg["To"] = receiver_email

    msg.set_content("""
Smart Attendance Tracker

Attendance report attached.

Regards,
Attendance System
""")

    # Attach PDF
    with open(
        "reports/attendance_report.pdf",
        "rb"
    ) as f:

        msg.add_attachment(
            f.read(),
            maintype="application",
            subtype="pdf",
            filename="attendance_report.pdf"
        )

    server = smtplib.SMTP(
        "smtp.gmail.com",
        587
    )

    server.starttls()

    server.login(
        sender_email,
        app_password
    )

    server.send_message(msg)

    server.quit()

    print("Email Sent Successfully")