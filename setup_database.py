import os
from supabase import create_client, Client
from dotenv import load_dotenv
import hashlib
from datetime import datetime, timedelta

# Load environment variables
load_dotenv()

# Initialize Supabase client
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

def hash_password(password: str) -> str:
    """Hash password using SHA256"""
    return hashlib.sha256(password.encode()).hexdigest()

def setup_database():
    print("=== Setting up BloodLink Database ===\n")
    
    # Check connection
    try:
        print("1. Testing Supabase connection...")
        response = supabase.table('users').select('*').limit(1).execute()
        print("   ✓ Connection successful")
    except Exception as e:
        print(f"   ✗ Connection failed: {e}")
        print("   Make sure SUPABASE_URL and SUPABASE_KEY are correct in .env file")
        return
    
    print("\n2. Creating test users...")
    
    # Create hospital staff user
    staff_data = {
        'email': 'staff@bloodlink.com',
        'password': hash_password('hospital123'),
        'role': 'staff'
    }
    
    try:
        # Insert staff user
        response = supabase.table('users').upsert(staff_data).execute()
        if response.data:
            staff_user_id = response.data[0]['id']
            print(f"   ✓ Staff user created: staff@bloodlink.com")
            
            # Create staff profile
            staff_profile = {
                'user_id': staff_user_id,
                'staff_name': 'Hospital Administrator',
                'hospital_name': 'City General Hospital'
            }
            supabase.table('staff').upsert(staff_profile).execute()
            print(f"   ✓ Staff profile created")
    except Exception as e:
        print(f"   ✗ Error creating staff: {e}")
    
    print("\n3. Creating sample donors...")
    
    # Sample donor data
    donors = [
        {
            'donor_name': 'John Smith',
            'blood_type': 'A+',
            'age': 30,
            'eligibility_status': True,
            'medical_history': 'No significant medical history',
            'email': 'john@example.com',
            'password': hash_password('donor123')
        },
        {
            'donor_name': 'Mary Johnson',
            'blood_type': 'O-',
            'age': 28,
            'eligibility_status': True,
            'medical_history': 'Mild allergy to penicillin',
            'email': 'mary@example.com',
            'password': hash_password('donor123')
        },
        {
            'donor_name': 'Robert Chen',
            'blood_type': 'B+',
            'age': 45,
            'eligibility_status': False,
            'medical_history': 'High blood pressure',
            'disqualification_reason': 'Blood pressure above acceptable limit',
            'email': 'robert@example.com',
            'password': hash_password('donor123')
        }
    ]
    
    for i, donor_data in enumerate(donors, 1):
        try:
            # Create user account for donor
            user_data = {
                'email': donor_data['email'],
                'password': donor_data['password'],
                'role': 'donor'
            }
            
            response = supabase.table('users').upsert(user_data).execute()
            if response.data:
                user_id = response.data[0]['id']
                
                # Create donor profile
                donor_profile = {
                    'user_id': user_id,
                    'donor_name': donor_data['donor_name'],
                    'blood_type': donor_data['blood_type'],
                    'age': donor_data['age'],
                    'eligibility_status': donor_data['eligibility_status'],
                    'medical_history': donor_data.get('medical_history', ''),
                    'disqualification_reason': donor_data.get('disqualification_reason')
                }
                
                supabase.table('donors').upsert(donor_profile).execute()
                print(f"   ✓ Donor {i}: {donor_data['donor_name']} created")
        except Exception as e:
            print(f"   ✗ Error creating donor {i}: {e}")
    
    print("\n4. Initializing blood inventory...")
    
    blood_types = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']
    
    for blood_type in blood_types:
        try:
            inventory_data = {
                'blood_type': blood_type,
                'quantity': 25 if blood_type == 'O+' else 15,  # More O+ stock
                'last_updated_by': None
            }
            
            supabase.table('inventory').upsert(inventory_data).execute()
            print(f"   ✓ {blood_type}: {inventory_data['quantity']} units")
        except Exception as e:
            print(f"   ✗ Error creating inventory for {blood_type}: {e}")
    
    print("\n5. Creating sample urgent request...")
    
    try:
        # Get staff ID for created_by field
        staff_response = supabase.table('staff').select('id').limit(1).execute()
        if staff_response.data:
            staff_id = staff_response.data[0]['id']
            
            request_data = {
                'blood_type': 'O-',
                'units_needed': 5,
                'urgency_level': 'High',
                'status': 'Pending',
                'notes': 'Emergency surgery for trauma patient',
                'handled_by': staff_id,
                'requested_at': datetime.now().isoformat()
            }
            
            supabase.table('urgent_request').upsert(request_data).execute()
            print(f"   ✓ Sample urgent request created")
    except Exception as e:
        print(f"   ✗ Error creating urgent request: {e}")

    print("\n6. Creating sample events and organizers...")

    try:
        org_user = {
            'email': 'organizer@bloodlink.com',
            'password': hash_password('org123'),
            'role': 'organizer'
        }
        org_response = supabase.table('users').upsert(org_user).execute()
        
        if org_response.data:
            org_user_id = org_response.data[0]['id']
            
            # Create organizer profile
            org_profile = {
                'user_id': org_user_id,
                'organiser_name': 'Event Coordinator'
            }
            supabase.table('event_organisers').upsert(org_profile).execute()
            
            # Create sample event
            sample_event = {
                'event_name': 'Community Blood Drive - January 2026',
                'event_date': '2026-01-30',
                'event_time': '10:00:00',
                'event_venue': 'City Hall Main Auditorium',
                'event_description': 'Monthly community blood donation drive',
                'event_status': 'Upcoming',
                'created_by': org_user_id
            }
            supabase.table('events').upsert(sample_event).execute()
            print("   ✓ Sample event organizer and event created")
    except Exception as e:
        print(f"   ✗ Error creating organizer/event: {e}")
    
    print("\n7. Creating admin user...")
    
    try:
        admin_user = {
            'email': 'admin@bloodlink.com',
            'password': hash_password('admin123'),
            'role': 'admin'
        }
        admin_response = supabase.table('users').upsert(admin_user).execute()
        
        if admin_response.data:
            admin_user_id = admin_response.data[0]['id']
            
            admin_profile = {
                'user_id': admin_user_id,
                'admin_name': 'System Administrator'
            }
            supabase.table('administrators').upsert(admin_profile).execute()
            print("   ✓ Admin user created")
    except Exception as e:
        print(f"   ✗ Error creating admin: {e}")
    
    print("\n=== Database Setup Complete! ===")
    print("\nTest Credentials:")
    print("  Staff Login: staff@bloodlink.com / hospital123")
    print("  Access the application at: http://localhost:5000")

if __name__ == '__main__':
    setup_database()