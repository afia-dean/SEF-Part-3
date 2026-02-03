# Update app.py with the following additions

from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file
from flask_cors import CORS
import os
from dotenv import load_dotenv
from supabase import create_client, Client
import hashlib
from datetime import datetime, timedelta
from functools import wraps
import csv
from io import StringIO

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

# ========== ROLE-BASED ACCESS CONTROL ==========
def role_required(required_role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Please login first', 'error')
                return redirect(url_for('login'))
            
            if session.get('role') != required_role:
                flash(f'Unauthorized access. {required_role.capitalize()} role required.', 'error')
                return redirect(url_for('login'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# ========== AUTHENTICATION ==========
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        password_hash = hash_password(password)
        
        try:
            response = supabase.table('users').select('*').eq('email', email).eq('password', password_hash).execute()
            
            if response.data:
                user = response.data[0]
                session['user_id'] = user['id']
                session['email'] = user['email']
                session['role'] = user['role']
                
                # Get role-specific data
                if user['role'] == 'staff':
                    staff_response = supabase.table('staff').select('*').eq('user_id', user['id']).execute()
                    if staff_response.data:
                        session['staff_id'] = staff_response.data[0]['id']
                        session['staff_name'] = staff_response.data[0]['staff_name']
                        flash('Login successful!', 'success')
                        return redirect(url_for('staff_dashboard'))
                    else:
                        flash('Staff record not found', 'error')
                        
                elif user['role'] == 'organizer':
                    organizer_response = supabase.table('organizer').select('*').eq('user_id', user['id']).execute()
                    if organizer_response.data:
                        session['organizer_id'] = organizer_response.data[0]['id']
                        session['organizer_name'] = organizer_response.data[0]['organizer_name']
                        flash('Login successful!', 'success')
                        return redirect(url_for('organizer_dashboard'))
                    else:
                        flash('Organizer record not found', 'error')
                        
                elif user['role'] == 'donor':
                    donor_response = supabase.table('donors').select('*').eq('user_id', user['id']).execute()
                    if donor_response.data:
                        session['donor_id'] = donor_response.data[0]['id']
                        session['donor_name'] = donor_response.data[0]['donor_name']
                        flash('Login successful!', 'success')
                        return redirect(url_for('donor_dashboard'))
                    else:
                        flash('Donor record not found', 'error')
                        
                elif user['role'] == 'admin':
                    flash('Login successful!', 'success')
                    return redirect(url_for('admin_dashboard'))
                    
                else:
                    flash('Invalid role', 'error')
            else:
                flash('Invalid email or password', 'error')
                
        except Exception as e:
            print(f"Login error: {e}")
            flash('Login failed. Please try again.', 'error')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            # Get form data
            email = request.form.get('email')
            password = request.form.get('password')
            confirm_password = request.form.get('confirm_password')
            role = request.form.get('role')
            full_name = request.form.get('full_name')
            
            # Validation
            if password != confirm_password:
                flash('Passwords do not match', 'error')
                return redirect(url_for('register'))
            
            if role not in ['donor', 'staff', 'organizer', 'admin']:
                flash('Invalid role selected', 'error')
                return redirect(url_for('register'))
            
            # Check if user exists
            existing_user = supabase.table('users').select('*').eq('email', email).execute()
            if existing_user.data:
                flash('Email already registered', 'error')
                return redirect(url_for('register'))
            
            # Hash password
            password_hash = hash_password(password)
            
            # Insert user
            user_response = supabase.table('users').insert({
                'email': email,
                'password': password_hash,
                'role': role,
                'created_at': datetime.now().isoformat()
            }).execute()
            
            user_id = user_response.data[0]['id']
            
            # Create role-specific record
            if role == 'staff':
                hospital_name = request.form.get('hospital_name', 'Not Specified')
                supabase.table('staff').insert({
                    'user_id': user_id,
                    'staff_name': full_name,
                    'hospital_name': hospital_name,
                    'created_at': datetime.now().isoformat()
                }).execute()
                
            elif role == 'donor':
                blood_type = request.form.get('blood_type', 'Unknown')
                age = request.form.get('age')
                
                supabase.table('donors').insert({
                    'user_id': user_id,
                    'donor_name': full_name,
                    'email': email,
                    'blood_type': blood_type,
                    'age': age if age else None,
                    'eligibility_status': False,
                    'medical_history': request.form.get('medical_history', ''),
                    'created_at': datetime.now().isoformat()
                }).execute()
                
            elif role == 'organizer':
                phone = request.form.get('phone', '')
                supabase.table('organizer').insert({
                    'user_id': user_id,
                    'organizer_name': full_name,
                    'phone': phone,
                    'created_at': datetime.now().isoformat()
                }).execute()
            
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
            
        except Exception as e:
            print(f"Registration error: {e}")
            flash('Registration failed. Please try again.', 'error')
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

# ========== EVENT ORGANIZER ROUTES ==========

@app.route('/organizer/dashboard')
@role_required('organizer')
def organizer_dashboard():
    try:
        organizer_id = session.get('organizer_id')
        
        # Get total events
        events_response = supabase.table('events').select('*').eq('organizer_id', organizer_id).execute()
        total_events = len(events_response.data) if events_response.data else 0
        
        # Get total registrations
        registrations_response = supabase.table('registrations').select('*').execute()
        total_registrations = len(registrations_response.data) if registrations_response.data else 0
        
        # Get total attendance
        attendance_response = supabase.table('attendance').select('*').execute()
        total_attendance = len(attendance_response.data) if attendance_response.data else 0
        
        # Get blood units collected (estimated from attendance)
        blood_units_collected = total_attendance * 1  # Assuming 1 unit per donor
        
        # Get recent events
        recent_events = []
        if events_response.data:
            for event in events_response.data[:5]:  # Get last 5 events
                # Get registration count for each event
                reg_count_response = supabase.table('registrations').select('*').eq('event_id', event['id']).execute()
                event['registration_count'] = len(reg_count_response.data) if reg_count_response.data else 0
                recent_events.append(event)
        
        # Get upcoming events
        upcoming_events = []
        today = datetime.now().date()
        if events_response.data:
            for event in events_response.data:
                event_date = datetime.strptime(event['event_date'], '%Y-%m-%d').date() if isinstance(event['event_date'], str) else event['event_date']
                if event_date >= today and event['status'] == 'Upcoming':
                    reg_count_response = supabase.table('registrations').select('*').eq('event_id', event['id']).execute()
                    event['registration_count'] = len(reg_count_response.data) if reg_count_response.data else 0
                    upcoming_events.append(event)
        
        # Calculate statistics
        completed_events_count = sum(1 for event in events_response.data if event.get('status') == 'Completed') if events_response.data else 0
        average_attendance = 75  # Placeholder value
        success_rate = 85  # Placeholder value
        
        return render_template('organizer_dashboard.html',
                             total_events=total_events,
                             total_registrations=total_registrations,
                             total_attendance=total_attendance,
                             blood_units_collected=blood_units_collected,
                             recent_events=recent_events,
                             upcoming_events=upcoming_events,
                             completed_events_count=completed_events_count,
                             average_attendance=average_attendance,
                             success_rate=success_rate)
    
    except Exception as e:
        print(f"Dashboard error: {e}")
        flash('Error loading dashboard', 'error')
        return render_template('organizer_dashboard.html',
                             total_events=0,
                             total_registrations=0,
                             total_attendance=0,
                             blood_units_collected=0,
                             recent_events=[],
                             upcoming_events=[],
                             completed_events_count=0,
                             average_attendance=0,
                             success_rate=0)

@app.route('/organizer/events')
@role_required('organizer')
def manage_events():
    try:
        organizer_id = session.get('organizer_id')
        
        # Get all events for this organizer
        events_response = supabase.table('events').select('*').eq('organizer_id', organizer_id).execute()
        events = events_response.data if events_response.data else []
        
        # Add registration count to each event
        for event in events:
            reg_count_response = supabase.table('registrations').select('*').eq('event_id', event['id']).execute()
            event['registration_count'] = len(reg_count_response.data) if reg_count_response.data else 0
        
        return render_template('manage_events.html', events=events)
    
    except Exception as e:
        print(f"Manage events error: {e}")
        flash('Error loading events', 'error')
        return render_template('manage_events.html', events=[])

@app.route('/organizer/event/<int:event_id>')
@role_required('organizer')
def view_event(event_id):
    try:
        # Get event details
        event_response = supabase.table('events').select('*').eq('id', event_id).execute()
        
        if not event_response.data:
            flash('Event not found', 'error')
            return redirect(url_for('manage_events'))
        
        event = event_response.data[0]
        
        # Get registrations for this event
        registrations_response = supabase.table('registrations').select('*').eq('event_id', event_id).execute()
        
        return render_template('view_event.html', event=event, registrations=registrations_response.data)
    
    except Exception as e:
        print(f"View event error: {e}")
        flash('Error loading event', 'error')
        return redirect(url_for('manage_events'))

@app.route('/organizer/event/save', methods=['POST'])
@role_required('organizer')
def save_event():
    try:
        organizer_id = session.get('organizer_id')
        event_id = request.form.get('event_id')
        
        event_data = {
            'organizer_id': organizer_id,
            'event_name': request.form.get('event_name'),
            'event_date': request.form.get('event_date'),
            'event_time': request.form.get('event_time'),
            'location': request.form.get('location'),
            'description': request.form.get('description'),
            'target_goal': request.form.get('target_goal') or 0,
            'status': request.form.get('status', 'Upcoming')
        }
        
        if event_id:
            # Update existing event
            supabase.table('events').update(event_data).eq('id', event_id).execute()
            flash('Event updated successfully!', 'success')
        else:
            # Create new event
            supabase.table('events').insert(event_data).execute()
            flash('Event created successfully!', 'success')
        
        return redirect(url_for('manage_events'))
    
    except Exception as e:
        print(f"Save event error: {e}")
        flash('Error saving event', 'error')
        return redirect(url_for('manage_events'))

@app.route('/event/<int:event_id>/status', methods=['POST'])
@role_required('organizer')
def update_event_status(event_id):
    try:
        data = request.get_json()
        new_status = data.get('status')
        
        if new_status not in ['Upcoming', 'Ongoing', 'Completed', 'Cancelled']:
            return jsonify({'success': False, 'message': 'Invalid status'})
        
        supabase.table('events').update({'status': new_status}).eq('id', event_id).execute()
        
        return jsonify({'success': True, 'message': 'Event status updated'})
    
    except Exception as e:
        print(f"Update event status error: {e}")
        return jsonify({'success': False, 'message': 'Error updating event status'})

@app.route('/organizer/registrations')
@role_required('organizer')
def view_registrations():
    try:
        organizer_id = session.get('organizer_id')
        event_id = request.args.get('event_id')
        
        # Get all events for dropdown
        events_response = supabase.table('events').select('*').eq('organizer_id', organizer_id).execute()
        all_events = events_response.data if events_response.data else []
        
        registrations = []
        selected_event = None
        statistics = {}
        
        if event_id:
            # Get registrations for specific event
            registrations_response = supabase.table('registrations').select('*').eq('event_id', event_id).execute()
            
            if registrations_response.data:
                # Get donor details for each registration
                for reg in registrations_response.data:
                    # Get donor info
                    donor_response = supabase.table('donors').select('*').eq('user_id', reg['donor_id']).execute()
                    if donor_response.data:
                        reg.update(donor_response.data[0])
                    
                    # Get attendance info
                    attendance_response = supabase.table('attendance').select('*').eq('event_id', event_id).eq('donor_id', reg['donor_id']).execute()
                    if attendance_response.data:
                        reg['check_in_time'] = attendance_response.data[0]['check_in_time']
                    
                    registrations.append(reg)
                
                # Get event details
                event_response = supabase.table('events').select('*').eq('id', event_id).execute()
                if event_response.data:
                    selected_event = event_response.data[0]
                
                # Calculate statistics
                total_registrations_count = len(registrations_response.data)
                confirmed_count = sum(1 for r in registrations_response.data if r.get('status') == 'Confirmed')
                attended_count = len([r for r in registrations if r.get('check_in_time')])
                attendance_rate = (attended_count / total_registrations_count * 100) if total_registrations_count > 0 else 0
                
                # Blood type distribution
                blood_type_distribution = {}
                for reg in registrations:
                    blood_type = reg.get('blood_type')
                    if blood_type:
                        blood_type_distribution[blood_type] = blood_type_distribution.get(blood_type, 0) + 1
                
                statistics = {
                    'total_registrations_count': total_registrations_count,
                    'confirmed_count': confirmed_count,
                    'attended_count': attended_count,
                    'attendance_rate': round(attendance_rate, 1),
                    'blood_type_distribution': blood_type_distribution
                }
        
        return render_template('view_registrations.html',
                             registrations=registrations,
                             all_events=all_events,
                             selected_event=selected_event,
                             selected_event_id=int(event_id) if event_id else None,
                             **statistics)
    
    except Exception as e:
        print(f"View registrations error: {e}")
        flash('Error loading registrations', 'error')
        return render_template('view_registrations.html',
                             registrations=[],
                             all_events=[],
                             selected_event=None,
                             selected_event_id=None,
                             total_registrations_count=0,
                             confirmed_count=0,
                             attended_count=0,
                             attendance_rate=0,
                             blood_type_distribution={})

@app.route('/registration/<int:registration_id>/status', methods=['POST'])
@role_required('organizer')
def update_registration_status(registration_id):
    try:
        data = request.get_json()
        new_status = data.get('status')
        
        if new_status not in ['Pending', 'Confirmed', 'Attended', 'No-show']:
            return jsonify({'success': False, 'message': 'Invalid status'})
        
        supabase.table('registrations').update({'status': new_status}).eq('id', registration_id).execute()
        
        return jsonify({'success': True, 'message': 'Registration status updated'})
    
    except Exception as e:
        print(f"Update registration status error: {e}")
        return jsonify({'success': False, 'message': 'Error updating registration status'})

@app.route('/registration/<int:registration_id>/attendance', methods=['POST'])
@role_required('organizer')
def mark_attendance(registration_id):
    try:
        # Get registration details
        registration_response = supabase.table('registrations').select('*').eq('id', registration_id).execute()
        
        if not registration_response.data:
            return jsonify({'success': False, 'message': 'Registration not found'})
        
        registration = registration_response.data[0]
        
        # Check if attendance already exists
        attendance_response = supabase.table('attendance').select('*').eq('event_id', registration['event_id']).eq('donor_id', registration['donor_id']).execute()
        
        if not attendance_response.data:
            # Create attendance record
            supabase.table('attendance').insert({
                'event_id': registration['event_id'],
                'donor_id': registration['donor_id'],
                'check_in_time': datetime.now().isoformat()
            }).execute()
            
            # Update registration status to Attended
            supabase.table('registrations').update({'status': 'Attended'}).eq('id', registration_id).execute()
        
        return jsonify({'success': True, 'message': 'Attendance marked successfully'})
    
    except Exception as e:
        print(f"Mark attendance error: {e}")
        return jsonify({'success': False, 'message': 'Error marking attendance'})

@app.route('/organizer/track-attendance')
@role_required('organizer')
def track_attendance():
    try:
        organizer_id = session.get('organizer_id')
        
        # Get all events for this organizer
        events_response = supabase.table('events').select('*').eq('organizer_id', organizer_id).execute()
        
        attendance_data = []
        
        if events_response.data:
            for event in events_response.data:
                # Get registrations for this event
                registrations_response = supabase.table('registrations').select('*').eq('event_id', event['id']).execute()
                
                # Get attendance for this event
                attendance_response = supabase.table('attendance').select('*').eq('event_id', event['id']).execute()
                
                event_data = {
                    'event_name': event['event_name'],
                    'event_date': event['event_date'],
                    'total_registrations': len(registrations_response.data) if registrations_response.data else 0,
                    'attended': len(attendance_response.data) if attendance_response.data else 0,
                    'attendance_rate': (len(attendance_response.data) / len(registrations_response.data) * 100) if registrations_response.data and len(registrations_response.data) > 0 else 0
                }
                
                attendance_data.append(event_data)
        
        return render_template('track_attendance.html', attendance_data=attendance_data)
    
    except Exception as e:
        print(f"Track attendance error: {e}")
        flash('Error loading attendance data', 'error')
        return render_template('track_attendance.html', attendance_data=[])

@app.route('/organizer/reports', methods=['GET', 'POST'])
@role_required('organizer')
def generate_report():
    try:
        organizer_id = session.get('organizer_id')
        
        # Get all events for this organizer
        events_response = supabase.table('events').select('*').eq('organizer_id', organizer_id).execute()
        events = events_response.data if events_response.data else []
        
        # Get previous reports
        reports_response = supabase.table('event_reports').select('*').execute()
        previous_reports = reports_response.data if reports_response.data else []
        
        # Add event names to reports
        for report in previous_reports:
            event_response = supabase.table('events').select('event_name').eq('id', report['event_id']).execute()
            if event_response.data:
                report['event_name'] = event_response.data[0]['event_name']
        
        preview_data = None
        
        if request.method == 'POST':
            event_id = request.form.get('event_id')
            action = request.form.get('action')
            
            if event_id:
                # Get event details
                event_response = supabase.table('events').select('*').eq('id', event_id).execute()
                
                if event_response.data:
                    event = event_response.data[0]
                    
                    # Get registrations for this event
                    registrations_response = supabase.table('registrations').select('*').eq('event_id', event_id).execute()
                    registrations = registrations_response.data if registrations_response.data else []
                    
                    # Get attendance count
                    attendance_response = supabase.table('attendance').select('*').eq('event_id', event_id).execute()
                    attended_count = len(attendance_response.data) if attendance_response.data else 0
                    
                    # Get confirmed count
                    confirmed_count = sum(1 for r in registrations if r.get('status') == 'Confirmed')
                    
                    # Blood type distribution
                    blood_type_distribution = {}
                    for reg in registrations:
                        # Get donor blood type
                        donor_response = supabase.table('donors').select('blood_type').eq('user_id', reg['donor_id']).execute()
                        if donor_response.data and donor_response.data[0].get('blood_type'):
                            blood_type = donor_response.data[0]['blood_type']
                            blood_type_distribution[blood_type] = blood_type_distribution.get(blood_type, 0) + 1
                    
                    preview_data = {
                        'event_name': event['event_name'],
                        'event_date': event['event_date'],
                        'event_time': event['event_time'],
                        'location': event['location'],
                        'status': event['status'],
                        'total_registrations': len(registrations),
                        'confirmed_count': confirmed_count,
                        'attended_count': attended_count,
                        'attendance_rate': round((attended_count / len(registrations) * 100), 1) if registrations else 0,
                        'blood_type_distribution': blood_type_distribution,
                        'organizer_notes': request.form.get('organizer_notes', '')
                    }
                    
                    if action == 'generate':
                        # Save report to database
                        report_data = {
                            'event_id': event_id,
                            'total_donors': len(registrations),
                            'blood_units_collected': attended_count,  # Assuming 1 unit per donor
                            'organizer_notes': request.form.get('organizer_notes', ''),
                            'generated_date': datetime.now().isoformat()
                        }
                        
                        supabase.table('event_reports').insert(report_data).execute()
                        
                        flash('Report generated successfully!', 'success')
                        return redirect(url_for('generate_report', event_id=event_id))
        
        return render_template('generate_report.html',
                             events=events,
                             previous_reports=previous_reports,
                             preview_data=preview_data,
                             selected_event_id=request.args.get('event_id'))
    
    except Exception as e:
        print(f"Generate report error: {e}")
        flash('Error generating report', 'error')
        return render_template('generate_report.html',
                             events=[],
                             previous_reports=[],
                             preview_data=None,
                             selected_event_id=None)

@app.route('/report/<int:report_id>/download')
@role_required('organizer')
def download_report(report_id):
    try:
        # Get report details
        report_response = supabase.table('event_reports').select('*').eq('id', report_id).execute()
        
        if not report_response.data:
            flash('Report not found', 'error')
            return redirect(url_for('generate_report'))
        
        report = report_response.data[0]
        
        # Get event details
        event_response = supabase.table('events').select('*').eq('id', report['event_id']).execute()
        
        if not event_response.data:
            flash('Event not found', 'error')
            return redirect(url_for('generate_report'))
        
        event = event_response.data[0]
        
        # Create CSV content
        output = StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(['BloodLink Event Report'])
        writer.writerow([])
        writer.writerow(['Event Details'])
        writer.writerow(['Event Name:', event['event_name']])
        writer.writerow(['Date:', event['event_date']])
        writer.writerow(['Location:', event['location']])
        writer.writerow(['Status:', event['status']])
        writer.writerow([])
        writer.writerow(['Report Statistics'])
        writer.writerow(['Total Donors:', report['total_donors']])
        writer.writerow(['Blood Units Collected:', report['blood_units_collected']])
        writer.writerow(['Report Generated:', report['generated_date']])
        writer.writerow([])
        
        if report['organizer_notes']:
            writer.writerow(['Organizer Notes:'])
            writer.writerow([report['organizer_notes']])
        
        # Prepare response
        output.seek(0)
        filename = f"bloodlink_report_{event['event_name'].replace(' ', '_')}_{report['generated_date'][:10]}.csv"
        
        return send_file(
            output,
            mimetype='text/csv',
            as_attachment=True,
            download_name=filename
        )
    
    except Exception as e:
        print(f"Download report error: {e}")
        flash('Error downloading report', 'error')
        return redirect(url_for('generate_report'))

@app.route('/report/<int:report_id>', methods=['DELETE'])
@role_required('organizer')
def delete_report(report_id):
    try:
        supabase.table('event_reports').delete().eq('id', report_id).execute()
        return jsonify({'success': True, 'message': 'Report deleted successfully'})
    
    except Exception as e:
        print(f"Delete report error: {e}")
        return jsonify({'success': False, 'message': 'Error deleting report'})

# ========== DASHBOARD ROUTES ==========
@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    role = session.get('role')
    if role == 'organizer':
        return redirect(url_for('organizer_dashboard'))
    elif role == 'staff':
        return redirect(url_for('staff_dashboard'))
    elif role == 'admin':
        return redirect(url_for('admin_dashboard'))
    elif role == 'donor':
        return redirect(url_for('donor_dashboard'))
    
    return redirect(url_for('login'))

@app.route('/staff/dashboard')
@role_required('staff')
def staff_dashboard():
    return render_template('staff_dashboard.html', 
                         staff_name=session.get('staff_name'))

@app.route('/donor/dashboard')
@role_required('donor')
def donor_dashboard():
    return render_template('donor_dashboard.html',
                         donor_name=session.get('donor_name'))

@app.route('/admin/dashboard')
@role_required('admin')
def admin_dashboard():
    return render_template('admin_dashboard.html')

# Create track_attendance.html (simple version)
@app.route('/organizer/track-attendance')
@role_required('organizer')
def track_attendance_page():
    return render_template('track_attendance.html')

if __name__ == '__main__':
    app.run(debug=True, port=5000)