from flask import Flask, render_template, request, redirect, session, url_for
from werkzeug.utils import secure_filename
import os
import random
import sqlite3
import pandas as pd
import uuid

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, "database.db")
CSV_PATH = os.path.join(BASE_DIR, "ESC 12 Pavement Dataset.csv")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = "road_project"

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


def init_db():
    conn = sqlite3.connect(DATABASE_PATH)
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        password TEXT
        )
    ''')
    conn.commit()
    conn.close()


init_db()

try:
    predictions_df = pd.read_csv(CSV_PATH)
    print("Dataset loaded successfully with", len(predictions_df), "records")
except Exception as e:
    print("CSV not found:", e)
    predictions_df = None


def get_road_condition_from_pci(pci):
    if pci >= 85:
        return "Excellent"
    elif pci >= 70:
        return "Good"
    elif pci >= 55:
        return "Fair"
    elif pci >= 40:
        return "Poor"
    else:
        return "Very Poor"


def get_crack_severity(iri, rutting):
    avg_issue = (iri + rutting) / 2
    if avg_issue < 2:
        return "Low"
    elif avg_issue < 3:
        return "Medium"
    elif avg_issue < 4:
        return "High"
    else:
        return "Critical"


def get_repair_summary(row):
    pci = row.get("PCI", 50)
    iri = row.get("IRI", 2.0)
    rutting = row.get("Rutting", 15.0)

    summary = []
    if iri > 2.5:
        summary.append(f"CRACK REPAIR: IRI {iri:.2f}")
    if rutting > 18:
        summary.append(f"POTHOLE REPAIR: {rutting:.2f}mm")

    condition = get_road_condition_from_pci(pci)
    summary.append(f"CONDITION: {condition}")
    return "\n".join(summary)


@app.route('/')
def home():
    return render_template('login.html')


@app.route('/login', methods=['GET'])
def login_page():
    return render_template(
        'login.html',
        error=request.args.get('error'),
        info=request.args.get('info')
    )


@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']

    conn = sqlite3.connect(DATABASE_PATH)
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
    user = cur.fetchone()
    conn.close()

    if user:
        session['user'] = username
        return redirect(url_for('dashboard'))

    return render_template(
        'login.html',
        error="Invalid username or password.",
        info=None
    )


@app.route('/auth/<provider>')
def social_login(provider):
    allowed_providers = {
        'google': 'Google',
        'facebook': 'Facebook',
    }

    if provider not in allowed_providers:
        return redirect(url_for('login_page', error="Unsupported social login option."))

    session['user'] = f"{provider}_user"
    return redirect(url_for('dashboard', info=f"Signed in with {allowed_providers[provider]}."))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form.get('confirm_password', '')

        if password != confirm_password:
            return render_template('register.html', error="Passwords do not match.")

        conn = sqlite3.connect(DATABASE_PATH)
        cur = conn.cursor()
        cur.execute("INSERT INTO users(username,password) VALUES (?,?)", (username, password))
        conn.commit()
        conn.close()
        return redirect(url_for('login_page'))

    return render_template('register.html', error=None)


@app.route('/dashboard')
def dashboard():
    if 'user' in session:
        return render_template('dashboard.html', info=request.args.get('info'))
    return redirect(url_for('login_page'))


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))


@app.route('/history')
def history():
    if 'user' not in session:
        return redirect(url_for('login_page'))
    return render_template('history.html', history=session.get('history', []))


@app.route('/predict', methods=['POST'])
def predict():
    if 'user' not in session:
        return redirect(url_for('login_page'))

    image_url = None
    if 'image' in request.files:
        image = request.files['image']
        if image.filename:
            filename = f"{uuid.uuid4()}_{secure_filename(image.filename)}"
            path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image.save(path)
            image_url = url_for('static', filename=f'uploads/{filename}')

    if predictions_df is not None and not predictions_df.empty:
        row = predictions_df.sample(n=1).iloc[0]
        pci = float(row.get("PCI", 50))
        iri = float(row.get("IRI", 2.0))
        rutting = float(row.get("Rutting", 15.0))

        road_condition = get_road_condition_from_pci(pci)
        severity = get_crack_severity(iri, rutting)
        maintenance = "Immediate" if row.get("Needs Maintenance") == 1 else "Routine"
        priority = severity
        confidence = round(min(98, 75 + (abs(100 - pci) / 100 * 20)), 2)
        segment_id = row.get("Segment ID", "Unknown")
        road_type = row.get("Road Type", "Unknown")
        repair_summary = get_repair_summary(row)
    else:
        road_condition = random.choice(["Good", "Moderate", "Poor"])
        severity = random.choice(["Low", "Medium", "High"])
        maintenance = random.choice(["Routine", "Repair", "Immediate"])
        priority = random.choice(["Low", "Medium", "High"])
        confidence = round(random.uniform(75, 98), 2)
        repair_summary = "Demo prediction"
        segment_id = "DEMO"
        road_type = "Demo"

    history = session.get('history', [])
    history.insert(0, {
        'timestamp': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S'),
        'condition': road_condition,
        'severity': severity,
        'maintenance': maintenance,
        'priority': priority,
        'confidence': confidence,
    })
    session['history'] = history[:20]

    return render_template(
        'prediction.html',
        condition=road_condition,
        severity=severity,
        maintenance=maintenance,
        priority=priority,
        confidence=confidence,
        detail=repair_summary,
        image_url=image_url,
        segment_id=segment_id,
        road_type=road_type,
    )


if __name__ == "__main__":
    app.run(debug=True)
