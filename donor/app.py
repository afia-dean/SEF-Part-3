from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_cors import CORS
import os
from dotenv import load_dotenv
from supabase import create_client, Client
import hashlib
from datetime import datetime

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key")
CORS(app)

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# ========== AUTHENTICATION ==========
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        password_hash = hash_password(password)
        
        try:
            # Check users table
            response = supabase.table('users').select('*').eq('email', email).eq('password', password_hash).execute()
            
            if response.data:
                user = response.data[0]
                session['user_id'] = user['id']
                session['email'] = user['email']
                session['role'] = user['role']
                
                # Role-based Redirection
                if user['role'] == 'staff':
                    staff_res = supabase.table('staff').select('*').eq('user_id', user['id']).execute()
                    if staff_res.data:
                        session['staff_name'] = staff_res.data[0].get('staff_name', 'Staff')
                        session['staff_id'] = staff_res.data[0].get('id')
                    return redirect(url_for('staff_dashboard'))
                
                elif user['role'] == 'donor':
                    return redirect(url_for('donor_dashboard'))
                
                elif user['role'] == 'organizer':
                    return redirect(url_for('organizer_dashboard'))
                
                elif user['role'] == 'admin':
                    return redirect(url_for('admin_dashboard'))
                
            else:
                flash('Invalid email or password', 'error')
                
        except Exception as e:
            print(f"Login error: {e}")
            flash('Login failed. Please try again.', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

# ========== NAVIGATION LOGIC ==========
@app.route('/')
def index():
    if 'user_id' in session:
        role = session.get('role')
        if role == 'staff': return redirect(url_for('staff_dashboard'))
        if role == 'donor': return redirect(url_for('donor_dashboard'))
    return redirect(url_for('login'))

# ========== STAFF ROUTES ==========
@app.route('/staff/dashboard')
def staff_dashboard():
    if 'user_id' not in session or session.get('role') != 'staff':
        return redirect(url_for('login'))
    # ... (Your existing staff dashboard logic remains here)
    return render_template('staff_dashboard.html', staff_name=session.get('staff_name', 'Staff'), current_date=datetime.now().strftime("%B %d, %Y"))

# ========== DONOR ROUTES ==========
@app.route('/donor')
def donor_dashboard():
    if 'user_id' not in session or session.get('role') != 'donor':
        return redirect(url_for('login'))
    return render_template('donor.html')

@app.route('/donor/appointment')
def donor_appointment():
    if 'user_id' not in session: return redirect(url_for('login'))
    return render_template('appointment.html')

@app.route('/donor/eligibility')
def donor_eligibility():
    if 'user_id' not in session: return redirect(url_for('login'))
    return render_template('eligibility.html')

@app.route('/donor/medical')
def donor_medical():
    if 'user_id' not in session: return redirect(url_for('login'))
    return render_template('medical.html')

@app.route('/donor/notifications')
def donor_notifications():
    if 'user_id' not in session: return redirect(url_for('login'))
    return render_template('notifications.html')

# ========== PLACEHOLDERS FOR OTHER ROLES ==========
@app.route('/organizer/dashboard')
def organizer_dashboard():
    if session.get('role') != 'organizer': return redirect(url_for('login'))
    return "Organizer Dashboard Coming Soon"

@app.route('/admin/dashboard')
def admin_dashboard():
    if session.get('role') != 'admin': return redirect(url_for('login'))
    return "Admin Dashboard Coming Soon"

if __name__ == '__main__':
    app.run(debug=True, port=5000)
