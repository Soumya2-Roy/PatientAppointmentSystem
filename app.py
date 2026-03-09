import streamlit as st
import mysql.connector
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime,date,time
from fpdf import FPDF
import hashlib
import smtplib
import joblib
import numpy as np

# ---------------- LOAD ML MODEL ----------------
model = joblib.load("disease_model.pkl")

# ---------------- DATABASE CONFIG ----------------
config = {
    "host": "localhost",
    "user": "root",
    "password": "Soumya123@Roy",
    "port": 3306
}

DB_NAME = "hospital_ai_system"

# ---------------- PASSWORD HASH ----------------
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# ---------------- DATABASE CONNECTION ----------------
def create_connection():
    return mysql.connector.connect(**config)

def create_database(db):

    cursor = db.cursor()

    cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}")
    cursor.execute(f"USE {DB_NAME}")

# ---------------- FIX DOCTOR TABLE COLUMNS ----------------
def ensure_doctor_time_columns(db):

    cursor = db.cursor()

    cursor.execute(f"USE {DB_NAME}")

    cursor.execute("""
    SELECT COLUMN_NAME
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_NAME='doctors'
    AND TABLE_SCHEMA=%s
    """,(DB_NAME,))

    columns = [c[0] for c in cursor.fetchall()]

    if "start_time" not in columns:
        cursor.execute("ALTER TABLE doctors ADD COLUMN start_time TIME")

    if "end_time" not in columns:
        cursor.execute("ALTER TABLE doctors ADD COLUMN end_time TIME")

    db.commit()

# ---------------- CREATE TABLES ----------------
def create_tables(db):

    cursor = db.cursor()

    cursor.execute(f"USE {DB_NAME}")

    # USERS
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users(
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50),
    password VARCHAR(255)
    )
    """)

    # default admin
    cursor.execute("""
    INSERT INTO users (username,password)
    SELECT * FROM (SELECT 'admin','{}') AS tmp
    WHERE NOT EXISTS (
        SELECT username FROM users WHERE username='admin'
    ) LIMIT 1
    """.format(hash_password("admin123")))

    # DOCTORS
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS doctors(
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100),
    specialization VARCHAR(100),
    fee INT,
    start_time TIME,
    end_time TIME
    )
    """)

    # PATIENTS
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS patients(
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100),
    age INT,
    contact VARCHAR(20),
    email VARCHAR(100),
    address VARCHAR(255),
    cnic VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # APPOINTMENTS
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS appointments(
    id INT AUTO_INCREMENT PRIMARY KEY,
    patient_id INT,
    doctor_id INT,
    appointment_date DATE,
    appointment_time TIME,
    notes TEXT,
    status VARCHAR(20),
    FOREIGN KEY(patient_id) REFERENCES patients(id) ON DELETE CASCADE,
    FOREIGN KEY(doctor_id) REFERENCES doctors(id) ON DELETE CASCADE
    )
    """)

    db.commit()

    # Ensure columns exist (fix for old database)
    ensure_doctor_time_columns(db)

# ---------------- LOGIN ----------------
def login(db,user,password):

    cursor = db.cursor()

    hashed = hash_password(password)

    cursor.execute(
        "SELECT * FROM users WHERE username=%s AND password=%s",
        (user,hashed)
    )

    return cursor.fetchone()

# ---------------- DOCTOR MANAGEMENT ----------------
def add_doctor(db,name,spec,fee,start,end):

    cursor = db.cursor()

    cursor.execute("""
    INSERT INTO doctors(name, specialization, fee, start_time, end_time)
    VALUES (%s, %s, %s, %s, %s)
    """, (name, spec, fee, start, end))

    db.commit()

def get_doctors(db):

    cursor = db.cursor()

    cursor.execute("SELECT * FROM doctors")

    return cursor.fetchall()

# ---------------- PATIENT MANAGEMENT ----------------
def add_patient(db,name,age,contact,email,address,cnic):

    cursor = db.cursor()

    cursor.execute("""
    INSERT INTO patients
    (name,age,contact,email,address,cnic)
    VALUES(%s,%s,%s,%s,%s,%s)
    """,(name,age,contact,email,address,cnic))

    db.commit()

def get_patients(db):

    cursor = db.cursor()

    cursor.execute("SELECT * FROM patients")

    return cursor.fetchall()

# ---------------- APPOINTMENT ----------------
def create_appointment(db,pid,did,adate,atime,notes):

    cursor = db.cursor()

    cursor.execute("""
    INSERT INTO appointments
    (patient_id,doctor_id,appointment_date,appointment_time,notes,status)
    VALUES(%s,%s,%s,%s,%s,'Scheduled')
    """,(pid,did,adate,atime,notes))

    db.commit()

def get_appointments(db):

    cursor = db.cursor()

    cursor.execute("""
    SELECT a.id,p.name,d.name,a.appointment_date,a.appointment_time,a.status
    FROM appointments a
    JOIN patients p ON a.patient_id=p.id
    JOIN doctors d ON a.doctor_id=d.id
    """)

    return cursor.fetchall()

# ---------------- UPDATE APPOINTMENT STATUS ----------------
def update_appointment_status(db, aid, status):

    cursor = db.cursor()

    cursor.execute(
        "UPDATE appointments SET status=%s WHERE id=%s",
        (status, aid)
    )

    db.commit()

# ---------------- DASHBOARD ----------------
def dashboard(db):

    cursor = db.cursor()

    cursor.execute("SELECT COUNT(*) FROM patients")
    p = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM appointments")
    a = cursor.fetchone()[0]

    st.subheader("Hospital Analytics")

    col1,col2 = st.columns(2)

    col1.metric("Total Patients",p)
    col2.metric("Total Appointments",a)

    data = {"Patients":p,"Appointments":a}

    fig,ax = plt.subplots()

    ax.bar(data.keys(),data.values())

    st.pyplot(fig)

# ---------------- PDF REPORT ----------------
def generate_pdf(data):

    pdf = FPDF()

    pdf.add_page()

    pdf.set_font("Arial",size=12)

    for row in data:
        pdf.cell(200,10,txt=str(row),ln=True)

    pdf.output("report.pdf")

# ---------------- EMAIL REMINDER ----------------
def send_email(receiver,msg):

    try:

        server = smtplib.SMTP("smtp.gmail.com",587)

        server.starttls()

        server.login("ghoshmoon19@gmail.com","Soumya123@Roy")

        server.sendmail(
            "ghoshmoon19@gmail.com",
            receiver,
            msg
        )

        server.quit()

        return True

    except:
        return False

# ---------------- AI PREDICTION ----------------
def predict_patient_risk(age):

    if age>60:
        return "High Risk"

    if age>40:
        return "Medium Risk"

    return "Low Risk"

# ---------------- ML DISEASE PREDICTION ----------------
def predict_disease(age,bp,sugar):

    data = np.array([[age,bp,sugar]])

    prediction = model.predict(data)

    if prediction[0] == 1:
        return "⚠ High Risk of Diabetes"

    return "✅ Low Risk"

# ---------------- MAIN APP ----------------
def main():

    df = None

    st.set_page_config(
        page_title="AI Hospital Management System",
        page_icon="🏥",
        layout="wide"
    )

    st.markdown("""
    <style>
    .stApp {
    background-color: #0e1117;
    color: white;
    }
    h1,h2,h3,h4,h5,h6 {
        color:#00e5ff;
    }
    .stButton>button{
        background:#00e5ff;
        color:black;
        border-radius:10px;
    }
    </style>
    """,unsafe_allow_html=True)

    st.image(
        "https://img.freepik.com/free-vector/flat-design-healthcare-banner-template_23-2149611192.jpg",
        use_container_width=True
    )

    st.title("🏥 AI Powered Hospital Management System")

    st.markdown("---")

    db = create_connection()
    create_database(db)
    create_tables(db)

    if "login" not in st.session_state:
        st.session_state.login = False

    if not st.session_state.login:

        st.subheader("Login")

        u = st.text_input("Username")
        p = st.text_input("Password",type="password")

        if st.button("Login"):

            auth = login(db,u,p)

            if auth:
                st.session_state.login=True
                st.success("Login Success")
                st.rerun()
            else:
                st.error("Invalid Credentials")

        return

    menu = st.sidebar.selectbox("Menu",[
        "Dashboard",
        "Add Doctor",
        "Add Patient",
        "View Patients",
        "Create Appointment",
        "Appointments",
        "Disease Prediction",
        "Generate PDF"
    ])

    st.sidebar.markdown("---")

    if st.sidebar.button("Logout"):
        st.session_state.login=False
        st.rerun()

    if menu=="Dashboard":
        dashboard(db)

    elif menu=="Add Doctor":

        name = st.text_input("Doctor Name")
        spec = st.text_input("Specialization")
        fee = st.number_input("Fee")
        start = st.time_input("Start Time")
        end = st.time_input("End Time")

        if st.button("Add"):

            add_doctor(
                db,
                name,
                spec,
                fee,
                start.strftime("%H:%M:%S"),
                end.strftime("%H:%M:%S")
            )

            st.success("Doctor Added Successfully")

    elif menu=="Add Patient":

        name = st.text_input("Name")
        age = st.number_input("Age")
        contact = st.text_input("Contact")
        email = st.text_input("Email")
        address = st.text_input("Address")
        cnic = st.text_input("CNIC")

        if st.button("Save"):

            add_patient(db,name,age,contact,email,address,cnic)

            risk = predict_patient_risk(age)

            st.success(f"Patient Added | Risk Level: {risk}")

    elif menu=="View Patients":

        data = get_patients(db)

        df = pd.DataFrame(data)

        st.dataframe(df)

    elif menu=="Create Appointment":

        patients = get_patients(db)
        doctors = get_doctors(db)

        patient_dict = {p[1]:p[0] for p in patients}
        doctor_dict = {d[1]:d[0] for d in doctors}

        pid = patient_dict[st.selectbox("Patient",patient_dict.keys())]
        did = doctor_dict[st.selectbox("Doctor",doctor_dict.keys())]

        adate = st.date_input("Date")
        atime = st.time_input("Time")

        notes = st.text_area("Notes")

        if st.button("Create"):

            create_appointment(
                db,
                pid,
                did,
                adate.strftime("%Y-%m-%d"),
                atime.strftime("%H:%M:%S"),
                notes
            )

            st.success("Appointment Created")

    elif menu=="Appointments":

        data = get_appointments(db)

        df = pd.DataFrame(
            data,
            columns=["ID","Patient","Doctor","Date","Time","Status"]
        )

        st.dataframe(df)

        st.subheader("Update Appointment Status")

        if df.empty:
            st.warning("No appointments available")
        else:

            aid = st.selectbox("Select Appointment ID",df["ID"].tolist())

            status = st.selectbox(
                "Status",
                ["Scheduled","Completed","Cancelled"]
            )

            if st.button("Update Status"):

                update_appointment_status(db,aid,status)

                st.success("Status Updated")

    elif menu=="Disease Prediction":

        st.subheader("AI Disease Prediction System")

        age = st.number_input("Age")
        bp = st.number_input("Blood Pressure")
        sugar = st.number_input("Sugar Level")

        if st.button("Predict Disease"):

            result = predict_disease(age,bp,sugar)

            st.success(result)

    elif menu=="Generate PDF":

        data = get_patients(db)

        if st.button("Generate Report"):

            generate_pdf(data)

            st.success("PDF Generated")

# ---------------- RUN ----------------
if __name__ == "__main__":
    main()