from flask import Flask, render_template

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('homescreen.html')

@app.route('/event_details') # Must have the slash /
def event_details():
    return render_template('partials/event_details.html')

if __name__ == '__main__':
    app.run(debug=True)