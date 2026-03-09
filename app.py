import streamlit as st
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, date, time
from fpdf import FPDF
import hashlib
import smtplib
import joblib
import numpy as np

# ---------------- LOAD ML MODEL ----------------
model = joblib.load("disease_model.pkl")

DB_FILE = "hospital.db"

# ---------------- PASSWORD HASH ----------------
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# ---------------- DATABASE CONNECTION ----------------
def create_connection():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    return conn

# ---------------- CREATE TABLES ----------------
def create_tables(db):
    cursor = db.cursor()

    # USERS
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        password TEXT
    )
    """)

    # default admin
    cursor.execute("""
    INSERT INTO users (username,password)
    SELECT 'admin', ? WHERE NOT EXISTS (
        SELECT 1 FROM users WHERE username='admin'
    )
    """, (hash_password("admin123"),))

    # DOCTORS
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS doctors(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        specialization TEXT,
        fee INTEGER,
        start_time TEXT,
        end_time TEXT
    )
    """)

    # PATIENTS
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS patients(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        age INTEGER,
        contact TEXT,
        email TEXT,
        address TEXT,
        cnic TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # APPOINTMENTS
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS appointments(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER,
        doctor_id INTEGER,
        appointment_date TEXT,
        appointment_time TEXT,
        notes TEXT,
        status TEXT,
        FOREIGN KEY(patient_id) REFERENCES patients(id) ON DELETE CASCADE,
        FOREIGN KEY(doctor_id) REFERENCES doctors(id) ON DELETE CASCADE
    )
    """)

    # ACTION LOGS
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS logs(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        action TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    db.commit()

# ---------------- LOGIN ----------------
def login(db, user, password):
    cursor = db.cursor()
    hashed = hash_password(password)
    cursor.execute(
        "SELECT * FROM users WHERE username=? AND password=?",
        (user, hashed)
    )
    return cursor.fetchone()

# ---------------- LOGGING ----------------
def add_log(db, action):
    cursor = db.cursor()
    cursor.execute("INSERT INTO logs(action) VALUES (?)", (action,))
    db.commit()

def get_logs(db):
    cursor = db.cursor()
    cursor.execute("SELECT * FROM logs ORDER BY created_at DESC")
    return cursor.fetchall()

# ---------------- DOCTOR MANAGEMENT ----------------
def add_doctor(db, name, spec, fee, start, end):
    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO doctors(name, specialization, fee, start_time, end_time)
        VALUES (?, ?, ?, ?, ?)
    """, (name, spec, fee, start, end))
    db.commit()
    add_log(db, f"Doctor added: {name}")

def get_doctors(db):
    cursor = db.cursor()
    cursor.execute("SELECT * FROM doctors")
    return cursor.fetchall()

# ---------------- PATIENT MANAGEMENT ----------------
def add_patient(db, name, age, contact, email, address, cnic):
    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO patients(name, age, contact, email, address, cnic)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (name, age, contact, email, address, cnic))
    db.commit()
    add_log(db, f"Patient added: {name}")

def get_patients(db):
    cursor = db.cursor()
    cursor.execute("SELECT * FROM patients")
    return cursor.fetchall()

# ---------------- APPOINTMENT ----------------
def create_appointment(db, pid, did, adate, atime, notes):
    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO appointments(patient_id, doctor_id, appointment_date, appointment_time, notes, status)
        VALUES (?, ?, ?, ?, ?, 'Scheduled')
    """, (pid, did, adate, atime, notes))
    db.commit()
    add_log(db, f"Appointment created for patient_id {pid} with doctor_id {did} on {adate}")

def get_appointments(db):
    cursor = db.cursor()
    cursor.execute("""
        SELECT a.id, p.name, d.name, a.appointment_date, a.appointment_time, a.status
        FROM appointments a
        JOIN patients p ON a.patient_id = p.id
        JOIN doctors d ON a.doctor_id = d.id
    """)
    return cursor.fetchall()

# ---------------- UPDATE APPOINTMENT STATUS ----------------
def update_appointment_status(db, aid, status):
    cursor = db.cursor()
    cursor.execute("UPDATE appointments SET status=? WHERE id=?", (status, aid))
    db.commit()
    add_log(db, f"Appointment {aid} status updated to {status}")

# ---------------- DASHBOARD ----------------
def dashboard(db):
    cursor = db.cursor()
    cursor.execute("SELECT COUNT(*) FROM patients")
    p = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM appointments")
    a = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM doctors")
    d = cursor.fetchone()[0]

    st.subheader("Hospital Analytics")
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Patients", p)
    col2.metric("Total Appointments", a)
    col3.metric("Total Doctors", d)

    # Graph
    data = {"Patients": p, "Appointments": a, "Doctors": d}
    fig, ax = plt.subplots()
    ax.bar(data.keys(), data.values(), color=["#00e5ff","#ff5733","#33ff57"])
    st.pyplot(fig)

    # Latest logs
    st.subheader("Recent Actions")
    logs = get_logs(db)
    if logs:
        df_logs = pd.DataFrame(logs, columns=["ID", "Action", "Timestamp"])
        st.dataframe(df_logs.head(10))
    else:
        st.info("No actions logged yet.")

# ---------------- PDF REPORT ----------------
def generate_pdf(data, title="Patient Report"):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, txt=title, ln=True, align='C')
    pdf.set_font("Arial", size=12)
    pdf.ln(5)
    for row in data:
        pdf.cell(0, 10, txt=f"ID: {row[0]} | Name: {row[1]} | Age: {row[2]} | Contact: {row[3]} | Email: {row[4]}", ln=True)
    pdf.output("report.pdf")

# ---------------- EMAIL REMINDER ----------------
def send_email(receiver, msg):
    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login("ghoshmoon19@gmail.com", "Soumya123@Roy")
        server.sendmail("ghoshmoon19@gmail.com", receiver, msg)
        server.quit()
        return True
    except:
        return False

# ---------------- AI PREDICTION ----------------
def predict_patient_risk(age):
    if age > 60:
        return "High Risk"
    if age > 40:
        return "Medium Risk"
    return "Low Risk"

# ---------------- ML DISEASE PREDICTION ----------------
def predict_disease(age, bp, sugar):
    data = np.array([[age, bp, sugar]])
    prediction = model.predict(data)
    if prediction[0] == 1:
        return "⚠ High Risk of Diabetes"
    return "✅ Low Risk"

# ---------------- MAIN APP ----------------
def main():
    df = None

    st.set_page_config(page_title="AI Hospital Management System",
                       page_icon="🏥", layout="wide")

    st.markdown("""
    <style>
    .stApp {background-color: #0e1117; color: white;}
    h1,h2,h3,h4,h5,h6 {color:#00e5ff;}
    .stButton>button {background:#00e5ff;color:black;border-radius:10px;}
    </style>
    """, unsafe_allow_html=True)

    st.image(
        "https://img.freepik.com/free-vector/flat-design-healthcare-banner-template_23-2149611192.jpg",
        use_container_width=True
    )

    st.title("🏥 AI Powered Hospital Management System")
    st.markdown("---")

    db = create_connection()
    create_tables(db)

    if "login" not in st.session_state:
        st.session_state.login = False

    if not st.session_state.login:
        st.subheader("Login")
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.button("Login"):
            auth = login(db, u, p)
            if auth:
                st.session_state.login = True
                st.success("Login Success")
                st.rerun()
            else:
                st.error("Invalid Credentials")
        return

    menu = st.sidebar.selectbox("Menu", [
        "Dashboard", "Add Doctor", "Add Patient", "View Patients",
        "Create Appointment", "Appointments", "Disease Prediction", "Generate PDF"
    ])

    st.sidebar.markdown("---")
    if st.sidebar.button("Logout"):
        st.session_state.login = False
        st.rerun()

    # ---------------- MENU HANDLERS ----------------
    if menu == "Dashboard":
        dashboard(db)

    elif menu == "Add Doctor":
        name = st.text_input("Doctor Name")
        spec = st.text_input("Specialization")
        fee = st.number_input("Fee")
        start = st.time_input("Start Time")
        end = st.time_input("End Time")
        if st.button("Add"):
            add_doctor(db, name, spec, fee, start.strftime("%H:%M:%S"), end.strftime("%H:%M:%S"))
            st.success("Doctor Added Successfully")

    elif menu == "Add Patient":
        name = st.text_input("Name")
        age = st.number_input("Age")
        contact = st.text_input("Contact")
        email = st.text_input("Email")
        address = st.text_input("Address")
        cnic = st.text_input("CNIC")
        if st.button("Save"):
            add_patient(db, name, age, contact, email, address, cnic)
            risk = predict_patient_risk(age)
            st.success(f"Patient Added | Risk Level: {risk}")

    elif menu == "View Patients":
        data = get_patients(db)
        df = pd.DataFrame(data, columns=["ID","Name","Age","Contact","Email","Address","CNIC","Created At"])
        st.subheader("All Patients")
        st.dataframe(df)
        st.markdown("### Search Patients")
        search_name = st.text_input("Enter patient name to search")
        if search_name:
            filtered = df[df["Name"].str.contains(search_name, case=False)]
            st.dataframe(filtered)

    elif menu == "Create Appointment":
        patients = get_patients(db)
        doctors = get_doctors(db)

        if not patients:
            st.warning("No patients available. Please add patients first.")
        elif not doctors:
            st.warning("No doctors available. Please add doctors first.")
        else:
            patient_dict = {p[1]: p[0] for p in patients}
            doctor_dict = {d[1]: d[0] for d in doctors}

            selected_patient = st.selectbox("Patient", list(patient_dict.keys()))
            pid = patient_dict.get(selected_patient)

            selected_doctor = st.selectbox("Doctor", list(doctor_dict.keys()))
            did = doctor_dict.get(selected_doctor)

            adate = st.date_input("Date")
            atime = st.time_input("Time")
            notes = st.text_area("Notes")
            if st.button("Create"):
                create_appointment(db, pid, did, adate.strftime("%Y-%m-%d"), atime.strftime("%H:%M:%S"), notes)
                st.success("Appointment Created")

    elif menu == "Appointments":
        data = get_appointments(db)
        df = pd.DataFrame(data, columns=["ID", "Patient", "Doctor", "Date", "Time", "Status"])
        st.subheader("All Appointments")
        st.dataframe(df)
        st.markdown("### Filter Appointments")
        status_filter = st.selectbox("Filter by Status", ["All", "Scheduled", "Completed", "Cancelled"])
        if status_filter != "All":
            df_filtered = df[df["Status"]==status_filter]
            st.dataframe(df_filtered)

        st.subheader("Update Appointment Status")
        if not df.empty:
            aid = st.selectbox("Select Appointment ID", df["ID"].tolist())
            status = st.selectbox("Status", ["Scheduled", "Completed", "Cancelled"])
            if st.button("Update Status"):
                update_appointment_status(db, aid, status)
                st.success("Status Updated")
        else:
            st.info("No appointments available.")

    elif menu == "Disease Prediction":
        st.subheader("AI Disease Prediction System")
        age = st.number_input("Age")
        bp = st.number_input("Blood Pressure")
        sugar = st.number_input("Sugar Level")
        if st.button("Predict Disease"):
            result = predict_disease(age, bp, sugar)
            st.success(result)

    elif menu == "Generate PDF":
        data = get_patients(db)
        if st.button("Generate Report"):
            generate_pdf(data)
            st.success("PDF Generated")

# ---------------- RUN ----------------
if __name__ == "__main__":
    main()
