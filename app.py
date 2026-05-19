from flask import Flask, render_template, request, redirect, session, Response, jsonify
import os
from glob import glob
from datetime import datetime, timedelta
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import csv
import io
import hashlib
import json
import re
from collections import Counter
import firebase_admin
from firebase_admin import credentials, db

# ================= INIT =================

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "supersecretkey")
app.permanent_session_lifetime = timedelta(hours=2)

# ================= FIREBASE =================

if not firebase_admin._apps:
    base_path = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(base_path, "firebase.json")

    try:
        cred = credentials.Certificate(json_path)
        firebase_admin.initialize_app(cred, {
            "databaseURL":'https://bug-severity-project-default-rtdb.firebaseio.com'
        })
    except Exception as e:
        print("Firebase Error:", e)

# ================= PASSWORD HASH =================

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# ================= DEFAULT USERS =================

DEFAULT_USERS = {
    "admin": {
        "password": hash_password("admin123"),
        "role": "Admin",
        "email": "admin@bugtracker.com",
        "name": "Admin User"
    },
    "developer": {
        "password": hash_password("dev123"),
        "role": "Developer",
        "email": "dev@bugtracker.com",
        "name": "Developer User"
    },
    "tester": {
        "password": hash_password("test123"),
        "role": "Tester",
        "email": "tester@bugtracker.com",
        "name": "Tester User"
    }
}

# ================= USERS =================

def get_users():
    try:
        ref = db.reference("users")
        users = ref.get()

        if not users:
            ref.set(DEFAULT_USERS)
            return DEFAULT_USERS

        return users

    except:
        return DEFAULT_USERS

def get_user(username):
    users = get_users()
    return users.get(username)

# ================= AI CLASSIFIER =================

def ai_classify_bug(bug_description):

    bug = bug_description.lower()

    high_keywords = [
        "crash", "critical", "server down",
        "database down", "security", "hack"
    ]

    medium_keywords = [
        "error", "timeout", "slow response",
        "login issue", "cannot"
    ]

    low_keywords = [
        "ui", "design", "alignment",
        "typo", "color"
    ]

    score = 0
    matched = []

    for word in high_keywords:
        if word in bug:
            score += 5
            matched.append(word)

    for word in medium_keywords:
        if word in bug:
            score += 3
            matched.append(word)

    for word in low_keywords:
        if word in bug:
            score += 1
            matched.append(word)

    if score >= 8:
        severity = "High"
        confidence = 90
        suggestion = "Critical issue detected."
        color = "danger"

    elif score >= 4:
        severity = "Medium"
        confidence = 75
        suggestion = "Needs developer review."
        color = "warning"

    else:
        severity = "Low"
        confidence = 60
        suggestion = "Minor issue."
        color = "success"

    tags = []

    if "ui" in bug:
        tags.append("Frontend")

    if "database" in bug:
        tags.append("Database")

    if "server" in bug:
        tags.append("Backend")

    if not tags:
        tags.append("General")

    return {
        "severity": severity,
        "confidence": confidence,
        "suggestion": suggestion,
        "tags": tags,
        "matched_keywords": matched,
        "color": color
    }

# ================= FIREBASE HELPERS =================

def save_bug(bug, severity, suggestion, confidence, tags, username):

    ref = db.reference("bugs")

    ref.push({
        "bug": bug,
        "severity": severity,
        "suggestion": suggestion,
        "confidence": confidence,
        "tags": tags,
        "status": "Open",
        "priority": "P2",
        "submitted_by": username,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

def get_all_bugs():

    ref = db.reference("bugs")
    return ref.get() or {}

def get_bug_counts():

    data = get_all_bugs()

    count = {
        "High": 0,
        "Medium": 0,
        "Low": 0
    }

    for item in data.values():

        sev = item.get("severity", "")

        if sev in count:
            count[sev] += 1

    return count

# ================= CHART =================

def create_pie_chart(count):

    if not os.path.exists("static"):
        os.makedirs("static")

    labels = ["High", "Medium", "Low"]

    values = [
        count.get("High", 0),
        count.get("Medium", 0),
        count.get("Low", 0)
    ]

    if sum(values) == 0:
        values = [1, 1, 1]

    colors = ["red", "orange", "green"]

    plt.figure(figsize=(5, 5))

    plt.pie(
        values,
        labels=labels,
        autopct='%1.1f%%',
        colors=colors
    )

    plt.title("Bug Severity")

    for old in glob("static/pie*.png"):
        os.remove(old)

    import time
    ts = int(time.time())

    filename = f"pie_{ts}.png"

    plt.savefig(f"static/{filename}")
    plt.close()

    return filename

# ================= HOME =================

@app.route('/')
def home():
    return render_template("login.html")

# ================= LOGIN =================

@app.route('/login', methods=['POST'])
def login():

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()

    if not username or not password:
        return render_template(
            "login.html",
            error="Enter Username and Password"
        )

    user = get_user(username)

    if user and user["password"] == hash_password(password):

        session.permanent = True
        session["user"] = username
        session["role"] = user["role"]
        session["name"] = user["name"]

        return redirect('/dashboard')

    return render_template(
        "login.html",
        error="Invalid Username or Password"
    )

# ================= DASHBOARD =================

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():

    if 'user' not in session:
        return redirect('/')

    result = None
    ai_result = None

    if request.method == 'POST':

        bug = request.form.get("bug", "").strip()

        if bug:

            ai_result = ai_classify_bug(bug)

            result = ai_result["severity"]

            save_bug(
                bug,
                ai_result["severity"],
                ai_result["suggestion"],
                ai_result["confidence"],
                ai_result["tags"],
                session["user"]
            )

    count = get_bug_counts()

    total = sum(count.values())

    chart = create_pie_chart(count)

    data = get_all_bugs()

    recent_bugs = []

    for key, item in data.items():
        item["id"] = key
        recent_bugs.append(item)

    recent_bugs = sorted(
        recent_bugs,
        key=lambda x: x.get("time", ""),
        reverse=True
    )[:5]

    return render_template(
        "dashboard.html",
        result=result,
        ai_result=ai_result,
        count=count,
        total=total,
        chart=chart,
        recent_bugs=recent_bugs,
        username=session.get("name"),
        role=session.get("role")
    )

# ================= HISTORY =================

@app.route('/history')
def history():

    if 'user' not in session:
        return redirect('/')

    data = get_all_bugs()

    return render_template(
        "history.html",
        data=data,
        role=session.get("role")
    )

# ================= LOGOUT =================

@app.route('/logout')
def logout():

    session.clear()

    return redirect('/')

# ================= ERROR HANDLERS =================

@app.errorhandler(404)
def page_not_found(e):
    return "404 Page Not Found", 404

@app.errorhandler(500)
def internal_server_error(e):
    return "500 Internal Server Error", 500

# ================= RUN =================

if __name__ == "__main__
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000))
    )


















