import os
from flask import Flask, render_template
from supabase import create_client, Client

app = Flask(__name__)

# 1. Supabase Configuration
# Replace these with your actual Supabase credentials
SUPABASE_URL = "https://axjhfhjifmctsaddotkr.supabase.co"
SUPABASE_KEY = "sb_publishable_cGnABVgrhWhjKnmGgLAAsA_rIbrulIX"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

@app.route('/')
def index():
    """Renders the main homescreen with the Hero and Cards."""
    return render_template('index.html')

@app.route('/event_details')
def event_details():
    """Fetches event data from Supabase and returns the partial HTML."""
    try:
        # 2. Query the 'events' table for a specific ID
        # Make sure your table in Supabase is named 'events'
        response = supabase.table("events").select("*").eq("id", "0001").execute()

        # 3. Check if data exists; otherwise, provide fallback defaults
        if response.data and len(response.data) > 0:
            event_data = response.data[0]
        else:
            event_data = {
                "name": "Event Not Found",
                "id": "N/A",
                "date": "N/A",
                "location": "N/A",
                "registered_count": 0,
                "verified_count": 0,
                "pending_count": 0
            }
            
        # 4. Pass the 'event' object to the partial
        return render_template('partials/event_details.html', event=event_data)

    except Exception as e:
        print(f"Error connecting to Supabase: {e}")
        return "Database Connection Error", 500

if __name__ == '__main__':
    # Start the Flask development server
    app.run(debug=True)
from flask import Flask, render_template

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/event_details') # Must have the slash /
def event_details():
    return render_template('partials/event_details.html')

if __name__ == '__main__':
    app.run(debug=True)
