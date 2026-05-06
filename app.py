from flask import Flask, render_template, request, redirect, session, Response
import os
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, db
import matplotlib.pyplot as plt
import csv
from io import StringIO

app = Flask(__name__)
app.secret_key = "secret123"

# 🔐 USERS (ROLE SYSTEM)
USERS = {
    "admin": {"password": "1234", "role": "admin"},
    "user1": {"password": "1111", "role": "user"}
}

# ☁️ Firebase setup
cred = credentials.Certificate("firebase.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://bug-severity-project-default-rtdb.firebaseio.com/'
})


# 💾 Save bug
def save_to_cloud(bug, severity, suggestion):
    db.reference("bugs").push({
        "bug": bug,
        "severity": severity,
        "suggestion": suggestion,
        "time": str(datetime.now())
    })


# 📊 LINE GRAPH
def create_graph(count):
    if not os.path.exists("static"):
        os.makedirs("static")

    labels = list(count.keys())
    values = list(count.values())

    plt.figure(figsize=(5,4))
    plt.plot(labels, values, marker='o', linestyle='-', color='blue')

    plt.title("Bug Severity Trend")
    plt.xlabel("Severity")
    plt.ylabel("Count")
    plt.grid(True, linestyle='--', alpha=0.5)

    path = "static/graph.png"
    plt.savefig(path)
    plt.close()

    return path


# 🏠 HOME
@app.route('/')
def home():
    return render_template("login.html")


# 🔐 LOGIN
@app.route('/login', methods=['POST'])
def login():
    username = request.form['username'].strip()
    password = request.form['password'].strip()

    if username in USERS and USERS[username]["password"] == password:
        session['user'] = username
        session['role'] = USERS[username]["role"]
        return redirect('/dashboard')

    return "Invalid Login"


# 🚪 LOGOUT
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')


# 📊 DASHBOARD
@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'user' not in session:
        return redirect('/')

    ref = db.reference("bugs")
    data = ref.get() or {}

    count = {"High": 0, "Medium": 0, "Low": 0}

    for v in data.values():
        if v.get("severity") in count:
            count[v["severity"]] += 1

    result = None
    suggestion = None

    if request.method == 'POST':
        bug = request.form['bug'].lower()

        high = ["crash", "down", "fatal"]
        medium = ["error", "fail", "slow"]

        score = 0

        for w in bug.split():
            if w in high:
                score += 2
            elif w in medium:
                score += 1

        if score >= 2:
            result = "High"
            suggestion = "Critical issue detected"
        elif score == 1:
            result = "Medium"
            suggestion = "Fix errors in code"
        else:
            result = "Low"
            suggestion = "Minor UI improvement"

        save_to_cloud(bug, result, suggestion)

        # refresh counts
        data = db.reference("bugs").get() or {}
        count = {"High": 0, "Medium": 0, "Low": 0}

        for v in data.values():
            if v.get("severity") in count:
                count[v["severity"]] += 1

    graph = create_graph(count)

    return render_template(
        "dashboard.html",
        user=session['user'],
        role=session['role'],
        result=result,
        suggestion=suggestion,
        graph=graph,
        high=count["High"],
        medium=count["Medium"],
        low=count["Low"]
    )


# 📜 HISTORY
@app.route('/history')
def history():
    if 'user' not in session:
        return redirect('/')

    data = db.reference("bugs").get() or {}

    search = request.args.get("search", "").lower()
    filter_type = request.args.get("filter")

    result = {}

    for k, v in data.items():
        if search in v.get("bug", "").lower():
            if not filter_type or v.get("severity") == filter_type:
                result[k] = v

    return render_template("history.html", data=result, role=session.get('role'))


# ❌ DELETE (ADMIN ONLY)
@app.route('/delete/<id>')
def delete(id):
    if session.get('role') != "admin":
        return "Access Denied (Admin Only)"

    db.reference("bugs").child(id).delete()
    return redirect('/history')


# 📥 CSV EXPORT (ADMIN ONLY)
@app.route('/download')
def download():
    if session.get('role') != "admin":
        return "Access Denied (Admin Only)"

    data = db.reference("bugs").get() or {}

    output = StringIO()
    writer = csv.writer(output)

    writer.writerow(["Bug", "Severity", "Suggestion", "Time"])

    for v in data.values():
        writer.writerow([
            v.get("bug", ""),
            v.get("severity", ""),
            v.get("suggestion", ""),
            v.get("time", "")
        ])

    output.seek(0)

    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=bug_report.csv"}
    )


# ▶️ RUN APP
if __name__ == '__main__':
    app.run(debug=True)