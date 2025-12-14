# healthcare_app.py
"""
Healthcare Management System - Flask demo with OTP (dev) + exports + background auto-update.
Dev OTP: printed to server console. Do NOT use as-is in production.
"""

import os
import secrets
import threading
import time
import tempfile
import traceback
from datetime import datetime, timedelta
import random

# If you want Twilio later:
try:
    from twilio.rest import Client
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False

from flask import (
    Flask, render_template, jsonify, send_file, request,
    session, redirect, url_for
)
from flask_cors import CORS
import pandas as pd

# ---------- Config ----------
PORT = int(os.environ.get("HCS_PORT", 5002))
HOST = os.environ.get("HCS_HOST", "0.0.0.0")
AUTO_UPDATE_SECONDS = int(os.environ.get("HCS_UPDATE_SECONDS", 20))
GENERATE_EMP_COUNT = int(os.environ.get("HCS_EMP_COUNT", 300))
GENERATE_PAT_COUNT = int(os.environ.get("HCS_PAT_COUNT", 300))
UPDATE_MODE = os.environ.get("HCS_UPDATE_MODE", "update_timestamps")  # or "replace_full"

OTP_TTL_SECONDS = int(os.environ.get("OTP_TTL_SECONDS", 300))
MAX_OTP_ATTEMPTS = int(os.environ.get("MAX_OTP_ATTEMPTS", 5))

# Patient OTP & access (for employee -> patient consent flow)
PATIENT_OTP_TTL_SECONDS = int(os.environ.get("PATIENT_OTP_TTL_SECONDS", 300))  # otp life (seconds)
PATIENT_ACCESS_SECONDS = int(os.environ.get("PATIENT_ACCESS_SECONDS", 120))    # how long employee can view after verify (seconds)

# Patient login OTP (for patient login improvement)
PATIENT_LOGIN_OTP_TTL_SECONDS = int(os.environ.get("PATIENT_LOGIN_OTP_TTL_SECONDS", 300))

# ---------- App setup ----------
app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.environ.get("HCS_SECRET") or secrets.token_hex(32)
CORS(app)

# Thread safety lock
data_lock = threading.Lock()

# In-memory data
healthcare_data = {
    "employees": [],
    "patients": [],
    "last_updated": None,
    "processing": False
}

# Demo users (dev only)
USERS = {
    "employee": {
        "emp001": {"password": "emp123", "name": "Dr. John Smith", "role": "Doctor", "employee_id": 1},
        "emp002": {"password": "emp123", "name": "Sarah Johnson", "role": "Nurse", "employee_id": 2},
        "admin": {"password": "admin123", "name": "Admin User", "role": "Administrator", "employee_id": 0}
    },
    "patient": {
        "pat001": {"password": "pat123", "name": "Michael Brown", "patient_id": 1},
        "pat002": {"password": "pat123", "name": "Emily Davis", "patient_id": 2},
    }
}

# OTP store (dev, in-memory) for employee login OTPs
otp_store = {}  # { identifier: { otp, expires_at, attempts } }

# Patient OTP store (dev, in-memory) for patient consent OTPs
patient_otp_store = {}  # { phone: { otp, expires_at, attempts, patient_id } }

# Patient login OTP store (dev, in-memory) for patient login OTPs
patient_login_otp_store = {}  # { identifier: { otp, expires_at, attempts } }

# ---------- Synthetic data generators ----------
def generate_employee_data(count=300):
    roles = ['Doctor', 'Nurse', 'Pharmacist', 'Lab Technician', 'Receptionist', 'Administrator']
    departments = ['Cardiology', 'Pediatrics', 'Orthopedics', 'Neurology', 'Emergency', 'Surgery']
    hospitals = ['City Hospital', 'General Medical Center', 'Metro Clinic', 'Central Hospital', 'Care Hospital']
    first_names = ['John', 'Sarah', 'Michael', 'Emily', 'David', 'Jessica', 'James', 'Maria', 'Robert', 'Lisa']
    last_names = ['Smith', 'Johnson', 'Williams', 'Brown', 'Davis', 'Miller', 'Wilson', 'Moore', 'Taylor', 'Anderson']
    employees = []
    for i in range(count):
        joining_date = datetime.now() - timedelta(days=random.randint(30, 1825))
        notice_period_days = random.choice([30, 60, 90])
        employee = {
            'id': i + 1,
            'employee_id': f'EMP{str(i+1).zfill(4)}',
            'name': f'{random.choice(first_names)} {random.choice(last_names)}',
            'role': random.choice(roles),
            'department': random.choice(departments),
            'email': f'employee{i+1}@healthcare.com',
            'phone': f'+1-{random.randint(200,999)}-{random.randint(100,999)}-{random.randint(1000,9999)}',
            'joining_date': joining_date.strftime('%Y-%m-%d'),
            'notice_period_days': notice_period_days,
            'previous_hospital': random.choice(hospitals),
            'previous_experience_years': random.randint(0, 15),
            'current_salary': random.randint(40000, 150000),
            'status': random.choice(['Active', 'Active', 'Active', 'On Leave']),
            'last_updated': datetime.now().isoformat()
        }
        employees.append(employee)
    return employees

def generate_patient_data(count=300):
    conditions = ['Hypertension', 'Diabetes', 'Asthma', 'Arthritis', 'Heart Disease', 'None']
    doctors = ['Dr. Smith', 'Dr. Johnson', 'Dr. Williams', 'Dr. Brown', 'Dr. Davis']
    blood_groups = ['A+', 'A-', 'B+', 'B-', 'O+', 'O-', 'AB+', 'AB-']
    first_names = ['Michael', 'Emily', 'Daniel', 'Olivia', 'Matthew', 'Sophia', 'Christopher', 'Ava']
    last_names = ['Brown', 'Davis', 'Miller', 'Wilson', 'Moore', 'Taylor', 'Anderson', 'Thomas']
    patients = []
    for i in range(count):
        admission_date = datetime.now() - timedelta(days=random.randint(1, 365))
        last_visit = datetime.now() - timedelta(days=random.randint(1, 90))
        patient = {
            'id': i + 1,
            'patient_id': f'PAT{str(i+1).zfill(4)}',
            'name': f'{random.choice(first_names)} {random.choice(last_names)}',
            'age': random.randint(18, 85),
            'gender': random.choice(['Male', 'Female']),
            'blood_group': random.choice(blood_groups),
            'phone': f'+1-{random.randint(200,999)}-{random.randint(100,999)}-{random.randint(1000,9999)}',
            'email': f'patient{i+1}@email.com',
            'address': f'{random.randint(100, 9999)} {random.choice(["Main","Oak","Maple","Park"])} St',
            'consulting_doctor': random.choice(doctors),
            'department': random.choice(['Cardiology','Pediatrics','Orthopedics','Neurology']),
            'condition': random.choice(conditions),
            'admission_date': admission_date.strftime('%Y-%m-%d'),
            'last_visit_date': last_visit.strftime('%Y-%m-%d'),
            'next_appointment': (datetime.now() + timedelta(days=random.randint(7, 60))).strftime('%Y-%m-%d'),
            'medication': random.choice(['Aspirin', 'Metformin', 'Lisinopril', 'Atorvastatin', 'None']),
            'status': random.choice(['Active', 'Recovered', 'Under Treatment']),
            'last_updated': datetime.now().isoformat()
        }
        patients.append(patient)
    return patients

# ---------- Background updater ----------
def update_data_background():
    while True:
        try:
            with data_lock:
                if healthcare_data.get('processing'):
                    pass
                else:
                    healthcare_data['processing'] = True
                    now_str = datetime.now().strftime('%H:%M:%S')
                    print(f"[{now_str}] Background update mode={UPDATE_MODE} ...")
                    if UPDATE_MODE == 'replace_full':
                        healthcare_data['employees'] = generate_employee_data(GENERATE_EMP_COUNT)
                        healthcare_data['patients'] = generate_patient_data(GENERATE_PAT_COUNT)
                    else:
                        # lightweight update: refresh timestamps only
                        for e in healthcare_data['employees']:
                            e['last_updated'] = datetime.now().isoformat()
                        for p in healthcare_data['patients']:
                            p['last_updated'] = datetime.now().isoformat()
                    healthcare_data['last_updated'] = datetime.now().isoformat()
                    healthcare_data['processing'] = False
                    print(f"[{now_str}] Data updated.")
        except Exception as ex:
            print("Background update error:", ex)
            traceback.print_exc()
            with data_lock:
                healthcare_data['processing'] = False
        time.sleep(AUTO_UPDATE_SECONDS)

# Start updater daemon
updater_thread = threading.Thread(target=update_data_background, daemon=True)
updater_thread.start()

# ---------- OTP helpers (employee login OTP already present) ----------
def _generate_otp():
    return f"{random.randint(100000, 999999)}"

def send_otp_dev_log(identifier, otp):
    print(f"[DEV-OTP] Identifier={identifier} OTP={otp} (valid {OTP_TTL_SECONDS}s)")

def request_otp_for(identifier):
    otp = _generate_otp()
    expires_at = datetime.utcnow() + timedelta(seconds=OTP_TTL_SECONDS)
    otp_store[identifier] = {'otp': otp, 'expires_at': expires_at, 'attempts': 0}
    send_otp_dev_log(identifier, otp)
    return otp

# ---------- Patient OTP helpers (consent) ----------
def _gen_otp():
    """Generate a 6-digit OTP for patient consent flow."""
    return f"{random.randint(100000, 999999)}"

def send_patient_otp_dev_log(phone, otp):
    print(f"[DEV-PATIENT-OTP] Phone={phone} OTP={otp} (valid {PATIENT_OTP_TTL_SECONDS}s)")

# Optional Twilio helper (commented if Twilio not configured)
def send_sms_via_twilio(to_number, message):
    if not TWILIO_AVAILABLE:
        print("[SMS-FALLBACK] Twilio not installed; message:", to_number, message)
        return None
    TWILIO_SID = os.environ.get('TWILIO_ACCOUNT_SID')
    TWILIO_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')
    TWILIO_FROM = os.environ.get('TWILIO_FROM')
    if not (TWILIO_SID and TWILIO_TOKEN and TWILIO_FROM):
        # fallback to dev-log
        print("[SMS-FALLBACK] Twilio not configured; message:", to_number, message)
        return None
    client = Client(TWILIO_SID, TWILIO_TOKEN)
    msg = client.messages.create(body=message, from_=TWILIO_FROM, to=to_number)
    return msg.sid

# Optional cleanup thread for expired OTPs (employee OTPs)
def otp_cleanup_task():
    while True:
        now = datetime.utcnow()
        to_remove = [k for k, v in otp_store.items() if v['expires_at'] < now]
        for k in to_remove:
            otp_store.pop(k, None)
        time.sleep(60)

threading.Thread(target=otp_cleanup_task, daemon=True).start()

# Optional cleanup thread for expired patient login OTPs
def patient_login_otp_cleanup_task():
    while True:
        now = datetime.utcnow()
        to_remove = [k for k, v in patient_login_otp_store.items() if v['expires_at'] < now]
        for k in to_remove:
            patient_login_otp_store.pop(k, None)
        time.sleep(60)

threading.Thread(target=patient_login_otp_cleanup_task, daemon=True).start()

# Optional cleanup thread for expired patient OTPs
def patient_otp_cleanup_task():
    while True:
        now = datetime.utcnow()
        to_remove = [k for k, v in patient_otp_store.items() if v['expires_at'] < now]
        for k in to_remove:
            patient_otp_store.pop(k, None)
        time.sleep(60)

threading.Thread(target=patient_otp_cleanup_task, daemon=True).start()

# ---------- Routes ----------
@app.route('/')
def home():
    if 'user_type' in session:
        if session['user_type'] == 'employee':
            return redirect(url_for('employee_dashboard'))
        else:
            return redirect(url_for('patient_dashboard'))
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    data = request.json or {}
    user_type = data.get('user_type')
    username = data.get('username')
    password = data.get('password')
    
    if user_type in USERS:
        # First try direct username lookup
        if username in USERS[user_type] and USERS[user_type][username]['password'] == password:
            session['user_type'] = user_type
            session['username'] = username
            session['user_data'] = USERS[user_type][username]
            return jsonify({'success': True, 'redirect': f'/{user_type}_dashboard'})
        
        # If not found and looks like email, search by email
        if '@' in username:
            for uname, user_data in USERS[user_type].items():
                if user_data.get('email') == username and user_data['password'] == password:
                    session['user_type'] = user_type
                    session['username'] = uname
                    session['user_data'] = user_data
                    return jsonify({'success': True, 'redirect': f'/{user_type}_dashboard'})
    
    return jsonify({'success': False, 'message': 'Invalid credentials'}), 401

@app.route('/register', methods=['POST'])
def register():
    data = request.json or {}
    user_type = data.get('user_type', 'patient')
    
    if user_type not in ['patient', 'employee']:
        return jsonify({'success': False, 'message': 'Invalid user type'}), 400
    
    required_fields = ['name', 'email', 'phone', 'password']
    if user_type == 'patient':
        required_fields.extend(['dob', 'gender', 'address', 'blood_group'])
    else:
        required_fields.extend(['role', 'department'])
    
    for field in required_fields:
        if not data.get(field):
            return jsonify({'success': False, 'message': f'{field.replace("_", " ").title()} is required'}), 400
    
    # Check if email already exists
    for ut in USERS:
        for user in USERS[ut].values():
            if user.get('email') == data['email']:
                return jsonify({'success': False, 'message': 'Email already registered'}), 400
    
    username = data['email']  # Use email as username
    
    if user_type == 'patient':
        # Generate patient ID
        patient_id = max([u.get('patient_id', 0) for u in USERS['patient'].values()] + [0]) + 1
        
        new_user = {
            'password': data['password'],
            'name': data['name'],
            'email': data['email'],
            'phone': data['phone'],
            'patient_id': patient_id,
            'age': calculate_age(data['dob']),
            'gender': data['gender'],
            'address': data['address'],
            'blood_group': data['blood_group'],
            'consulting_doctor': 'Dr. Smith',  # Default
            'department': 'General Medicine',  # Default
            'condition': 'New Patient',
            'medication': 'None',
            'status': 'Active',
            'admission_date': datetime.now().strftime('%Y-%m-%d'),
            'last_visit_date': datetime.now().strftime('%Y-%m-%d'),
            'next_appointment': 'Not scheduled',
            'last_updated': datetime.now().isoformat()
        }
    else:  # employee
        # Generate employee ID
        employee_id = max([u.get('employee_id', 0) for u in USERS['employee'].values()] + [0]) + 1
        
        new_user = {
            'password': data['password'],
            'name': data['name'],
            'email': data['email'],
            'phone': data['phone'],
            'role': data['role'],
            'department': data['department'],
            'employee_id': employee_id,
            'last_updated': datetime.now().isoformat()
        }
    
    USERS[user_type][username] = new_user
    
    return jsonify({'success': True, 'message': f'Registration successful! Your username is {username}'})

def calculate_age(dob_str):
    dob = datetime.strptime(dob_str, '%Y-%m-%d')
    today = datetime.now()
    age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    return age

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/employee_dashboard')
def employee_dashboard():
    if 'user_type' not in session or session['user_type'] != 'employee':
        return redirect(url_for('home'))

    user = session['user_data']
    is_admin = user.get('role') == 'Administrator'

    return render_template(
        'employee_dashboard.html',
        user=user,
        is_admin=is_admin
    )

@app.route('/admin/manual-update')
def admin_manual_update():
    return render_template('admin/manual_update.html')

@app.route('/admin/manage-users')
def admin_manage_users():
    return render_template('admin/manage_users.html')

@app.route('/admin/add-employee')
def admin_add_employee():
    return render_template('admin/add_employee.html')

@app.route('/admin/audit-logs')
def admin_audit_logs():
    return render_template('admin/audit_logs.html')


@app.route('/api/request-patient-otp', methods=['POST'])
def api_request_patient_otp():
    if 'user_type' not in session or session['user_type'] != 'employee':
        return jsonify({'ok': False, 'error': 'unauthorized'}), 403

    data = request.json or {}
    phone = data.get('phone')
    patient_id = data.get('patient_id')

    if not phone or not patient_id:
        return jsonify({'ok': False, 'error': 'phone and patient_id required'}), 400

    # Validate patient exists
    with data_lock:
        patient_exists = any(p['patient_id'] == patient_id for p in healthcare_data['patients'])
    if not patient_exists:
        return jsonify({'ok': False, 'error': 'patient not found'}), 404

    otp = _gen_otp()
    expires_at = datetime.utcnow() + timedelta(seconds=PATIENT_OTP_TTL_SECONDS)
    patient_otp_store[phone] = {
        'otp': otp,
        'expires_at': expires_at,
        'attempts': 0,
        'patient_id': patient_id
    }

    # DEV: log OTP to server; in production replace with send_sms_via_twilio(phone, msg)
    send_patient_otp_dev_log(phone, otp)

    return jsonify({'ok': True, 'message': 'OTP sent (dev mode log)'})


@app.route('/api/verify-patient-otp', methods=['POST'])
def api_verify_patient_otp():
    if 'user_type' not in session or session['user_type'] != 'employee':
        return jsonify({'ok': False, 'error': 'unauthorized'}), 403

    data = request.json or {}
    phone = data.get('phone')
    otp = data.get('otp')

    if not phone or not otp:
        return jsonify({'ok': False, 'error': 'phone and otp required'}), 400

    record = patient_otp_store.get(phone)
    if not record:
        return jsonify({'ok': False, 'error': 'otp not requested for this phone'}), 400

    if datetime.utcnow() > record['expires_at']:
        patient_otp_store.pop(phone, None)
        return jsonify({'ok': False, 'error': 'otp expired'}), 400

    if record['otp'] != str(otp).strip():
        # increment attempts for logging / rate-limit
        record['attempts'] = record.get('attempts', 0) + 1
        if record['attempts'] > 5:
            patient_otp_store.pop(phone, None)
            return jsonify({'ok': False, 'error': 'too many attempts'}), 429
        return jsonify({'ok': False, 'error': 'invalid otp'}), 400

    # success → assign temporary access
    access_expires_at = datetime.utcnow() + timedelta(seconds=PATIENT_ACCESS_SECONDS)
    session['patient_access'] = {
        'patient_id': record['patient_id'],
        'expires_at': access_expires_at.isoformat()
    }

    # clear the OTP record
    patient_otp_store.pop(phone, None)

    return jsonify({
        'ok': True,
        'message': 'OTP verified',
        'access_expires_in': PATIENT_ACCESS_SECONDS
    })


@app.route('/api/get-patient/<patient_id>')
def api_get_patient(patient_id):
    """
    Returns full patient details only if:
     - request from the patient themselves (session user_type == 'patient' and patient_id matches), OR
     - request from an employee who has temporary patient_access in session and it matches this patient and not expired.
    Otherwise returns 401/403.
    """
    if 'user_type' not in session:
        return jsonify({'error': 'Unauthorized'}), 403

    with data_lock:
        patient = next((p for p in healthcare_data['patients'] if p['patient_id'] == patient_id or str(p['id']) == str(patient_id)), None)

    if not patient:
        return jsonify({'error': 'Not found'}), 404

    # If patient is asking for their own data
    if session['user_type'] == 'patient':
        # session user_data patient_id may be numeric (as in USERS) while patient['patient_id'] is string PATxxxx
        # We'll try to match by id number or patient_id string
        sess_pid = session['user_data'].get('patient_id')
        # If sess_pid is numeric id, match by p['id']; else if string like PAT0001, match directly.
        if (isinstance(sess_pid, int) and sess_pid == patient.get('id')) or (isinstance(sess_pid, str) and sess_pid == patient.get('patient_id')):
            return jsonify({'patient': patient})
        return jsonify({'error': 'Unauthorized'}), 403

    # If employee: check session patient_access
    if session['user_type'] == 'employee':
        access = session.get('patient_access')
        if not access:
            return jsonify({'error': 'access_required', 'message': 'OTP verification required'}), 401

        try:
            expires_at = datetime.fromisoformat(access['expires_at'])
        except Exception:
            session.pop('patient_access', None)
            return jsonify({'error': 'access_required', 'message': 'OTP verification required'}), 401

        if datetime.utcnow() > expires_at:
            session.pop('patient_access', None)
            return jsonify({'error': 'access_expired', 'message': 'Access expired'}), 401

        # ensure the access patient matches the requested patient (match by patient_id)
        if access.get('patient_id') != patient.get('patient_id'):
            return jsonify({'error': 'access_mismatch', 'message': 'OTP was for a different patient'}), 403

        # Authorized
        return jsonify({'patient': patient, 'access_expires_at': access['expires_at']})

    return jsonify({'error': 'Unauthorized'}), 403


@app.route('/api/revoke-patient-access', methods=['POST'])
def api_revoke_patient_access():
    if 'user_type' not in session or session['user_type'] != 'employee':
        return jsonify({'ok': False, 'error': 'unauthorized'}), 403
    session.pop('patient_access', None)
    return jsonify({'ok': True})


@app.route('/api/employees')
def api_get_employees():
    if 'user_type' not in session or session['user_type'] != 'employee':
        return jsonify({'error': 'Unauthorized'}), 403
    with data_lock:
        return jsonify({
            'employees': healthcare_data['employees'],
            'total': len(healthcare_data['employees']),
            'last_updated': healthcare_data['last_updated']
        })

@app.route('/api/patients')
def api_get_patients():
    if 'user_type' not in session:
        return jsonify({'error': 'Unauthorized'}), 403
    with data_lock:
        if session['user_type'] == 'employee':
            return jsonify({
                'patients': healthcare_data['patients'],
                'total': len(healthcare_data['patients']),
                'last_updated': healthcare_data['last_updated']
            })
        elif session['user_type'] == 'patient':
            # Return only the patient's own data
            patient_id = session['user_data'].get('patient_id')
            # match by numeric id, by stored patient_id string, or by PAT#### formatted id
            def _matches(p, pid):
                try:
                    if pid is None:
                        return False
                    if str(p.get('id')) == str(pid):
                        return True
                    if str(p.get('patient_id')) == str(pid):
                        return True
                    # try PAT formatting when pid is numeric or numeric string
                    try:
                        formatted = f"PAT{int(pid):04d}"
                        if str(p.get('patient_id')) == formatted:
                            return True
                    except Exception:
                        pass
                except Exception:
                    return False
                return False

            patient = next((p for p in healthcare_data['patients'] if _matches(p, patient_id)), None)
            if patient:
                return jsonify({
                    'patients': [patient],
                    'total': 1,
                    'last_updated': healthcare_data['last_updated']
                })
            else:
                return jsonify({'patients': [], 'total': 0, 'last_updated': healthcare_data['last_updated']})
        else:
            return jsonify({'error': 'Unauthorized'}), 403


@app.route('/api/patient/me')
def api_patient_me():
    """Return the logged-in patient's own data. Used by patient_dashboard.html which
    fetches `/api/patient/me`.
    """
    if 'user_type' not in session:
        return jsonify({'error': 'Unauthorized'}), 403
    if session['user_type'] != 'patient':
        return jsonify({'error': 'Unauthorized'}), 403

    patient_id = session['user_data'].get('patient_id')
    with data_lock:
        def _matches(p, pid):
            try:
                if pid is None:
                    return False
                if str(p.get('id')) == str(pid):
                    return True
                if str(p.get('patient_id')) == str(pid):
                    return True
                try:
                    formatted = f"PAT{int(pid):04d}"
                    if str(p.get('patient_id')) == formatted:
                        return True
                except Exception:
                    pass
            except Exception:
                return False
            return False

        patient = next((p for p in healthcare_data['patients'] if _matches(p, patient_id)), None)

    if patient:
        return jsonify({'patients': [patient], 'total': 1, 'last_updated': healthcare_data['last_updated']})
    return jsonify({'patients': [], 'total': 0, 'last_updated': healthcare_data['last_updated']})


@app.route('/patient_dashboard')
def patient_dashboard():
    if 'user_type' not in session or session['user_type'] != 'patient':
        return redirect(url_for('home'))
    return render_template('patient_dashboard.html', user=session['user_data'])

@app.route('/api/register-appointment', methods=['POST'])
def register_appointment():
    if 'user_type' not in session or session['user_type'] != 'patient':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    data = request.json or {}
    date = data.get('date')
    time = data.get('time')
    reason = data.get('reason', '')
    
    if not date or not time:
        return jsonify({'success': False, 'message': 'Date and time are required'}), 400
    
    # Update patient's next appointment
    username = session['username']
    if username in USERS['patient']:
        appointment_datetime = f"{date} {time}"
        USERS['patient'][username]['next_appointment'] = appointment_datetime
        USERS['patient'][username]['last_updated'] = datetime.now().isoformat()
        
        return jsonify({'success': True, 'message': f'Appointment registered for {appointment_datetime}'})
    
    return jsonify({'success': False, 'message': 'Patient not found'}), 404

# Exports using temp files
def _export_dataframe_tempfile(df, fmt):
    suffix = '.csv' if fmt == 'csv' else '.xlsx'
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp_name = tmp.name
    tmp.close()
    if fmt == 'csv':
        df.to_csv(tmp_name, index=False)
    else:
        df.to_excel(tmp_name, index=False, sheet_name='Data')
    return tmp_name

@app.route('/api/export/employees/<fmt>')
def api_export_employees(fmt):
    if 'user_type' not in session or session['user_type'] != 'employee':
        return jsonify({'error': 'Unauthorized'}), 403
    fmt = fmt.lower()
    if fmt not in ('csv', 'excel', 'xlsx'):
        return jsonify({'error': 'Invalid format'}), 400
    try:
        with data_lock:
            df = pd.DataFrame(healthcare_data['employees'])
        file_path = _export_dataframe_tempfile(df, 'csv' if fmt == 'csv' else 'xlsx')
        resp = send_file(file_path, as_attachment=True)
        def _cleanup(path):
            try:
                time.sleep(1)
                os.remove(path)
            except Exception:
                pass
        threading.Thread(target=_cleanup, args=(file_path,), daemon=True).start()
        return resp
    except Exception as ex:
        traceback.print_exc()
        return jsonify({'error': str(ex)}), 500

@app.route('/api/export/patients/<fmt>')
def api_export_patients(fmt):
    if 'user_type' not in session or session['user_type'] != 'employee':
        return jsonify({'error': 'Unauthorized'}), 403
    fmt = fmt.lower()
    if fmt not in ('csv', 'excel', 'xlsx'):
        return jsonify({'error': 'Invalid format'}), 400
    try:
        with data_lock:
            df = pd.DataFrame(healthcare_data['patients'])
        file_path = _export_dataframe_tempfile(df, 'csv' if fmt == 'csv' else 'xlsx')
        resp = send_file(file_path, as_attachment=True)
        def _cleanup(path):
            try:
                time.sleep(1)
                os.remove(path)
            except Exception:
                pass
        threading.Thread(target=_cleanup, args=(file_path,), daemon=True).start()
        return resp
    except Exception as ex:
        traceback.print_exc()
        return jsonify({'error': str(ex)}), 500

# ---------- OTP endpoints (employee login OTP) ----------
@app.route('/api/request-otp', methods=['POST'])
def api_request_otp():
    data = request.json or {}
    identifier = data.get('identifier')
    if not identifier:
        return jsonify({'ok': False, 'error': 'identifier required'}), 400
    # validate identifier belongs to an employee
    if identifier not in USERS.get('employee', {}):
        return jsonify({'ok': False, 'error': 'unknown employee identifier'}), 404
    try:
        request_otp_for(identifier)
        return jsonify({'ok': True, 'message': 'OTP generated (dev-log).'})
    except Exception as ex:
        return jsonify({'ok': False, 'error': str(ex)}), 500

@app.route('/api/verify-otp', methods=['POST'])
def api_verify_otp():
    data = request.json or {}
    identifier = data.get('identifier')
    otp = data.get('otp')
    if not identifier or not otp:
        return jsonify({'ok': False, 'error': 'identifier and otp required'}), 400
    record = otp_store.get(identifier)
    if not record:
        return jsonify({'ok': False, 'error': 'no OTP requested for this identifier'}), 400
    record['attempts'] += 1
    if record['attempts'] > MAX_OTP_ATTEMPTS:
        otp_store.pop(identifier, None)
        return jsonify({'ok': False, 'error': 'too many attempts'}), 429
    if datetime.utcnow() > record['expires_at']:
        otp_store.pop(identifier, None)
        return jsonify({'ok': False, 'error': 'otp expired'}), 400
    if record['otp'] != str(otp).strip():
        return jsonify({'ok': False, 'error': 'invalid otp'}), 400
    # success
    otp_store.pop(identifier, None)
    user_data = USERS['employee'].get(identifier)
    if not user_data:
        return jsonify({'ok': False, 'error': 'employee not found'}), 404
    session['user_type'] = 'employee'
    session['username'] = identifier
    session['user_data'] = user_data
    return jsonify({'ok': True, 'message': 'OTP verified', 'redirect': '/employee_dashboard'})

@app.route('/api/request-patient-login-otp', methods=['POST'])
def api_request_patient_login_otp():
    data = request.json or {}
    identifier = data.get('identifier')
    if not identifier:
        return jsonify({'ok': False, 'error': 'identifier required'}), 400
    # validate identifier belongs to a patient
    if identifier not in USERS.get('patient', {}):
        return jsonify({'ok': False, 'error': 'unknown patient identifier'}), 404
    try:
        otp = _generate_otp()
        expires_at = datetime.utcnow() + timedelta(seconds=PATIENT_LOGIN_OTP_TTL_SECONDS)
        patient_login_otp_store[identifier] = {'otp': otp, 'expires_at': expires_at, 'attempts': 0}
        print(f"[DEV-PATIENT-LOGIN-OTP] Identifier={identifier} OTP={otp} (valid {PATIENT_LOGIN_OTP_TTL_SECONDS}s)")
        return jsonify({'ok': True, 'message': 'OTP generated (dev-log).'})
    except Exception as ex:
        return jsonify({'ok': False, 'error': str(ex)}), 500

@app.route('/api/verify-patient-login-otp', methods=['POST'])
def api_verify_patient_login_otp():
    data = request.json or {}
    identifier = data.get('identifier')
    otp = data.get('otp')
    if not identifier or not otp:
        return jsonify({'ok': False, 'error': 'identifier and otp required'}), 400
    record = patient_login_otp_store.get(identifier)
    if not record:
        return jsonify({'ok': False, 'error': 'no OTP requested for this identifier'}), 400
    record['attempts'] += 1
    if record['attempts'] > MAX_OTP_ATTEMPTS:
        patient_login_otp_store.pop(identifier, None)
        return jsonify({'ok': False, 'error': 'too many attempts'}), 429
    if datetime.utcnow() > record['expires_at']:
        patient_login_otp_store.pop(identifier, None)
        return jsonify({'ok': False, 'error': 'otp expired'}), 400
    if record['otp'] != str(otp).strip():
        return jsonify({'ok': False, 'error': 'invalid otp'}), 400
    # success
    patient_login_otp_store.pop(identifier, None)
    user_data = USERS['patient'].get(identifier)
    if not user_data:
        return jsonify({'ok': False, 'error': 'patient not found'}), 404
    session['user_type'] = 'patient'
    session['username'] = identifier
    session['user_data'] = user_data
    return jsonify({'ok': True, 'message': 'OTP verified', 'redirect': '/patient_dashboard'})

@app.route('/api/stats')
def api_stats():
    if 'user_type' not in session:
        return jsonify({'error': 'Unauthorized'}), 403
    with data_lock:
        stats = {
            'total_employees': len(healthcare_data['employees']),
            'total_patients': len(healthcare_data['patients']),
            'active_employees': len([e for e in healthcare_data['employees'] if e.get('status') == 'Active']),
            'active_patients': len([p for p in healthcare_data['patients'] if p.get('status') == 'Active']),
            'last_updated': healthcare_data['last_updated']
        }
    return jsonify(stats)


# ---------- Admin / employee management APIs (in-memory demo) ----------
def _is_admin_session():
    return ('user_type' in session and session['user_type'] == 'employee'
            and session.get('user_data', {}).get('role') == 'Administrator')


@app.route('/api/manual_update')
def api_manual_update():
    if not _is_admin_session():
        return jsonify({'success': False, 'error': 'unauthorized'}), 403
    try:
        with data_lock:
            if UPDATE_MODE == 'replace_full':
                healthcare_data['employees'] = generate_employee_data(GENERATE_EMP_COUNT)
                healthcare_data['patients'] = generate_patient_data(GENERATE_PAT_COUNT)
            else:
                for e in healthcare_data['employees']:
                    e['last_updated'] = datetime.now().isoformat()
                for p in healthcare_data['patients']:
                    p['last_updated'] = datetime.now().isoformat()
            healthcare_data['last_updated'] = datetime.now().isoformat()
        return jsonify({'success': True})
    except Exception as ex:
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(ex)}), 500


@app.route('/api/employees', methods=['POST'])
def api_add_employee():
    if not _is_admin_session():
        return jsonify({'success': False, 'error': 'unauthorized'}), 403
    data = request.json or {}
    name = data.get('name')
    role = data.get('role')
    department = data.get('department')
    email = data.get('email')
    phone = data.get('phone')
    password = data.get('password')
    if not name or not role:
        return jsonify({'success': False, 'error': 'name and role required'}), 400
    try:
        with data_lock:
            max_id = max((e.get('id', 0) for e in healthcare_data['employees']), default=0)
            new_id = max_id + 1
            emp_code = f'EMP{str(new_id).zfill(4)}'
            new_emp = {
                'id': new_id,
                'employee_id': emp_code,
                'name': name,
                'role': role,
                'department': department or '',
                'email': email or '',
                'phone': phone or '',
                'joining_date': datetime.now().strftime('%Y-%m-%d'),
                'notice_period_days': 30,
                'previous_hospital': '',
                'previous_experience_years': 0,
                'current_salary': 0,
                'status': 'Active',
                'last_updated': datetime.now().isoformat()
            }
            healthcare_data['employees'].append(new_emp)
            # create a demo login if password provided
            if password:
                username = f'emp{str(new_id).zfill(3)}'
                USERS.setdefault('employee', {})[username] = {
                    'password': password,
                    'name': name,
                    'role': role,
                    'employee_id': new_id
                }
        return jsonify({'success': True, 'employee': new_emp})
    except Exception as ex:
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(ex)}), 500


@app.route('/api/employees/<int:emp_id>', methods=['PUT', 'DELETE'])
def api_modify_employee(emp_id):
    if not _is_admin_session():
        return jsonify({'success': False, 'error': 'unauthorized'}), 403
    if request.method == 'DELETE':
        try:
            with data_lock:
                idx = next((i for i, e in enumerate(healthcare_data['employees']) if e.get('id') == emp_id), None)
                if idx is None:
                    return jsonify({'success': False, 'error': 'not found'}), 404
                removed = healthcare_data['employees'].pop(idx)
                # remove any USERS entries matching employee_id
                for uname, ud in list(USERS.get('employee', {}).items()):
                    if ud.get('employee_id') == emp_id:
                        USERS['employee'].pop(uname, None)
            return jsonify({'success': True, 'removed': removed})
        except Exception as ex:
            traceback.print_exc()
            return jsonify({'success': False, 'error': str(ex)}), 500

    # PUT -> update
    data = request.json or {}
    try:
        with data_lock:
            emp = next((e for e in healthcare_data['employees'] if e.get('id') == emp_id), None)
            if not emp:
                return jsonify({'success': False, 'error': 'not found'}), 404
            # update allowed fields
            for k in ('name', 'role', 'department', 'email', 'phone', 'status'):
                if k in data:
                    emp[k] = data[k]
            emp['last_updated'] = datetime.now().isoformat()
            # also update USERS mapping if exists
            for uname, ud in USERS.get('employee', {}).items():
                if ud.get('employee_id') == emp_id:
                    ud['name'] = emp.get('name')
                    ud['role'] = emp.get('role')
        return jsonify({'success': True, 'employee': emp})
    except Exception as ex:
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(ex)}), 500


@app.route('/api/employees/<int:emp_id>/password', methods=['PATCH'])
def api_change_employee_password(emp_id):
    if not _is_admin_session():
        return jsonify({'success': False, 'error': 'unauthorized'}), 403
    data = request.json or {}
    new_password = data.get('password')
    if not new_password:
        return jsonify({'success': False, 'error': 'password required'}), 400
    try:
        updated = False
        with data_lock:
            for uname, ud in USERS.get('employee', {}).items():
                if ud.get('employee_id') == emp_id:
                    ud['password'] = new_password
                    updated = True
        if updated:
            return jsonify({'success': True})
        else:
            # No login for this employee; still return success for demo
            return jsonify({'success': True, 'warning': 'no-login-for-employee'})
    except Exception as ex:
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(ex)}), 500


@app.route('/api/patients/<int:pat_id>', methods=['PUT', 'DELETE'])
def api_modify_patient(pat_id):
    if 'user_type' not in session or session['user_type'] != 'employee':
        return jsonify({'success': False, 'error': 'unauthorized'}), 403
    user = session['user_data']
    is_admin = user.get('role') == 'Administrator'
    
    if request.method == 'DELETE':
        if not is_admin:
            return jsonify({'success': False, 'error': 'only admin can delete patients'}), 403
        try:
            with data_lock:
                idx = next((i for i, p in enumerate(healthcare_data['patients']) if p.get('id') == pat_id), None)
                if idx is None:
                    return jsonify({'success': False, 'error': 'not found'}), 404
                removed = healthcare_data['patients'].pop(idx)
                # remove any USERS entries matching patient_id
                for uname, ud in list(USERS.get('patient', {}).items()):
                    if ud.get('patient_id') == pat_id:
                        USERS['patient'].pop(uname, None)
            return jsonify({'success': True, 'removed': removed})
        except Exception as ex:
            traceback.print_exc()
            return jsonify({'success': False, 'error': str(ex)}), 500

    # PUT -> update
    data = request.json or {}
    action = data.get('action')  # for discharge
    try:
        with data_lock:
            pat = next((p for p in healthcare_data['patients'] if p.get('id') == pat_id), None)
            if not pat:
                return jsonify({'success': False, 'error': 'not found'}), 404
            if action == 'discharge':
                if session['user_type'] == 'employee':  # employees can discharge
                    pat['status'] = 'Discharged'
                    pat['last_updated'] = datetime.now().isoformat()
                else:
                    return jsonify({'success': False, 'error': 'unauthorized for discharge'}), 403
            else:
                # update allowed fields - only admin can update?
                if not is_admin:
                    return jsonify({'success': False, 'error': 'only admin can update patient details'}), 403
                for k in ('name', 'age', 'gender', 'blood_group', 'phone', 'email', 'address', 'consulting_doctor', 'department', 'condition', 'admission_date', 'last_visit_date', 'next_appointment', 'medication', 'status'):
                    if k in data:
                        pat[k] = data[k]
                pat['last_updated'] = datetime.now().isoformat()
                # also update USERS mapping if exists
                for uname, ud in USERS.get('patient', {}).items():
                    if ud.get('patient_id') == pat_id:
                        ud['name'] = pat.get('name')
        return jsonify({'success': True, 'patient': pat})
    except Exception as ex:
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(ex)}), 500


@app.route('/api/audit/logs')
def api_audit_logs():
    if not _is_admin_session():
        return jsonify({'logs': []})
    # demo: return empty logs
    return jsonify({'logs': []})

# ---------- Initialize demo data ----------
with data_lock:
    healthcare_data['employees'] = generate_employee_data(GENERATE_EMP_COUNT)
    healthcare_data['patients'] = generate_patient_data(GENERATE_PAT_COUNT)
    healthcare_data['last_updated'] = datetime.now().isoformat()

if __name__ == '__main__':
    print("\n" + "="*60)
    print(" HEALTHCARE MANAGEMENT SYSTEM (Flask demo)")
    print("="*60)
    print(f" Web App: http://localhost:{PORT}")
    print(f" Auto-update every {AUTO_UPDATE_SECONDS}s (mode={UPDATE_MODE})")
    print(f" Records: {len(healthcare_data['employees'])} employees + {len(healthcare_data['patients'])} patients")
    print("="*60 + "\n")
    app.run(debug=True, host=HOST, port=PORT, use_reloader=False)
