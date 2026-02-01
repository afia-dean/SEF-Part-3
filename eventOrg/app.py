from flask import Flask, render_template, request, redirect, url_for
from supabase import create_client, Client
import os
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

# Initialize Supabase
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(url, key)

# --- UC8: Monitor Registrations ---
@app.route('/')
def index():
    try:
        # Fetch data for the dashboard
        events = supabase.table('events').select("*").execute()
        # Ensure your table name matches 'registrations'
        regs = supabase.table('registrations').select("*, events(title)").execute()
        return render_template('organizer_dashboard.html', 
                               events=events.data, 
                               registrations=regs.data)
    except Exception as e:
        return f"Database Error: {e}. Check if tables 'events' and 'registrations' exist.", 500

# --- UC7: Create Event ---
@app.route('/create', methods=['POST'])
def create_event():
    data = {
        "title": request.form.get('title'),
        "date": request.form.get('date'),
        "location": request.form.get('location')
    }
    supabase.table('events').insert(data).execute()
    return redirect(url_for('index'))

# --- UC10: Manage Attendance ---
@app.route('/status/<int:reg_id>/<status>')
def update_status(reg_id, status):
    supabase.table('registrations').update({"status": status}).eq("id", reg_id).execute()
    return redirect(url_for('index'))

# --- UC9: Generate Report ---
@app.route('/report/<int:event_id>')
def generate_report(event_id):
    event_data = supabase.table('events').select("*").eq("id", event_id).single().execute()
    attendee_data = supabase.table('registrations').select("*").eq("event_id", event_id).execute()
    
    total = len(attendee_data.data)
    present = sum(1 for a in attendee_data.data if a['status'] == 'Attended')
    
    return render_template('event_report.html', 
                           event=event_data.data, 
                           attendees=attendee_data.data, 
                           total=total, 
                           present=present)

if __name__ == '__main__':
    # Using Port 5005 to ensure a fresh connection
    app.run(debug=True, port=5005)