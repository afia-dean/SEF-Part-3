from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file
from flask_cors import CORS
import os
from dotenv import load_dotenv
from supabase import create_client, Client
import hashlib
from datetime import datetime
import csv
from io import StringIO
from functools import wraps

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
                
                if user['role'] == 'staff':
                    staff_response = supabase.table('staff').select('*').eq('user_id', user['id']).execute()
                    
                    if staff_response.data:
                        session['staff_id'] = staff_response.data[0]['id']
                        session['staff_name'] = staff_response.data[0]['staff_name']
                        flash('Login successful!', 'success')
                        return redirect(url_for('staff_dashboard'))
                    else:
                        flash('Staff record not found', 'error')
                elif user['role'] == 'donor':
                    donor_response = supabase.table('donors').select('*').eq('user_id', user['id']).execute()
                    
                    if donor_response.data:
                        session['donor_id'] = donor_response.data[0]['id']
                        session['donor_name'] = donor_response.data[0]['donor_name']
                        flash('Login successful!', 'success')
                        return redirect(url_for('donor_dashboard'))
                    else:
                        flash('Donor record not found. Please contact support.', 'error')
                elif user['role'] == 'organizer':

                    organizer_response = supabase.table('organizer').select('*').eq('user_id', user['id']).execute()
                    
                    if organizer_response.data:
                        organizer = organizer_response.data[0]
                        session['organizer_id'] = organizer['id']
                        session['organizer_name'] = organizer.get('organizer_name', organizer.get('full_name', 'Organizer'))
                        flash('Login successful!', 'success')
                        return redirect(url_for('organizer_dashboard'))
                    else:
                        flash('Organizer record not found. Please contact support.', 'error')
                elif user['role'] == 'admin':
                    flash('Login successful!', 'success')
                    return redirect(url_for('admin_dashboard'))
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
            email = request.form.get('email')
            password = request.form.get('password')
            confirm_password = request.form.get('confirm_password')
            role = request.form.get('role')
            full_name = request.form.get('full_name')
            
            if password != confirm_password:
                flash('Passwords do not match', 'error')
                return redirect(url_for('register'))
            
            if role not in ['donor', 'staff', 'organizer', 'admin']:
                flash('Invalid role selected', 'error')
                return redirect(url_for('register'))
            
            existing_user = supabase.table('users').select('*').eq('email', email).execute()
            if existing_user.data:
                flash('Email already registered', 'error')
                return redirect(url_for('register'))
            
            password_hash = hash_password(password)
            
            user_response = supabase.table('users').insert({
                'email': email,
                'password': password_hash,
                'role': role,
                'created_at': datetime.now().isoformat()
            }).execute()
            
            user_id = user_response.data[0]['id']
            
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
                
                donor_data = {
                    'user_id': user_id,
                    'donor_name': full_name,
                    'email': email,
                    'blood_type': blood_type,
                    'eligibility_status': False,
                    'medical_history': request.form.get('medical_history', ''),
                    'disqualification_reason': 'Pending verification',
                    'created_at': datetime.now().isoformat()
                }
                
                if age and age.isdigit():
                    donor_data['age'] = int(age)
                
                supabase.table('donors').insert(donor_data).execute()
            
            elif role == 'organizer':
                # Create organizer record in organizers table
                supabase.table('organizers').insert({
                    'user_id': user_id,
                    'organizer_name': full_name,
                    'email': email,
                    'created_at': datetime.now().isoformat()
                }).execute()
            
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
                        
        except Exception as e:
            flash('Registration failed. Please try again.', 'error')
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

# ========== DASHBOARD ==========
@app.route('/')
def index():
    if 'user_id' in session:
        if session.get('role') == 'staff':
            return redirect(url_for('staff_dashboard'))
        elif session.get('role') == 'donor':
            return redirect(url_for('donor_dashboard'))
        elif session.get('role') == 'organizer':
            return redirect(url_for('organizer_dashboard'))
        elif session.get('role') == 'admin':
            return redirect(url_for('admin_dashboard'))
    return redirect(url_for('login'))

@app.route('/staff/dashboard')
@role_required('staff')
def staff_dashboard():
    try:
        staff_response = supabase.table('staff').select('*').eq('user_id', session['user_id']).execute()
        
        if not staff_response.data:
            flash('Staff record not found', 'error')
            return redirect(url_for('logout'))
        
        staff_details = staff_response.data[0]
        hospital_name = staff_details.get('hospital_name', 'Hospital')
        
        inventory_response = supabase.table('inventory').select('*').execute()
        total_units = sum(item['quantity'] for item in inventory_response.data) if inventory_response.data else 0
        
        requests_response = supabase.table('urgent_request').select('*', count='exact').eq('status', 'Pending').execute()
        pending_requests = len(requests_response.data)
        
        donors_response = supabase.table('donors').select('*', count='exact').execute()
        total_donors = len(donors_response.data)
        
    except Exception as e:
        total_units = 0
        pending_requests = 0
        total_donors = 0
        hospital_name = 'Hospital'
        staff_details = {'staff_name': 'Staff'}
    
    return render_template('staff_dashboard.html', 
                         total_units=total_units,
                         pending_requests=pending_requests,
                         total_donors=total_donors,
                         staff_name=staff_details.get('staff_name', 'Staff'),
                         hospital_name=hospital_name,
                         current_date=datetime.now().strftime("%B %d, %Y"))

# ========== DONOR ROUTES ==========
@app.route('/donor/dashboard')
@role_required('donor')
def donor_dashboard():
    try:
        donor_response = supabase.table('donors').select('*').eq('user_id', session['user_id']).execute()
        
        if not donor_response.data:
            flash('Donor record not found', 'error')
            return redirect(url_for('logout'))
        
        donor = donor_response.data[0]
        
        # Get registered events
        appointments = []
        try:
            # Get registrations for this donor
            registrations_response = supabase.table('registrations')\
                .select('*')\
                .eq('donor_id', session['user_id'])\
                .execute()
            
            if registrations_response.data:
                # Get event details for each registration
                for registration in registrations_response.data:
                    if registration.get('event_id'):
                        event_response = supabase.table('events')\
                            .select('*')\
                            .eq('id', registration['event_id'])\
                            .execute()
                        
                        if event_response.data:
                            # Combine registration and event data
                            event = event_response.data[0]
                            appointment = {
                                'event': event,
                                'status': registration.get('status', 'Pending'),
                                'registered_at': registration.get('registered_at'),
                                'check_in_time': registration.get('registered_at')
                            }
                            appointments.append(appointment)
        except Exception as e:
            print(f"Note: Could not fetch appointments: {e}")
            appointments = []
        
        # Get last donation date
        last_donation = None
        if donor.get('last_donation_date'):
            last_donation = {'donation_date': donor['last_donation_date']}
        
        # Get unread notifications count
        unread_notifications = 0
        try:
            unread_response = supabase.table('notifications').select('*', count='exact').eq('status', False).execute()
            if unread_response.data:
                unread_notifications = len(unread_response.data)
        except Exception as e:
            print(f"Note: Could not fetch notifications: {e}")
            unread_notifications = 0
        
        return render_template('donor.html',
                             donor=donor,
                             appointments=appointments,
                             last_donation=last_donation,
                             unread_notifications=unread_notifications)
        
    except Exception as e:
        print(f"Error loading dashboard: {e}")
        flash('Error loading dashboard', 'error')
        return redirect(url_for('login'))

@app.route('/donor/appointment', methods=['GET', 'POST'])
@role_required('donor')
def donor_appointment():
    try:
        donor_response = supabase.table('donors').select('*').eq('user_id', session['user_id']).execute()
        if not donor_response.data:
            flash('Donor record not found', 'error')
            return redirect(url_for('logout'))
        
        donor = donor_response.data[0]
        
        # Get ALL events from events table
        events_response = supabase.table('events').select('*').order('event_date').execute()
        events = events_response.data if events_response.data else []
        
        print(f"DEBUG: Found {len(events)} events in database")
        
        # Get existing registrations for this donor
        registered_event_ids = []
        try:
            # Use session['user_id'] (which is users.id) to check registrations
            registrations_response = supabase.table('registrations')\
                .select('event_id')\
                .eq('donor_id', session['user_id'])\
                .execute()
            
            if registrations_response.data:
                registered_event_ids = [reg['event_id'] for reg in registrations_response.data]
        except Exception as e:
            print(f"Note: Could not fetch registrations: {e}")
            registered_event_ids = []
        
        print(f"DEBUG: Already registered for event IDs: {registered_event_ids}")
        
        # Determine which events are registerable
        today = datetime.now().date()
        for event in events:
            # Parse event date
            event_date = None
            if event.get('event_date'):
                if isinstance(event['event_date'], str):
                    try:
                        event_date = datetime.strptime(event['event_date'], '%Y-%m-%d').date()
                    except:
                        event_date = None
                elif isinstance(event['event_date'], datetime):
                    event_date = event['event_date'].date()
            
            # Check if event is in past
            is_past = False
            if event_date:
                is_past = event_date < today
            
            # Check if event is cancelled
            is_cancelled = event.get('status') == 'Cancelled'
            
            # Check if already registered
            already_registered = event['id'] in registered_event_ids
            
            # Can register if: not past, not cancelled, not already registered, and eligible
            event['can_register'] = (not is_past and 
                                   not is_cancelled and 
                                   not already_registered and 
                                   donor.get('eligibility_status', False))
            
            event['is_past'] = is_past
            event['is_cancelled'] = is_cancelled
            event['already_registered'] = already_registered
        
        if request.method == 'POST':
            try:
                data = request.get_json()
                event_id = data.get('event_id')
                
                if not event_id:
                    return jsonify({'success': False, 'error': 'Event ID required'}), 400
                
                # Check if already registered
                existing_registration = supabase.table('registrations')\
                    .select('*')\
                    .eq('donor_id', session['user_id'])\
                    .eq('event_id', event_id)\
                    .execute()
                
                if existing_registration.data:
                    return jsonify({'success': False, 'error': 'Already registered for this event'}), 400
                
                # Create registration using user_id from session
                registration_response = supabase.table('registrations').insert({
                    'donor_id': session['user_id'],
                    'event_id': event_id,
                    'status': 'Pending',
                    'registered_at': datetime.now().isoformat()
                }).execute()
                
                return jsonify({'success': True, 'message': 'Successfully registered for event!'})
                
            except Exception as e:
                print(f"Error registering for event: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
        
        return render_template('appointment.html',
                             donor=donor,
                             events=events,
                             registered_event_ids=registered_event_ids)
        
    except Exception as e:
        print(f"Error loading appointment page: {e}")
        flash('Error loading appointment page', 'error')
        return redirect(url_for('donor_dashboard'))

@app.route('/donor/eligibility')
@role_required('donor')
def donor_eligibility():
    try:
        donor_response = supabase.table('donors').select('*').eq('user_id', session['user_id']).execute()
        
        if not donor_response.data:
            flash('Donor record not found', 'error')
            return redirect(url_for('logout'))
        
        donor = donor_response.data[0]
        
        unread_notifications = 0
        try:
            unread_response = supabase.table('notifications').select('*', count='exact').eq('status', False).execute()
            if unread_response.data:
                unread_notifications = len(unread_response.data)
        except Exception as e:
            print(f"Note: Could not fetch notifications: {e}")
            unread_notifications = 0
        
        return render_template('eligibility.html',
                             donor=donor,
                             unread_notifications=unread_notifications)
        
    except Exception as e:
        print(f"Error loading eligibility page: {e}")
        flash('Error loading eligibility page', 'error')
        return redirect(url_for('donor_dashboard'))

@app.route('/donor/eligibility/check')
@role_required('donor')
def check_eligibility():
    try:
        donor_response = supabase.table('donors').select('*').eq('user_id', session['user_id']).execute()
        
        if not donor_response.data:
            return jsonify({'success': False, 'error': 'Donor not found'}), 404
        
        donor = donor_response.data[0]
        
        eligible = donor.get('eligibility_status', False)
        reason = donor.get('disqualification_reason', '')
        last_donation = donor.get('last_donation_date')
        
        if last_donation:
            if isinstance(last_donation, datetime):
                last_donation_str = last_donation.isoformat()
            elif isinstance(last_donation, str):
                last_donation_str = last_donation
            else:
                last_donation_str = str(last_donation)
        else:
            last_donation_str = None
        
        response_data = {
            'success': True,
            'eligible': eligible,
            'message': 'You are eligible to donate!' if eligible else 'You are not eligible to donate.',
            'reason': reason if reason else '',
            'last_donation': last_donation_str
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        print(f"Error checking eligibility: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/donor/medical')
@role_required('donor')
def donor_medical():
    return render_template('medical.html')

@app.route('/donor/medical/get')
@role_required('donor')
def get_medical_info():
    try:
        donor_response = supabase.table('donors').select('medical_history, medical_notes').eq('user_id', session['user_id']).execute()
        
        if donor_response.data:
            donor = donor_response.data[0]
            medical_info = donor.get('medical_history') or donor.get('medical_notes') or ''
            return jsonify({'success': True, 'medical_info': medical_info})
        else:
            return jsonify({'success': False, 'error': 'Donor not found'}), 404
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/donor/medical/save', methods=['POST'])
@role_required('donor')
def save_medical_info():
    try:
        data = request.get_json()
        medical_history = data.get('medical_history', '')
        
        response = supabase.table('donors').update({
            'medical_history': medical_history,
            'updated_at': datetime.now().isoformat()
        }).eq('user_id', session['user_id']).execute()
        
        return jsonify({'success': True, 'message': 'Medical information saved'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/donor/notifications')
@role_required('donor')
def donor_notifications():
    return render_template('notifications.html')

@app.route('/donor/notifications/all')
@role_required('donor')
def get_donor_notifications():
    try:
        notifications_response = supabase.table('notifications').select('*').execute()
        
        if notifications_response.data:
            formatted_notifications = []
            for notification in notifications_response.data:
                formatted_notifications.append({
                    'id': notification.get('id'),
                    'title': 'Notification',
                    'message': notification.get('message', ''),
                    'status': 'read' if notification.get('status') else 'unread',
                    'read': notification.get('status', False),
                    'created_at': datetime.now().isoformat()
                })
            
            return jsonify({
                'success': True,
                'notifications': formatted_notifications
            })
        else:
            return jsonify({
                'success': True,
                'notifications': []
            })
        
    except Exception as e:
        print(f"Error fetching notifications: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/donor/notifications/mark-read', methods=['POST'])
@role_required('donor')
def mark_notification_read():
    try:
        data = request.get_json()
        notification_id = data.get('notification_id')
        
        if not notification_id:
            return jsonify({'success': False, 'error': 'Notification ID required'}), 400
        
        response = supabase.table('notifications').update({
            'status': True
        }).eq('id', notification_id).execute()
        
        return jsonify({'success': True, 'message': 'Notification marked as read'})
        
    except Exception as e:
        print(f"Error marking notification: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/donor/notifications/mark-all-read', methods=['POST'])
@role_required('donor')
def mark_all_notifications_read():
    try:
        response = supabase.table('notifications').update({
            'status': True
        }).eq('status', False).execute()
        
        return jsonify({'success': True, 'message': 'All notifications marked as read'})
        
    except Exception as e:
        print(f"Error marking all notifications: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ========== ORGANIZER ROUTES ==========
@app.route('/organizer/dashboard')
@role_required('organizer')
def organizer_dashboard():
    try:
        organizer_id = session.get('organizer_id') or session.get('user_id')
        
        # Get events created by this organizer
        events_response = supabase.table('events').select('*').eq('organizer_id', organizer_id).execute()
        total_events = len(events_response.data) if events_response.data else 0
        
        # Get total registrations across all events
        total_registrations = 0
        if events_response.data:
            for event in events_response.data:
                reg_response = supabase.table('registrations').select('*', count='exact').eq('event_id', event['id']).execute()
                if reg_response.data:
                    total_registrations += len(reg_response.data)
        
        # Get total attendance
        total_attendance = 0
        if events_response.data:
            for event in events_response.data:
                attendance_response = supabase.table('attendance').select('*', count='exact').eq('event_id', event['id']).execute()
                if attendance_response.data:
                    total_attendance += len(attendance_response.data)
        
        # Blood units collected
        blood_units_collected = total_attendance
        
        # Recent events
        recent_events = []
        if events_response.data:
            for event in events_response.data[:5]:
                reg_count_response = supabase.table('registrations').select('*', count='exact').eq('event_id', event['id']).execute()
                event['registration_count'] = len(reg_count_response.data) if reg_count_response.data else 0
                recent_events.append(event)
        
        # Upcoming events
        upcoming_events = []
        today = datetime.now().date()
        if events_response.data:
            for event in events_response.data:
                event_date = None
                if event.get('event_date'):
                    if isinstance(event['event_date'], str):
                        try:
                            event_date = datetime.strptime(event['event_date'], '%Y-%m-%d').date()
                        except:
                            event_date = None
                    elif isinstance(event['event_date'], datetime):
                        event_date = event['event_date'].date()
                
                if event_date and event_date >= today and event.get('status') == 'Upcoming':
                    reg_count_response = supabase.table('registrations').select('*', count='exact').eq('event_id', event['id']).execute()
                    event['registration_count'] = len(reg_count_response.data) if reg_count_response.data else 0
                    upcoming_events.append(event)
        
        # Statistics
        completed_events_count = sum(1 for event in events_response.data if event.get('status') == 'Completed') if events_response.data else 0
        average_attendance = (total_attendance / completed_events_count) if completed_events_count > 0 else 0
        success_rate = (completed_events_count / total_events * 100) if total_events > 0 else 0
        
        return render_template('organizer_dashboard.html',
                             total_events=total_events,
                             total_registrations=total_registrations,
                             total_attendance=total_attendance,
                             blood_units_collected=blood_units_collected,
                             recent_events=recent_events,
                             upcoming_events=upcoming_events,
                             completed_events_count=completed_events_count,
                             average_attendance=round(average_attendance, 1),
                             success_rate=round(success_rate, 1))
    
    except Exception as e:
        print(f"Organizer dashboard error: {e}")
        flash('Error loading organizer dashboard', 'error')
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
        organizer_id = session.get('organizer_id') or session.get('user_id')
        
        events_response = supabase.table('events').select('*').eq('organizer_id', organizer_id).execute()
        events = events_response.data if events_response.data else []
        
        for event in events:
            reg_count_response = supabase.table('registrations').select('*', count='exact').eq('event_id', event['id']).execute()
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
        event_response = supabase.table('events').select('*').eq('id', event_id).execute()
        
        if not event_response.data:
            flash('Event not found', 'error')
            return redirect(url_for('manage_events'))
        
        event = event_response.data[0]
        
        registrations_response = supabase.table('registrations').select('*').eq('event_id', event_id).execute()
        registrations = registrations_response.data if registrations_response.data else []
        
        return render_template('view_event.html', event=event, registrations=registrations)
    
    except Exception as e:
        print(f"View event error: {e}")
        flash('Error loading event', 'error')
        return redirect(url_for('manage_events'))

@app.route('/organizer/event/save', methods=['POST'])
@role_required('organizer')
def save_event():
    try:
        organizer_id = session.get('organizer_id') or session.get('user_id')
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
            supabase.table('events').update(event_data).eq('id', event_id).execute()
            flash('Event updated successfully!', 'success')
        else:
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
        organizer_id = session.get('organizer_id') or session.get('user_id')
        event_id = request.args.get('event_id')
        
        events_response = supabase.table('events').select('*').eq('organizer_id', organizer_id).execute()
        all_events = events_response.data if events_response.data else []
        
        registrations = []
        selected_event = None
        statistics = {}
        
        if event_id:
            registrations_response = supabase.table('registrations').select('*').eq('event_id', event_id).execute()
            
            if registrations_response.data:
                for reg in registrations_response.data:
                    donor_response = supabase.table('donors').select('*').eq('user_id', reg['donor_id']).execute()
                    if donor_response.data:
                        reg.update(donor_response.data[0])
                    
                    attendance_response = supabase.table('attendance').select('*').eq('event_id', event_id).eq('donor_id', reg['donor_id']).execute()
                    if attendance_response.data:
                        reg['check_in_time'] = attendance_response.data[0]['check_in_time']
                    
                    registrations.append(reg)
                
                event_response = supabase.table('events').select('*').eq('id', event_id).execute()
                if event_response.data:
                    selected_event = event_response.data[0]
                
                total_registrations_count = len(registrations_response.data)
                confirmed_count = sum(1 for r in registrations_response.data if r.get('status') == 'Confirmed')
                attended_count = len([r for r in registrations if r.get('check_in_time')])
                attendance_rate = (attended_count / total_registrations_count * 100) if total_registrations_count > 0 else 0
                
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
        registration_response = supabase.table('registrations').select('*').eq('id', registration_id).execute()
        
        if not registration_response.data:
            return jsonify({'success': False, 'message': 'Registration not found'})
        
        registration = registration_response.data[0]
        
        attendance_response = supabase.table('attendance').select('*').eq('event_id', registration['event_id']).eq('donor_id', registration['donor_id']).execute()
        
        if not attendance_response.data:
            supabase.table('attendance').insert({
                'event_id': registration['event_id'],
                'donor_id': registration['donor_id'],
                'check_in_time': datetime.now().isoformat()
            }).execute()
            
            supabase.table('registrations').update({'status': 'Attended'}).eq('id', registration_id).execute()
        
        return jsonify({'success': True, 'message': 'Attendance marked successfully'})
    
    except Exception as e:
        print(f"Mark attendance error: {e}")
        return jsonify({'success': False, 'message': 'Error marking attendance'})

@app.route('/organizer/track-attendance')
@role_required('organizer')
def track_attendance():
    try:
        organizer_id = session.get('organizer_id') or session.get('user_id')
        
        events_response = supabase.table('events').select('*').eq('organizer_id', organizer_id).execute()
        
        attendance_data = []
        
        if events_response.data:
            for event in events_response.data:
                registrations_response = supabase.table('registrations').select('*', count='exact').eq('event_id', event['id']).execute()
                attendance_response = supabase.table('attendance').select('*', count='exact').eq('event_id', event['id']).execute()
                
                total_reg = len(registrations_response.data) if registrations_response.data else 0
                attended = len(attendance_response.data) if attendance_response.data else 0
                
                event_data = {
                    'event_name': event['event_name'],
                    'event_date': event['event_date'],
                    'total_registrations': total_reg,
                    'attended': attended,
                    'attendance_rate': (attended / total_reg * 100) if total_reg > 0 else 0
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
        organizer_id = session.get('organizer_id') or session.get('user_id')
        
        events_response = supabase.table('events').select('*').eq('organizer_id', organizer_id).execute()
        events = events_response.data if events_response.data else []
        
        reports_response = supabase.table('event_reports').select('*').execute()
        previous_reports = reports_response.data if reports_response.data else []
        
        for report in previous_reports:
            event_response = supabase.table('events').select('event_name').eq('id', report['event_id']).execute()
            if event_response.data:
                report['event_name'] = event_response.data[0]['event_name']
        
        preview_data = None
        
        if request.method == 'POST':
            event_id = request.form.get('event_id')
            action = request.form.get('action')
            
            if event_id:
                event_response = supabase.table('events').select('*').eq('id', event_id).execute()
                
                if event_response.data:
                    event = event_response.data[0]
                    
                    registrations_response = supabase.table('registrations').select('*').eq('event_id', event_id).execute()
                    registrations = registrations_response.data if registrations_response.data else []
                    
                    attendance_response = supabase.table('attendance').select('*', count='exact').eq('event_id', event_id).execute()
                    attended_count = len(attendance_response.data) if attendance_response.data else 0
                    
                    confirmed_count = sum(1 for r in registrations if r.get('status') == 'Confirmed')
                    
                    blood_type_distribution = {}
                    for reg in registrations:
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
                        report_data = {
                            'event_id': event_id,
                            'total_donors': len(registrations),
                            'blood_units_collected': attended_count,
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
        report_response = supabase.table('event_reports').select('*').eq('id', report_id).execute()
        
        if not report_response.data:
            flash('Report not found', 'error')
            return redirect(url_for('generate_report'))
        
        report = report_response.data[0]
        
        event_response = supabase.table('events').select('*').eq('id', report['event_id']).execute()
        
        if not event_response.data:
            flash('Event not found', 'error')
            return redirect(url_for('generate_report'))
        
        event = event_response.data[0]
        
        output = StringIO()
        writer = csv.writer(output)
        
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

# ========== STAFF ROUTES ==========
@app.route('/staff/inventory', methods=['GET'])
@role_required('staff')
def view_inventory():
    try:
        response = supabase.table('inventory').select('*').order('blood_type').execute()
        inventory = response.data
        
        blood_types = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']
        
        return render_template('update_inventory.html', 
                             inventory=inventory,
                             blood_types=blood_types)
        
    except Exception as e:
        flash('Error loading inventory', 'error')
        return render_template('update_inventory.html', inventory=[], blood_types=[])

@app.route('/staff/inventory/update', methods=['POST'])
@role_required('staff')
def update_inventory():
    try:
        data = request.get_json()
        blood_type = data.get('blood_type')
        quantity = data.get('quantity')
        
        if not blood_type or quantity is None:
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400
        
        existing = supabase.table('inventory').select('*').eq('blood_type', blood_type).execute()
        
        if existing.data:
            response = supabase.table('inventory').update({
                'quantity': quantity,
                'last_updated_by': session.get('staff_id'),
                'updated_at': datetime.now().isoformat()
            }).eq('blood_type', blood_type).execute()
        else:
            response = supabase.table('inventory').insert({
                'blood_type': blood_type,
                'quantity': quantity,
                'last_updated_by': session.get('staff_id'),
                'updated_at': datetime.now().isoformat()
            }).execute()
        
        return jsonify({'success': True, 'message': 'Inventory updated successfully'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/staff/donors', methods=['GET'])
@role_required('staff')
def donor_list():
    try:
        response = supabase.table('donors').select('*').order('donor_name').execute()
        donors = response.data
        
        for donor in donors:
            if not donor.get('email') and donor.get('user_id'):
                try:
                    user_response = supabase.table('users').select('email').eq('id', donor['user_id']).execute()
                    if user_response.data:
                        donor['email'] = user_response.data[0]['email']
                except:
                    donor['email'] = 'No email'
        
        return render_template('donor_list.html', donors=donors)
        
    except Exception as e:
        flash('Error loading donor list', 'error')
        return render_template('donor_list.html', donors=[])

@app.route('/staff/donors/add', methods=['POST'])
@role_required('staff')
def add_donor():
    try:
        data = request.get_json()
        
        donor_name = data.get('donor_name')
        email = data.get('email')
        age = data.get('age')
        blood_type = data.get('blood_type')
        eligibility_status = data.get('eligibility_status') == 'true'
        medical_history = data.get('medical_history', '')
        
        if not all([donor_name, email, blood_type]):
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400
        
        existing_donor = supabase.table('donors').select('*').eq('email', email).execute()
        if existing_donor.data:
            return jsonify({'success': False, 'error': 'Donor with this email already exists'}), 400
        
        existing_user = supabase.table('users').select('*').eq('email', email).execute()
        
        user_id = None
        if existing_user.data:
            user_id = existing_user.data[0]['id']
        else:
            temp_password = "TempPassword123"
            password_hash = hash_password(temp_password)
            
            user_response = supabase.table('users').insert({
                'email': email,
                'password': password_hash,
                'role': 'donor',
                'created_at': datetime.now().isoformat()
            }).execute()
            
            user_id = user_response.data[0]['id']
        
        donor_data = {
            'user_id': user_id,
            'donor_name': donor_name,
            'email': email,
            'blood_type': blood_type,
            'eligibility_status': eligibility_status,
            'medical_history': medical_history,
            'disqualification_reason': '' if eligibility_status else 'Pending verification',
            'created_at': datetime.now().isoformat()
        }
        
        if age and int(age) > 0:
            donor_data['age'] = int(age)
        
        donor_response = supabase.table('donors').insert(donor_data).execute()
        
        return jsonify({
            'success': True, 
            'message': 'Donor added successfully!',
            'donor_id': donor_response.data[0]['id'] if donor_response.data else None
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/staff/requests', methods=['GET'])
@role_required('staff')
def view_requests():
    try:
        response = supabase.table('urgent_request').select('*').order('requested_at', desc=True).execute()
        requests = response.data
        
        return render_template('view_requests.html', requests=requests)
        
    except Exception as e:
        flash('Error loading urgent requests', 'error')
        return render_template('view_requests.html', requests=[])

@app.route('/staff/requests/create', methods=['GET', 'POST'])
@role_required('staff')
def create_request():
    staff_id = session.get('staff_id')
    hospital_name = 'City General Hospital'
    
    if staff_id:
        try:
            staff_response = supabase.table('staff').select('*').eq('id', staff_id).execute()
            if staff_response.data:
                hospital_name = staff_response.data[0].get('hospital_name', 'City General Hospital')
        except Exception as e:
            pass
    
    if request.method == 'GET':
        blood_types = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']
        urgency_levels = ['High', 'Medium', 'Low']
        
        current_datetime = datetime.now().strftime("%Y-%m-%dT%H:%M")
        
        return render_template('urgent_request.html',
                             blood_types=blood_types,
                             urgency_levels=urgency_levels,
                             hospital_name=hospital_name,
                             current_datetime=current_datetime)
    
    elif request.method == 'POST':
        try:
            blood_type = request.form.get('blood_type')
            units_needed = int(request.form.get('units_needed', 0))
            urgency_level = request.form.get('urgency_level')
            notes = request.form.get('notes', '')
            
            if not all([blood_type, units_needed, urgency_level]):
                flash('Please fill in all required fields', 'error')
                return redirect(url_for('create_request'))
            
            response = supabase.table('urgent_request').insert({
                'blood_type': blood_type,
                'units_needed': units_needed,
                'urgency_level': urgency_level,
                'notes': notes,
                'handled_by': session.get('staff_id'),
                'hospital_name': hospital_name,
                'status': 'Pending',
                'requested_at': datetime.now().isoformat()
            }).execute()
            
            flash('Urgent blood request created successfully!', 'success')
            return redirect(url_for('view_requests'))
            
        except Exception as e:
            flash('Error creating urgent request', 'error')
            return redirect(url_for('create_request'))
        
@app.route('/staff/donors/toggle-eligibility', methods=['POST'])
@role_required('staff')
def toggle_donor_eligibility():
    try:
        data = request.get_json()
        donor_id = data.get('donor_id')
        new_status = data.get('new_status')
        
        if not donor_id or new_status is None:
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400
        
        update_data = {
            'eligibility_status': new_status
        }
        
        if not new_status:
            update_data['disqualification_reason'] = 'Manually disqualified by staff'
        
        response = supabase.table('donors').update(update_data).eq('id', donor_id).execute()
        
        if response.data:
            return jsonify({'success': True, 'message': 'Donor eligibility updated'})
        else:
            return jsonify({'success': False, 'error': 'Donor not found'}), 404
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    
@app.route('/staff/donors/<donor_id>', methods=['GET'])
@role_required('staff')
def get_donor_details(donor_id):
    try:
        response = supabase.table('donors').select('*').eq('id', donor_id).execute()
        if response.data:
            donor = response.data[0]
            return jsonify({'success': True, 'donor': donor})
        else:
            return jsonify({'success': False, 'error': 'Donor not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    
@app.route('/staff/donors/<donor_id>/update', methods=['POST'])
@role_required('staff')
def update_donor(donor_id):
    try:
        data = request.get_json()
        
        update_data = {}
        if 'donor_name' in data:
            update_data['donor_name'] = data['donor_name']
        if 'blood_type' in data:
            update_data['blood_type'] = data['blood_type']
        if 'age' in data and data['age']:
            update_data['age'] = int(data['age'])
        
        response = supabase.table('donors').update(update_data).eq('id', donor_id).execute()
        
        if response.data:
            return jsonify({'success': True, 'message': 'Donor updated'})
        else:
            return jsonify({'success': False, 'error': 'Donor not found'}), 404
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/staff/requests/<int:request_id>/fulfill', methods=['POST'])
@role_required('staff')
def fulfill_request(request_id):
    try:
        response = supabase.table('urgent_request').update({
            'status': 'Fulfilled',
            'handled_by': session.get('staff_id')
        }).eq('id', request_id).execute()
        
        if response.data:
            return jsonify({'success': True, 'message': 'Request fulfilled successfully'})
        else:
            return jsonify({'success': False, 'error': 'Request not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/staff/requests/<int:request_id>/cancel', methods=['POST'])
@role_required('staff')
def cancel_request(request_id):
    try:
        response = supabase.table('urgent_request').update({
            'status': 'Cancelled',
            'handled_by': session.get('staff_id')
        }).eq('id', request_id).execute()
        
        if response.data:
            return jsonify({'success': True, 'message': 'Request cancelled successfully'})
        else:
            return jsonify({'success': False, 'error': 'Request not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/staff/requests/<int:request_id>/notify', methods=['POST'])
@role_required('staff')
def notify_donors(request_id):
    try:
        request_response = supabase.table('urgent_request').select('*').eq('id', request_id).execute()
        if not request_response.data:
            return jsonify({'success': False, 'error': 'Request not found'}), 404
        
        request_data = request_response.data[0]
        blood_type = request_data['blood_type']
        
        donors_response = supabase.table('donors').select('*').eq('blood_type', blood_type).eq('eligibility_status', True).execute()
        
        print(f"Would notify {len(donors_response.data)} donors for blood type {blood_type}")
        
        return jsonify({
            'success': True, 
            'message': f'Notification sent to {len(donors_response.data)} matching donors',
            'donors_notified': len(donors_response.data)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    
@app.route('/staff/requests/<request_id>', methods=['GET'])
@role_required('staff')
def get_request_details(request_id):
    try:
        try:
            request_id_int = int(request_id)
            response = supabase.table('urgent_request').select('*').eq('id', request_id_int).execute()
        except ValueError:
            response = supabase.table('urgent_request').select('*').eq('id', request_id).execute()
        
        if response.data and len(response.data) > 0:
            request_data = response.data[0]
            
            if request_data.get('handled_by'):
                staff_response = supabase.table('staff').select('*').eq('id', request_data['handled_by']).execute()
                if staff_response.data:
                    request_data['staff_name'] = staff_response.data[0].get('staff_name', 'Staff')
                    request_data['hospital_name'] = staff_response.data[0].get('hospital_name', 'City General Hospital')
                else:
                    request_data['staff_name'] = session.get('staff_name', 'Staff')
                    request_data['hospital_name'] = session.get('hospital_name', 'City General Hospital')
            else:
                request_data['staff_name'] = session.get('staff_name', 'Staff')
                request_data['hospital_name'] = session.get('hospital_name', 'City General Hospital')
            
            return jsonify({'success': True, 'request': request_data})
        else:
            return jsonify({'success': False, 'error': 'Request not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ========== ADMIN ROUTES ==========
@app.route('/admin/dashboard')
@role_required('admin')
def admin_dashboard():
    return render_template('admin_dashboard.html')

if __name__ == '__main__':
    print("=== BloodLink Portal ===")
    print("Starting server...")
    print("Open your browser to: http://localhost:5000")
    print("=" * 40)
    app.run(debug=True, port=5000)
