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
                    flash('Login successful!', 'success')
                    return redirect(url_for('organizer_dashboard'))
                elif user['role'] == 'admin':
                    flash('Login successful!', 'success')
                    return redirect(url_for('admin_dashboard'))
            else:
                flash('Invalid email or password', 'error')
                
        except Exception as e:
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
def staff_dashboard():
    if 'user_id' not in session or session.get('role') != 'staff':
        return redirect(url_for('login'))
    
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
def donor_dashboard():
    if 'user_id' not in session or session.get('role') != 'donor':
        return redirect(url_for('login'))
    
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
                                'check_in_time': registration.get('registered_at')  # Use registered_at for display
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

def donor_appointment():
    if 'user_id' not in session or session.get('role') != 'donor':
        return redirect(url_for('login'))
    
    try:
        donor_response = supabase.table('donors').select('*').eq('user_id', session['user_id']).execute()
        if not donor_response.data:
            flash('Donor record not found', 'error')
            return redirect(url_for('logout'))
        
        donor = donor_response.data[0]
        
        # Get UPCOMING events from events table
        today = datetime.now().date().isoformat()
        events_response = supabase.table('events')\
            .select('*')\
            .gte('event_date', today)\
            .eq('status', 'Upcoming')\
            .order('event_date')\
            .execute()
        
        events = events_response.data if events_response.data else []
        
        # Get existing registrations
        profile_response = supabase.table('profiles').select('*').eq('id', session['user_id']).execute()
        
        registered_event_ids = []
        if profile_response.data:
            profile = profile_response.data[0]
            registrations_response = supabase.table('registrations')\
                .select('event_id')\
                .eq('donor_id', profile['id'])\
                .execute()
            
            if registrations_response.data:
                registered_event_ids = [reg['event_id'] for reg in registrations_response.data]
        
        # Mark which events user is already registered for
        for event in events:
            event['already_registered'] = event['id'] in registered_event_ids
        
        if request.method == 'POST':
            try:
                data = request.get_json()
                event_id = data.get('event_id')
                
                if not event_id:
                    return jsonify({'success': False, 'error': 'Event ID required'}), 400
                
                if not profile_response.data:
                    return jsonify({'success': False, 'error': 'Profile not found'}), 400
                
                profile = profile_response.data[0]
                
                # Check if already registered
                existing_registration = supabase.table('registrations')\
                    .select('*')\
                    .eq('donor_id', profile['id'])\
                    .eq('event_id', event_id)\
                    .execute()
                
                if existing_registration.data:
                    return jsonify({'success': False, 'error': 'Already registered for this event'}), 400
                
                # Create registration
                registration_response = supabase.table('registrations').insert({
                    'donor_id': profile['id'],
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
        print(f"Error loading appointments: {e}")
        flash('Error loading appointments', 'error')
        return redirect(url_for('donor_dashboard'))
    
@app.route('/donor/appointment', methods=['GET', 'POST'])
def donor_appointment():
    if 'user_id' not in session or session.get('role') != 'donor':
        return redirect(url_for('login'))
    
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
                    'donor_id': session['user_id'],  # This is users.id
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
def donor_eligibility():
    if 'user_id' not in session or session.get('role') != 'donor':
        return redirect(url_for('login'))
    
    try:
        # Get donor for sidebar
        donor_response = supabase.table('donors').select('*').eq('user_id', session['user_id']).execute()
        
        if not donor_response.data:
            flash('Donor record not found', 'error')
            return redirect(url_for('logout'))
        
        donor = donor_response.data[0]
        
        # Get unread notifications count - handle if table doesn't exist
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
def check_eligibility():
    if 'user_id' not in session or session.get('role') != 'donor':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    
    try:
        donor_response = supabase.table('donors').select('*').eq('user_id', session['user_id']).execute()
        
        if not donor_response.data:
            return jsonify({'success': False, 'error': 'Donor not found'}), 404
        
        donor = donor_response.data[0]
        
        eligible = donor.get('eligibility_status', False)
        reason = donor.get('disqualification_reason', '')
        last_donation = donor.get('last_donation_date')
        
        # Handle date serialization
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
def donor_medical():
    if 'user_id' not in session or session.get('role') != 'donor':
        return redirect(url_for('login'))
    return render_template('medical.html')

@app.route('/donor/medical/get')
def get_medical_info():
    if 'user_id' not in session or session.get('role') != 'donor':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    
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
def save_medical_info():
    if 'user_id' not in session or session.get('role') != 'donor':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    
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
def donor_notifications():
    if 'user_id' not in session or session.get('role') != 'donor':
        return redirect(url_for('login'))
    return render_template('notifications.html')

@app.route('/donor/notifications/all')
def get_donor_notifications():
    if 'user_id' not in session or session.get('role') != 'donor':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    
    try:
        # Get notifications - no created_at column, so we can't order by it
        notifications_response = supabase.table('notifications').select('*').execute()
        
        if notifications_response.data:
            # Format the notifications to match what the template expects
            formatted_notifications = []
            for notification in notifications_response.data:
                formatted_notifications.append({
                    'id': notification.get('id'),
                    'title': 'Notification',
                    'message': notification.get('message', ''),
                    'status': 'read' if notification.get('status') else 'unread',
                    'read': notification.get('status', False),
                    'created_at': datetime.now().isoformat()  # Default value since no timestamp
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
def mark_notification_read():
    if 'user_id' not in session or session.get('role') != 'donor':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    
    try:
        data = request.get_json()
        notification_id = data.get('notification_id')
        
        if not notification_id:
            return jsonify({'success': False, 'error': 'Notification ID required'}), 400
        
        response = supabase.table('notifications').update({
            'status': True  # status column acts as read flag
        }).eq('id', notification_id).execute()
        
        return jsonify({'success': True, 'message': 'Notification marked as read'})
        
    except Exception as e:
        print(f"Error marking notification: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/donor/notifications/mark-all-read', methods=['POST'])
def mark_all_notifications_read():
    if 'user_id' not in session or session.get('role') != 'donor':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    
    try:
        # Mark all notifications as read (set status = True)
        response = supabase.table('notifications').update({
            'status': True
        }).eq('status', False).execute()
        
        return jsonify({'success': True, 'message': 'All notifications marked as read'})
        
    except Exception as e:
        print(f"Error marking all notifications: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/donor/eligibility/check')
def check_donor_eligibility():
    if 'user_id' not in session or session.get('role') != 'donor':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    
    try:
        donor_response = supabase.table('donors').select('*').eq('user_id', session['user_id']).execute()
        
        if not donor_response.data:
            return jsonify({'success': False, 'error': 'Donor not found'}), 404
        
        donor = donor_response.data[0]
        
        eligible = donor.get('eligibility_status', False)
        reason = donor.get('disqualification_reason', '')
        
        response_data = {
            'success': True,
            'eligible': eligible,
            'message': 'You are eligible to donate!' if eligible else 'You are not eligible to donate.',
            'reason': reason if reason else '',
            'last_donation': donor.get('last_donation_date')
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ========== STAFF ROUTES (UNCHANGED) ==========
@app.route('/staff/inventory', methods=['GET'])
def view_inventory():
    if 'user_id' not in session or session.get('role') != 'staff':
        return redirect(url_for('login'))
    
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
def update_inventory():
    if 'user_id' not in session or session.get('role') != 'staff':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    
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
def donor_list():
    if 'user_id' not in session or session.get('role') != 'staff':
        return redirect(url_for('login'))
    
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
def add_donor():
    if 'user_id' not in session or session.get('role') != 'staff':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    
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
def view_requests():
    if 'user_id' not in session or session.get('role') != 'staff':
        return redirect(url_for('login'))
    
    try:
        response = supabase.table('urgent_request').select('*').order('requested_at', desc=True).execute()
        requests = response.data
        
        return render_template('view_requests.html', requests=requests)
        
    except Exception as e:
        flash('Error loading urgent requests', 'error')
        return render_template('view_requests.html', requests=[])

@app.route('/staff/requests/create', methods=['GET', 'POST'])
def create_request():
    if 'user_id' not in session or session.get('role') != 'staff':
        return redirect(url_for('login'))
    
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
def toggle_donor_eligibility():
    if 'user_id' not in session or session.get('role') != 'staff':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    
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
def get_donor_details(donor_id):
    if 'user_id' not in session or session.get('role') != 'staff':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    
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
def update_donor(donor_id):
    if 'user_id' not in session or session.get('role') != 'staff':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    
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
def fulfill_request(request_id):
    if 'user_id' not in session or session.get('role') != 'staff':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    
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
def cancel_request(request_id):
    if 'user_id' not in session or session.get('role') != 'staff':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    
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
def notify_donors(request_id):
    if 'user_id' not in session or session.get('role') != 'staff':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    
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
def get_request_details(request_id):
    if 'user_id' not in session or session.get('role') != 'staff':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    
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

# ========== OTHER ROUTES ==========
@app.route('/organizer/dashboard')
def organizer_dashboard():
    if 'user_id' not in session or session.get('role') != 'organizer':
        return redirect(url_for('login'))
    return render_template('organizer_dashboard.html')

@app.route('/admin/dashboard')
def admin_dashboard():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    return render_template('admin_dashboard.html')

if __name__ == '__main__':
    print("=== BloodLink Portal ===")
    print("Starting server...")
    print("Open your browser to: http://localhost:5000")
    print("=" * 40)
    app.run(debug=True, port=5000)
