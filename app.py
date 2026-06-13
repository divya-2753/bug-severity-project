from flask import Flask, render_template, request, redirect, session, Response, jsonify
import os
from glob import glob
from datetime import datetime, timedelta
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import csv
import io
import hashlib
import json
import re
from collections import Counter
import firebase_admin
from firebase_admin import credentials, db
 
# ================ INIT ================
 
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", os.urandom(24))
app.permanent_session_lifetime = timedelta(hours=2)
 
# ================ FIREBASE SETUP ================
 
cred = credentials.Certificate("firebase.json")
firebase_admin.initialize_app(cred, {
    'databaseURL':'https://bug-severity-project-default-rtdb.firebaseio.com/' 
})
 
# ================ USERS (Role Based) ================
 
# Password hashing function
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()
 
# Default users (Firebase मध्ये save होतील)
DEFAULT_USERS = {
    "admin": {
        "password": hash_password("py"),
        "role": "Admin",
        "email": "admin@bugtracker.com",
        "name": "Admin User"
    },
    "developer": {
        "password": hash_password("dev123"),
        "role": "Developer",
        "email": "dev@bugtracker.com",
        "name": "Dev User"
    },
    "tester": {
        "password": hash_password("test123"),
        "role": "Tester",
        "email": "tester@bugtracker.com",
        "name": "Tester User"
    }
}
 
def get_users():
    try:
        ref = db.reference("users")
        users = ref.get()
        if not users:
            # पहिल्यांदा default users save करा
            ref.set(DEFAULT_USERS)
            return DEFAULT_USERS
        return users
    except:
        return DEFAULT_USERS
 
def get_user(username):
    users = get_users()
    return users.get(username)
 
# ================ AI CLASSIFICATION ================
 
def ai_classify_bug(bug_description):
    """
    Smart AI Bug Classifier with Confidence Score
    - Keyword based NLP
    - Confidence score calculate करतो
    - Auto tags detect करतो
    - Similar bug check करतो
    """
    bug = bug_description.lower()
    score = 0
    max_score = 0
    tags = []
    matched_keywords = []
 
    # 🔴 High Severity Keywords
    high_keywords = {
        "crash": 5, "down": 5,"not working": 4,"broken": 4, "critical": 5,"urgent": 4,"emergency": 5,"data loss": 5, "security": 5, "hack": 5,"breach": 5,"corrupt": 4,"failure": 4,"failed": 3,"exception": 4, "500": 5, "database down": 5,"server down": 5, "production": 5,
         "otp": 4, "authentication": 5, "login failed": 4, "payment": 5, "transaction": 5, "refund": 4, "gateway": 4, "unauthorized": 5, "access denied": 5,
         "jwt": 4, "token": 4, "session": 4, "memory leak": 5, "deadlock": 5, "race condition": 5, "microservice": 4,"service unavailable": 5, "503": 5, "502": 4, "null pointer": 5, "disk full": 5, "out of memory": 5
    }
    
    # 🟡 Medium Severity Keywords
    medium_keywords = {
        "error": 3, "bug": 2, "wrong": 2, "incorrect": 2,
        "not loading": 3, "timeout": 3, "slow response": 2,
        "404": 2, "400": 2, "login issue": 3, "cannot": 2,
        "unable": 2, "missing": 2, "blank": 2, "empty": 2,
        "profile": 2, "notification": 2, "email": 2, "report": 2,
        "export": 2, "upload": 2, "download": 2, "api issue": 3, "dashboard": 2,
    }
 
    # 🟢 Low Severity Keywords
    low_keywords = {
        "slow": 1, "ui": 1, "design": 1, "color": 1,
        "spelling": 1, "typo": 1, "alignment": 1, "minor": 1,
        "cosmetic": 1, "suggestion": 1, "improvement": 1, "layout": 1,
        "spacing": 1, "font": 1, "icon": 1, "responsive": 1, "theme": 1,
    }
 
    # 🏷️ Auto Tags
    tag_keywords = {
        "Frontend": ["ui", "css", "html", "design", "button", "page", "screen", "display", "color", "font", "layout"],
        "Backend": ["api", "server", "database", "query", "function", "logic", "python", "flask", "code", "backend"],
        "Database": ["database", "db", "sql", "firebase", "query", "data", "record", "table", "storage"],
        "Network": ["network", "internet", "connection", "timeout", "slow", "request", "response", "api"],
        "Security": ["security", "hack", "breach", "password", "login", "auth", "access", "permission"],
        "Performance": ["slow", "lag", "speed", "performance", "memory", "cpu", "load", "response time"],
        "Authentication": [ "login","logout","otp", "password","authentication","jwt","token","session","sso"],
        "Payment": ["payment","transaction", "refund","billing", "checkout","gateway","upi"],
        "API": ["api","endpoint","service","microservice"],
        "Reporting": ["report","dashboard","analytics","chart","graph","export"],
        "File Handling": ["upload","download","pdf","csv","file"]
    }
 
    # Score calculate करा
    for keyword, weight in high_keywords.items():
        if keyword in bug:
            score += weight
            max_score += weight
            matched_keywords.append(keyword)
 
    for keyword, weight in medium_keywords.items():
        if keyword in bug:
            score += weight
            max_score += weight
            matched_keywords.append(keyword)
 
    for keyword, weight in low_keywords.items():
        if keyword in bug:
            score += weight
            max_score += weight
            matched_keywords.append(keyword)
 
    # Tags detect करा
    for tag, keywords in tag_keywords.items():
        for keyword in keywords:
            if keyword in bug:
                if tag not in tags:
                    tags.append(tag)
                break
 
    if not tags:
        tags = ["General"]
 
    # Severity आणि Confidence calculate करा
  # Severity calculate
    if score >= 8:
        severity = "High"
        confidence = min(95, 70 + score * 2)
        color = "danger"

    elif score >= 4:
        severity = "Medium"
        confidence = min(90, 60 + score * 3)
        color = "warning"

    else:
        severity = "Low"
        confidence = min(85, 50 + score * 5)
        color = "success"

    # 🎯 Smart Dynamic Suggestions
    if any(x in bug for x in ["otp","login","password","authentication","jwt","token","sso"]):
        suggestion = "🔐 Authentication issue detected. Verify login flow, OTP delivery, token validation and session handling."
    elif any(x in bug for x in ["payment","transaction","refund","billing","checkout","gateway","upi"]):
        suggestion = "💳 Payment issue detected. Check transaction logs, gateway responses and payment reconciliation."

    elif any(x in bug for x in ["security","hack","breach","unauthorized","permission","xss","csrf"]):
        suggestion = "🔒 Security issue detected. Review access control, authentication and security audit logs."

    elif any(x in bug for x in ["database","sql","firebase","query","record","deadlock"]):
        suggestion = "🗄️ Database issue detected. Verify connectivity, query execution and data consistency."

    elif any(x in bug for x in ["memory leak","cpu","performance","slow","lag","timeout","latency"]):
         suggestion = "⚡ Performance issue detected. Analyze resource utilization, response time and bottlenecks."

    elif any(x in bug for x in ["crash","exception","fatal","500","null pointer"]):
         suggestion = "🐞 Application crash detected. Review stack traces, logs and exception handling."

    elif any(x in bug for x in ["network","connection","dns","503","502","api"]):
        suggestion = "🌐 Network/API issue detected. Verify connectivity, endpoint availability and timeout settings."

    elif any(x in bug for x in ["upload","download","pdf","csv","file"]):
        suggestion = "📁 File handling issue detected. Verify file integrity, storage and upload/download processing."

    elif any(x in bug for x in ["report","dashboard","analytics","chart","graph","export"]):
        suggestion = "📊 Reporting issue detected. Validate report generation logic and data aggregation."

    elif any(x in bug for x in ["ui","design","alignment","layout","button","screen"]):
        suggestion = "🎨 UI issue detected. Review responsive layout and rendering behavior."

    else:
        suggestion = """
🔍 Recommended Investigation

    • Reproduce the issue consistently
    • Review application logs
    • Review server logs
    • Analyze recent code changes
    • Verify database and API interactions
    • Perform root cause analysis
    """
    # Confidence minimum 60%
    confidence = max(60, confidence)

    return {
        "severity": severity,
        "confidence": int(confidence),
        "suggestion": suggestion,
        "tags": tags,
        "matched_keywords": matched_keywords,
        "color": color,
        "score": score
    }
 
# ================ FIREBASE HELPERS ================
 
def save_bug(bug, severity, suggestion, confidence, tags, username):
    """Bug Firebase मध्ये save करा"""
    ref = db.reference("bugs")
    bug_id = ref.push({
        "bug": bug,
        "severity": severity,
        "suggestion": suggestion,
        "confidence": confidence,
        "tags": tags,
        "status": "Open",
        "assigned_to": "",
        "priority": "P2",
        "submitted_by": username,
        "time": str(datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        "resolved_time": "",
        "comments": []
    })
    return bug_id.key
 
def get_all_bugs():
    """सगळे bugs Firebase मधून आण"""
    ref = db.reference("bugs")
    data = ref.get() or {}
    return data
 
def get_bug_counts():
    """Firebase मधून live counts आण"""
    data = get_all_bugs()
    count = {"High": 0, "Medium": 0, "Low": 0}
    for item in data.values():
        sev = item.get("severity", "")
        if sev in count:
            count[sev] += 1
    return count
 
def get_status_counts():
    """Status counts आण"""
    data = get_all_bugs()
    status = {"Open": 0, "In Progress": 0, "Testing": 0, "Resolved": 0, "Closed": 0}
    for item in data.values():
        s = item.get("status", "Open")
        if s in status:
            status[s] += 1
    return status
 
def save_login_history(username, role):
    """Login history save करा"""
    ref = db.reference("login_history")
    ref.push({
        "username": username,
        "role": role,
        "time": str(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    })
def save_notification(message, user="all"):
    ref = db.reference("notifications")
    ref.push({
        "message": message,
        "user": user,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

def get_notifications():
    ref = db.reference("notifications")
    data = ref.get() or {}

    notifications = []
    for key, item in data.items():
        item["id"] = key
        notifications.append(item)

    notifications = sorted(
        notifications,
        key=lambda x: x.get("time", ""),
        reverse=True
    )

    return notifications[:10]
# ================ GRAPH GENERATION ================
 
def create_pie_chart(count):
    """Severity Pie Chart"""
    if not os.path.exists("static"):
        os.makedirs("static")
 
    labels = ["High", "Medium", "Low"]
    values = [count.get("High", 0), count.get("Medium", 0), count.get("Low", 0)]
 
    if sum(values) == 0:
        values = [1, 1, 1]
 
    colors = ['#ef4444', '#f59e0b', '#10b981']
    explode = (0.05, 0.05, 0.05)
 
    plt.figure(figsize=(6, 5), facecolor='#1e293b')
    ax = plt.gca()
    ax.set_facecolor('#1e293b')
 
    wedges, texts, autotexts = plt.pie(
        values, labels=labels, autopct='%1.1f%%',
        colors=colors, startangle=90,
        explode=explode,
        wedgeprops={'edgecolor': '#334155', 'linewidth': 2}
    )
 
    for text in texts:
        text.set_color('white')
        text.set_fontsize(12)
    for autotext in autotexts:
        autotext.set_color('white')
        autotext.set_fontweight('bold')
 
    plt.title('Bug Severity Distribution', color='white', fontsize=14, pad=20)
    plt.axis('equal')
    plt.tight_layout()
    for old_file in glob("static/pie_chart_*.png"):
        os.remove(old_file)
    import time 
    timestamp = int(time.time())
    path = f"static/pie_chart_{timestamp}.png"
    plt.savefig(path, bbox_inches='tight', facecolor='#1e293b')
    plt.close()
    return f"pie_chart_{timestamp}.png"
 
def create_trend_chart():
    """Daily Bug Trend Line Chart"""
    if not os.path.exists("static"):
        os.makedirs("static")
 
    data = get_all_bugs()
 
    # Last 7 days data
    dates = {}
    for i in range(7):
        date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        dates[date] = {"High": 0, "Medium": 0, "Low": 0}
 
    for item in data.values():
        time_str = item.get("time", "")
        if time_str:
            date = time_str[:10]
            if date in dates:
                sev = item.get("severity", "Low")
                if sev in dates[date]:
                    dates[date][sev] += 1
 
    sorted_dates = sorted(dates.keys())
    high_vals = [dates[d]["High"] for d in sorted_dates]
    med_vals = [dates[d]["Medium"] for d in sorted_dates]
    low_vals = [dates[d]["Low"] for d in sorted_dates]
    x_labels = [d[5:] for d in sorted_dates]  # MM-DD format
 
    fig, ax = plt.subplots(figsize=(8, 4), facecolor='#1e293b')
    ax.set_facecolor('#1e293b')
 
    ax.plot(x_labels, high_vals, color='#ef4444', marker='o', linewidth=2, label='High', markersize=6)
    ax.plot(x_labels, med_vals, color='#f59e0b', marker='s', linewidth=2, label='Medium', markersize=6)
    ax.plot(x_labels, low_vals, color='#10b981', marker='^', linewidth=2, label='Low', markersize=6)
 
    ax.set_title('Bug Trend (Last 7 Days)', color='white', fontsize=13, pad=15)
    ax.tick_params(colors='white')
    ax.spines['bottom'].set_color('#334155')
    ax.spines['left'].set_color('#334155')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.legend(facecolor='#334155', labelcolor='white')
    ax.set_xlabel('Date', color='#94a3b8')
    ax.set_ylabel('Bug Count', color='#94a3b8')
 
    plt.tight_layout()
    plt.savefig("static/trend_chart.png", bbox_inches='tight', facecolor='#1e293b')
    plt.close()
 
def create_bar_chart(status_count):
    """Status Bar Chart"""
    if not os.path.exists("static"):
        os.makedirs("static")
 
    labels = list(status_count.keys())
    values = list(status_count.values())
    colors = ['#3b82f6', '#f59e0b', '#8b5cf6', '#10b981', '#6b7280']
 
    fig, ax = plt.subplots(figsize=(7, 4), facecolor='#1e293b')
    ax.set_facecolor('#1e293b')
 
    bars = ax.bar(labels, values, color=colors, edgecolor='#334155', linewidth=1.5)
 
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1,
                str(val), ha='center', va='bottom', color='white', fontweight='bold')
 
    ax.set_title('Bug Status Overview', color='white', fontsize=13, pad=15)
    ax.tick_params(colors='white')
    ax.spines['bottom'].set_color('#334155')
    ax.spines['left'].set_color('#334155')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.set_ylabel('Count', color='#94a3b8')
 
    plt.tight_layout()
    plt.savefig("static/bar_chart.png", bbox_inches='tight', facecolor='#1e293b')
    plt.close()
 
# ==================== LOGIN ====================
@app.route('/')
def home():
    if 'user' in session:
        return redirect('/dashboard')
    return render_template("login.html")
 
@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()

    if not username or not password:
        return render_template("login.html", error="Username आणि Password टाका!")

    # १. Admin लॉगिन (थेट कोडमधून)
    if username == 'admin' and password == 'admin123':
        session.permanent = True
        session['user'] = username
        session['role'] = 'Admin'
        session['name'] = 'Admin User'
        return redirect('/dashboard')

    # २. Developer लॉगिन (डेटाबेस खराब असला तरी थेट चालेल)
    if username == 'developer' and password == 'dev123':
        session.permanent = True
        session['user'] = username
        session['role'] = 'Developer'
        session['name'] = 'Dev User'
        return redirect('/dashboard')

    # ३. Tester लॉगिन (थेट कोडमधून)
    if username == 'tester' and password == 'test123':
        session.permanent = True
        session['user'] = username
        session['role'] = 'Tester'
        session['name'] = 'Tester User'
        return redirect('/dashboard')

    return render_template("login.html", error="❌ चुकीचा Username किंवा Password!")
# ================ DASHBOARD ================
 
@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'user' not in session:
        return redirect('/')
 
    result = None
    ai_result = None
 
    if request.method == 'POST':
        bug = request.form.get('bug', '').strip()
        priority = request.form.get('priority', 'P2')
 
        if bug:
            # 🤖 AI Classification
            ai_result = ai_classify_bug(bug)
            result = ai_result['severity']
 
            # Firebase मध्ये save करा
            save_bug(
                bug=bug,
                severity=ai_result['severity'],
                suggestion=ai_result['suggestion'],
                confidence=ai_result['confidence'],
                tags=ai_result['tags'],
                username=session['user']
            )
            save_notification(
                 f"New bug reported by {session['user']} - {ai_result['severity']} Severity"
            )
 
    # Live Stats
    count = get_bug_counts()
    status_count = get_status_counts()
    total = sum(count.values())

    notifications = get_notifications()
    
    # Percentages
    high_p = round((count["High"] / total) * 100, 1) if total > 0 else 0
    medium_p = round((count["Medium"] / total) * 100, 1) if total > 0 else 0
    low_p = round((count["Low"] / total) * 100, 1) if total > 0 else 0
 
    # Recent bugs (last 5)
    all_bugs = get_all_bugs()
    recent_bugs = []
    for key, item in all_bugs.items():
        item['id'] = key
        recent_bugs.append(item)
    recent_bugs = sorted(recent_bugs, key=lambda x: x.get('time', ''), reverse=True)[:5]
 
    # Charts generate करा
    create_pie_chart(count)
    create_trend_chart()
 
    return render_template(
       "dashboard.html",
        result=result,
        ai_result=ai_result,
        count=count,
        status_count=status_count,
        total=total,
        notifications=notifications,
        recent_bugs=recent_bugs,
        username=session.get('name', session['user']),
        role=session.get('role', 'User')
    )
 
# ================ HISTORY ================
 
@app.route('/history')
def history():
    if 'user' not in session:
        return redirect('/')
 
    data = get_all_bugs()
 
    search = request.args.get("search", "").lower()
    filter_severity = request.args.get("severity", "")
    filter_status = request.args.get("status", "")
    filter_priority = request.args.get("priority", "")
    filter_date = request.args.get("date", "")
 
    filtered = {}
    for key, item in data.items():
        bug = item.get("bug", "").lower()
        severity = item.get("severity", "")
        status = item.get("status", "")
        priority = item.get("priority", "")
        time = item.get("time", "")
 
        # Filters apply करा
        if search and search not in bug:
            continue
        if filter_severity and severity != filter_severity:
            continue
        if filter_status and status != filter_status:
            continue
        if filter_priority and priority != filter_priority:
            continue
        if filter_date and not time.startswith(filter_date):
            continue
 
        item['id'] = key
        filtered[key] = item
 
    # Sort by time (newest first)
    sorted_bugs = sorted(filtered.items(), key=lambda x: x[1].get('time', ''), reverse=True)
    sorted_filtered = dict(sorted_bugs)
 
    return render_template(
        "history.html",
        data=sorted_filtered,
        total=len(sorted_filtered),
        role=session.get('role', 'User')
    )
 
# ================ BUG DETAIL ================
 
@app.route('/bug/<id>')
def bug_detail(id):
    if 'user' not in session:
        return redirect('/')
 
    ref = db.reference(f"bugs/{id}")
    bug = ref.get()
 
    if not bug:
        return redirect('/history')
 
    bug['id'] = id
    return render_template("bug_detail.html", bug=bug, role=session.get('role', 'User'))
 
# ================ UPDATE BUG STATUS ================
 
@app.route('/bug/update/<id>', methods=['POST'])
def update_bug(id):
    if 'user' not in session:
        return redirect('/')
 
    ref = db.reference(f"bugs/{id}")
    bug = ref.get()
 
    if bug:
        new_status = request.form.get('status', bug.get('status', 'Open'))
        new_assigned = request.form.get('assigned_to', bug.get('assigned_to', ''))
        new_priority = request.form.get('priority', bug.get('priority', 'P2'))
        comment = request.form.get('comment', '').strip()
 
        update_data = {
            'status': new_status,
            'assigned_to': new_assigned,
            'priority': new_priority
        }
 
        # Resolved time set करा
        if new_status == 'Resolved' and not bug.get('resolved_time'):
            update_data['resolved_time'] = str(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
 
        # Comment add करा
        if comment:
            comments = bug.get('comments', [])
            if isinstance(comments, dict):
                comments = list(comments.values())
            comments.append({
                "text": comment,
                "by": session['user'],
                "time": str(datetime.now().strftime("%Y-%m-%d %H:%M"))
            })
            update_data['comments'] = comments
 
        ref.update(update_data)
        save_notification(
             f"Bug status changed to {new_status} by {session['user']}"
        )
 
    return redirect(f'/bug/{id}')
 
# ================ ANALYTICS ================
 
@app.route('/analytics')
def analytics():
    if 'user' not in session:
        return redirect('/')
 
    data = get_all_bugs()
    count = get_bug_counts()
    status_count = get_status_counts()
    total = sum(count.values())
 
    # Top bugs analysis
    bug_texts = [item.get('bug', '') for item in data.values()]
    all_words = []
    for text in bug_texts:
        words = re.findall(r'\b\w{4,}\b', text.lower())
        all_words.extend(words)
 
    # Stop words हटवा
    stop_words = {'this', 'that', 'with', 'from', 'have', 'been', 'when', 'there', 'which'}
    filtered_words = [w for w in all_words if w not in stop_words]
    top_keywords = Counter(filtered_words).most_common(8)
 
    # Resolution time calculate करा
    resolved_times = []
    for item in data.values():
        if item.get('resolved_time') and item.get('time'):
            try:
                submitted = datetime.strptime(item['time'], "%Y-%m-%d %H:%M:%S")
                resolved = datetime.strptime(item['resolved_time'], "%Y-%m-%d %H:%M:%S")
                diff = (resolved - submitted).total_seconds() / 3600  # hours
                resolved_times.append(round(diff, 1))
            except:
                pass
 
    avg_resolution = round(sum(resolved_times) / len(resolved_times), 1) if resolved_times else 0
 
    # Tag analysis
    all_tags = []
    for item in data.values():
        tags = item.get('tags', [])
        if isinstance(tags, list):
            all_tags.extend(tags)
    tag_counts = Counter(all_tags).most_common(6)
 
    # Charts generate करा
    create_pie_chart(count)
    create_trend_chart()
    create_bar_chart(status_count)
 
    return render_template(
        "analytics.html",
        count=count,
        status_count=status_count,
        total=total,
        top_keywords=top_keywords,
        avg_resolution=avg_resolution,
        tag_counts=tag_counts,
        role=session.get('role', 'User')
    )
 
# ================ PROFILE ================
 
@app.route('/profile')
def profile():
    if 'user' not in session:
        return redirect('/')
 
    username = session['user']
    user = get_user(username)
    data = get_all_bugs()
 
    # माझे bugs
    my_bugs = []
    my_resolved = 0
    my_open = 0
 
    for key, item in data.items():
        if item.get('submitted_by') == username:
            item['id'] = key
            my_bugs.append(item)
            if item.get('status') == 'Resolved':
                my_resolved += 1
            elif item.get('status') == 'Open':
                my_open += 1
 
    my_bugs = sorted(my_bugs, key=lambda x: x.get('time', ''), reverse=True)
 
    # Login history
    login_ref = db.reference("login_history")
    login_data = login_ref.get() or {}
    my_logins = []
    for item in login_data.values():
        if item.get('username') == username:
            my_logins.append(item)
    my_logins = sorted(my_logins, key=lambda x: x.get('time', ''), reverse=True)[:5]
 
    return render_template(
        "profile.html",
        user=user,
        username=username,
        my_bugs=my_bugs,
        my_resolved=my_resolved,
        my_open=my_open,
        my_logins=my_logins,
        role=session.get('role', 'User')
    )
 
# ================ REPORT PAGE ================
 
@app.route('/report')
def report():
    if 'user' not in session:
        return redirect('/')
 
    data = get_all_bugs()
    count = get_bug_counts()
    status_count = get_status_counts()
    total = sum(count.values())
 
    return render_template(
        "report.html",
        data=data,
        count=count,
        status_count=status_count,
        total=total,
        role=session.get('role', 'User'),
        generated_on=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )
 
# ================ EXPORT CSV ================
 
@app.route('/download/csv')
def download_csv():
    if 'user' not in session:
        return redirect('/')
 
    data = get_all_bugs()
 
    def generate():
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['#', 'Bug Description', 'Severity', 'Status', 'Priority',
                         'Confidence %', 'Tags', 'Submitted By', 'Assigned To', 'Time'])
        output.seek(0)
        yield output.read()
        output.truncate(0)
        output.seek(0)
 
        for i, (key, v) in enumerate(data.items(), 1):
            tags = v.get('tags', [])
            if isinstance(tags, list):
                tags_str = ', '.join(tags)
            else:
                tags_str = str(tags)
            writer.writerow([
                i,
                v.get('bug', ''),
                v.get('severity', ''),
                v.get('status', ''),
                v.get('priority', ''),
                f"{v.get('confidence', 0)}%",
                tags_str,
                v.get('submitted_by', ''),
                v.get('assigned_to', ''),
                v.get('time', '')
            ])
            output.seek(0)
            yield output.read()
            output.truncate(0)
            output.seek(0)
 
    headers = {
        "Content-Disposition": "attachment; filename=bug_report.csv",
        "Content-Type": "text/csv; charset=utf-8"
    }
    return Response(generate(), headers=headers)
 
# ================ EXPORT JSON ================
 
@app.route('/download/json')
def download_json():
    if 'user' not in session:
        return redirect('/')
 
    data = get_all_bugs()
    json_data = json.dumps(data, indent=2, ensure_ascii=False)
 
    return Response(
        json_data,
        mimetype='application/json',
        headers={"Content-Disposition": "attachment; filename=bug_report.json"}
    )
 
# ================ DELETE BUG ================
 
@app.route('/delete/<id>')
def delete(id):
    if 'user' not in session:
        return redirect('/')
 
    # फक्त Admin delete करू शकतो
    if session.get('role') != 'Admin':
        return redirect('/history')
 
    ref = db.reference("bugs")
    ref.child(id).delete()
    return redirect('/history')
 
# ================ ADMIN PANEL ================
 
@app.route('/admin')
def admin():
    if 'user' not in session:
        return redirect('/')
 
    if session.get('role') != 'Admin':
        return redirect('/dashboard')
 
    data = get_all_bugs()
    count = get_bug_counts()
    status_count = get_status_counts()
    total = sum(count.values())
    users = get_users()
 
    # Login history
    login_ref = db.reference("login_history")
    login_data = login_ref.get() or {}
    recent_logins = sorted(login_data.values(), key=lambda x: x.get('time', ''), reverse=True)[:10]
 
    return render_template(
        "admin.html",
        data=data,
        count=count,
        status_count=status_count,
        total=total,
        users=users,
        recent_logins=recent_logins,
        role=session.get('role', 'User')
    )
 
# ================ API ENDPOINTS (AJAX साठी) ================
 
@app.route('/api/stats')
def api_stats():
    """Live stats JSON format मध्ये"""
    if 'user' not in session:
        return jsonify({"error": "Unauthorized"}), 401
 
    count = get_bug_counts()
    status_count = get_status_counts()
    total = sum(count.values())
 
    return jsonify({
        "count": count,
        "status": status_count,
        "total": total,
        "timestamp": str(datetime.now().strftime("%H:%M:%S"))
    })
 
@app.route('/api/recent')
def api_recent():
    """Recent 5 bugs JSON format मध्ये"""
    if 'user' not in session:
        return jsonify({"error": "Unauthorized"}), 401
 
    all_bugs = get_all_bugs()
    recent = []
    for key, item in all_bugs.items():
        recent.append({
            "id": key,
            "bug": item.get('bug', '')[:50],
            "severity": item.get('severity', ''),
            "status": item.get('status', ''),
            "time": item.get('time', '')
        })
    recent = sorted(recent, key=lambda x: x.get('time', ''), reverse=True)[:5]
    return jsonify(recent)
 
# ================ LOGOUT ================
 
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')
 
# ================ ERROR HANDLERS ================
 
@app.errorhandler(404)
def not_found(e):
    return render_template("login.html", error="Page सापडला नाही!"), 404
 
@app.errorhandler(500)
def server_error(e):
    return render_template("login.html", error="Server Error! Admin ला contact करा."), 500
 
# ================ RUN ================
 
if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)















