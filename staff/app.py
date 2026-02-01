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
        inventory_response = supabase.table('inventory').select('*').execute()
        total_units = sum(item['quantity'] for item in inventory_response.data) if inventory_response.data else 0
        
        requests_response = supabase.table('urgent_request').select('*', count='exact').eq('status', 'Pending').execute()
        pending_requests = len(requests_response.data)
        
        donors_response = supabase.table('donors').select('*', count='exact').execute()
        total_donors = len(donors_response.data)
        
    except Exception as e:
        print(f"Error fetching dashboard data: {e}")
        total_units = 0
        pending_requests = 0
        total_donors = 0
    
    return render_template('staff_dashboard.html', 
                         total_units=total_units,
                         pending_requests=pending_requests,
                         total_donors=total_donors,
                         staff_name=session.get('staff_name', 'Staff'),
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
        response = supabase.table('donors').select('*').order('donor_name').execute()
        donors = response.data
        
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
    
    if request.method == 'GET':
        blood_types = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']
        urgency_levels = ['High', 'Medium', 'Low']
        
        return render_template('urgent_request.html',
                             blood_types=blood_types,
                             urgency_levels=urgency_levels)
    
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
                'status': 'Pending',
                'requested_at': datetime.now().isoformat()
            }).execute()
            
            flash('Urgent blood request created successfully!', 'success')
            return redirect(url_for('view_requests'))
            
        except Exception as e:
            print(f"Error creating request: {e}")
            flash('Error creating urgent request', 'error')
            return redirect(url_for('create_request'))

if __name__ == '__main__':
    print("=== BloodLink Hospital Staff Portal ===")
    print("Starting server...")
    print("Open your browser to: http://localhost:5000")
    print("Login with: staff@bloodlink.com / hospital123")
    print("=" * 40)
    app.run(debug=True, port=5000)
