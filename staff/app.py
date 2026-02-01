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
                
                if user['role'] == 'staff':
                    staff_response = supabase.table('staff').select('*').eq('user_id', user['id']).execute()
                    
                    if staff_response.data:
                        session['user_id'] = user['id']
                        session['email'] = user['email']
                        session['role'] = user['role']
                        session['staff_id'] = staff_response.data[0]['id']
                        session['staff_name'] = staff_response.data[0]['staff_name']
                        
                        flash('Login successful!', 'success')
                        return redirect(url_for('staff_dashboard'))
                    else:
                        flash('Staff record not found', 'error')
                else:
                    flash('Access denied. Staff login only.', 'error')
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

# ========== DASHBOARD ==========
@app.route('/')
def index():
    if 'user_id' in session:
        if session.get('role') == 'staff':
            return redirect(url_for('staff_dashboard'))
        else:
            return redirect(url_for('login'))
    return redirect(url_for('login'))

@app.route('/staff/dashboard')
def staff_dashboard():
    if 'user_id' not in session or session.get('role') != 'staff':
        return redirect(url_for('login'))
    
    try:
        # Get staff details including hospital name
        staff_response = supabase.table('staff').select('*').eq('user_id', session['user_id']).execute()
        
        if not staff_response.data:
            flash('Staff record not found', 'error')
            return redirect(url_for('logout'))
        
        staff_details = staff_response.data[0]
        hospital_name = staff_details.get('hospital_name', 'Hospital')
        
        # Get inventory stats
        inventory_response = supabase.table('inventory').select('*').execute()
        total_units = sum(item['quantity'] for item in inventory_response.data) if inventory_response.data else 0
        
        # Get pending requests
        requests_response = supabase.table('urgent_request').select('*', count='exact').eq('status', 'Pending').execute()
        pending_requests = len(requests_response.data)
        
        # Get total donors
        donors_response = supabase.table('donors').select('*', count='exact').execute()
        total_donors = len(donors_response.data)
        
    except Exception as e:
        print(f"Error fetching dashboard data: {e}")
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

# ========== INVENTORY ==========
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
        print(f"Error fetching inventory: {e}")
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
        print(f"Error updating inventory: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ========== DONORS ==========
@app.route('/staff/donors', methods=['GET'])
def donor_list():
    if 'user_id' not in session or session.get('role') != 'staff':
        return redirect(url_for('login'))
    
    try:
        # Get donors - use email from donors table since we added it
        response = supabase.table('donors').select('*').order('donor_name').execute()
        donors = response.data
        
        # For donors without email in donors table, try to get from users table
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
        print(f"Error fetching donors: {e}")
        flash('Error loading donor list', 'error')
        return render_template('donor_list.html', donors=[])
    
# ========== DONOR ROUTES ==========
@app.route('/donor/register', methods=['GET', 'POST'])
def donor_register():
    if request.method == 'POST':
        # Implement donor registration
        pass
    return render_template('donor_register.html')

@app.route('/donor/dashboard')
def donor_dashboard():
    if 'user_id' not in session or session.get('role') != 'donor':
        return redirect(url_for('login'))
    return render_template('donor_dashboard.html')

@app.route('/donor/book-appointment', methods=['GET', 'POST'])
def book_appointment():
    # Implement appointment booking
    pass

# ========== ORGANIZER ROUTES ==========
@app.route('/organizer/dashboard')
def organizer_dashboard():
    if 'user_id' not in session or session.get('role') != 'organizer':
        return redirect(url_for('login'))
    return render_template('organizer_dashboard.html')

@app.route('/organizer/create-event', methods=['GET', 'POST'])
def create_event():
    # Implement event creation
    pass

# ========== ADMIN ROUTES ==========
@app.route('/admin/dashboard')
def admin_dashboard():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    return render_template('admin_dashboard.html')

# ========== DONOR ADDITION ==========
@app.route('/staff/donors/add', methods=['POST'])
def add_donor():
    if 'user_id' not in session or session.get('role') != 'staff':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    
    try:
        data = request.get_json()
        
        # Extract form data
        donor_name = data.get('donor_name')
        email = data.get('email')
        age = data.get('age')
        blood_type = data.get('blood_type')
        eligibility_status = data.get('eligibility_status') == 'true'
        medical_history = data.get('medical_history', '')
        
        # Validate required fields
        if not all([donor_name, email, blood_type]):
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400
        
        # Check if donor with this email already exists
        existing_donor = supabase.table('donors').select('*').eq('email', email).execute()
        if existing_donor.data:
            return jsonify({'success': False, 'error': 'Donor with this email already exists'}), 400
        
        # Check if user exists
        existing_user = supabase.table('users').select('*').eq('email', email).execute()
        
        user_id = None
        if existing_user.data:
            user_id = existing_user.data[0]['id']
        else:
            # Create new user account for donor
            temp_password = "TempPassword123"
            password_hash = hash_password(temp_password)
            
            user_response = supabase.table('users').insert({
                'email': email,
                'password': password_hash,
                'role': 'donor',
                'created_at': datetime.now().isoformat()
            }).execute()
            
            user_id = user_response.data[0]['id']
        
        # Create donor record - matching your schema exactly
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
        
        # Add age if provided
        if age and int(age) > 0:
            donor_data['age'] = int(age)
        
        donor_response = supabase.table('donors').insert(donor_data).execute()
        
        return jsonify({
            'success': True, 
            'message': 'Donor added successfully!',
            'donor_id': donor_response.data[0]['id'] if donor_response.data else None
        })
        
    except Exception as e:
        print(f"Error adding donor: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ========== REQUESTS ==========
@app.route('/staff/requests', methods=['GET'])
def view_requests():
    if 'user_id' not in session or session.get('role') != 'staff':
        return redirect(url_for('login'))
    
    try:
        response = supabase.table('urgent_request').select('*').order('requested_at', desc=True).execute()
        requests = response.data
        
        return render_template('view_requests.html', requests=requests)
        
    except Exception as e:
        print(f"Error fetching requests: {e}")
        flash('Error loading urgent requests', 'error')
        return render_template('view_requests.html', requests=[])

@app.route('/staff/requests/create', methods=['GET', 'POST'])
def create_request():
    if 'user_id' not in session or session.get('role') != 'staff':
        return redirect(url_for('login'))
    
    # Get staff's hospital name
    staff_id = session.get('staff_id')
    hospital_name = 'City General Hospital'  # Default
    
    if staff_id:
        try:
            staff_response = supabase.table('staff').select('*').eq('id', staff_id).execute()
            if staff_response.data:
                hospital_name = staff_response.data[0].get('hospital_name', 'City General Hospital')
        except Exception as e:
            print(f"Error fetching staff hospital: {e}")
    
    if request.method == 'GET':
        blood_types = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']
        urgency_levels = ['High', 'Medium', 'Low']
        
        # Get current datetime for the form
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
                'hospital_name': hospital_name,  # Save hospital name with request
                'status': 'Pending',
                'requested_at': datetime.now().isoformat()
            }).execute()
            
            flash('Urgent blood request created successfully!', 'success')
            return redirect(url_for('view_requests'))
            
        except Exception as e:
            print(f"Error creating request: {e}")
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
        
        # Update donor eligibility
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
        print(f"Error toggling eligibility: {e}")
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
        print(f"Error fetching donor details: {e}")
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
        print(f"Error updating donor: {e}")
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
        print(f"Error fulfilling request: {e}")
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
        print(f"Error cancelling request: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/staff/requests/<int:request_id>/notify', methods=['POST'])
def notify_donors(request_id):
    if 'user_id' not in session or session.get('role') != 'staff':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    
    try:
        # Get request details
        request_response = supabase.table('urgent_request').select('*').eq('id', request_id).execute()
        if not request_response.data:
            return jsonify({'success': False, 'error': 'Request not found'}), 404
        
        request_data = request_response.data[0]
        blood_type = request_data['blood_type']
        
        # Find matching donors
        donors_response = supabase.table('donors').select('*').eq('blood_type', blood_type).eq('eligibility_status', True).execute()
        
        # In a real app, you would send notifications here
        # For now, just log and return success
        print(f"Would notify {len(donors_response.data)} donors for blood type {blood_type}")
        
        return jsonify({
            'success': True, 
            'message': f'Notification sent to {len(donors_response.data)} matching donors',
            'donors_notified': len(donors_response.data)
        })
        
    except Exception as e:
        print(f"Error notifying donors: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    
@app.route('/staff/requests/<request_id>', methods=['GET'])
def get_request_details(request_id):
    if 'user_id' not in session or session.get('role') != 'staff':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    
    try:
        # Handle both integer and string IDs
        try:
            request_id_int = int(request_id)
            response = supabase.table('urgent_request').select('*').eq('id', request_id_int).execute()
        except ValueError:
            response = supabase.table('urgent_request').select('*').eq('id', request_id).execute()
        
        if response.data and len(response.data) > 0:
            request_data = response.data[0]
            
            # Get staff details for hospital name
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
        print(f"Error fetching request details: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    print("=== BloodLink Portal ===")
    print("Starting server...")
    print("Open your browser to: http://localhost:5000")
    print("=" * 40)
    app.run(debug=True, port=5000)
