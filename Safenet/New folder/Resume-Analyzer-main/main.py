from flask import Flask, request, jsonify, render_template, redirect, url_for, session
import sqlite3
import webbrowser
import threading

app = Flask(__name__)
app.secret_key = "secret123"

# ===== DATABASE =====
def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS resumes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        role TEXT,
        score INTEGER,
        ats INTEGER,
        matched TEXT,
        missing TEXT
    )
    """)
    conn.commit()
    conn.close()

init_db()

# ===== HOME =====
@app.route("/")
def home():
    if "user" not in session:
        return redirect("/login")
    return render_template("hirex.html")

# ===== LOGIN PAGE =====
@app.route("/login", methods=["GET"])
def login_page():
    return render_template("login.html")

# ===== LOGIN API =====
@app.route("/login", methods=["POST"])
def login():
    if request.is_json:
        data = request.get_json()
        username = data.get("username", "")
        password = data.get("password", "")
    else:
        username = request.form.get("username", "")
        password = request.form.get("password", "")

    if username == "admin" and password == "1234":
        session["user"] = username
        return jsonify({"status": "success"})

    return jsonify({"status": "error"})

# ===== LOGOUT =====
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ===== FILE UPLOAD =====
from PyPDF2 import PdfReader

@app.route("/api/upload", methods=["POST"])
def upload():
    file = request.files.get("file")

    if not file:
        return jsonify({"text": ""})

    text = ""

    if file.filename.endswith(".pdf"):
        reader = PdfReader(file)
        for page in reader.pages:
            text += page.extract_text() or ""

    else:
        text = file.read().decode("utf-8", errors="ignore")

    return jsonify({"text": text})

# ===== ANALYZE =====
import re

@app.route("/api/analyze", methods=["POST"])
def analyze():
    data = request.get_json()

    resume = data.get("resume", "").lower()
    jd = data.get("jd", "").lower()

    skills = [
        "python","java","c++","javascript",
        "sql","mongodb","react","node",
        "aws","docker","kubernetes",
        "machine learning","deep learning","nlp",
        "pandas","numpy","excel","power bi",
        "tableau","etl","data warehouse",
        "cloud","linux"
    ]

    matched = []
    missing = []

    # ✅ MATCHING LOOP
    for skill in skills:
        if skill in jd:
            if re.search(r'\b'+re.escape(skill)+r'\b', resume):
                matched.append(skill)
            else:
                missing.append(skill)

    # ✅ SCORE LOGIC
    jd_skills = [s for s in skills if s in jd]
    base = max(len(jd_skills), 5)
    score = int((len(matched) / base) * 100)

    # ✅ ROLE DETECTION (INSIDE FUNCTION)
        # ✅ ROLE DETECTION
    role_keywords = {
        "Software Developer": ["python", "java", "c++", "api", "backend"],
        "Frontend Developer": ["react", "html", "css", "javascript"],
        "Backend Developer": ["node", "express", "java", "python", "api"],
        "Full Stack Developer": ["react", "node", "api", "javascript", "database"],
        "Data Scientist": ["machine learning", "deep learning", "nlp", "pandas", "numpy"],
        "Data Analyst": ["sql", "excel", "power bi", "tableau", "etl"],
        "Java Developer": ["java", "spring", "hibernate", "jsp"],
        "Python Developer": ["python", "django", "flask"],
        "Business Analyst": ["requirements", "stakeholder", "analysis", "excel", "documentation"],
        "DevOps Engineer": ["docker", "kubernetes", "aws", "cloud", "linux", "ci/cd"],
        "Cloud Engineer": ["aws", "azure", "gcp", "cloud"],
        "AI Engineer": ["machine learning", "deep learning", "tensorflow", "pytorch"],
        "Database Engineer": ["sql", "mongodb", "data warehouse"],
        "Cybersecurity Analyst": ["security", "network", "encryption", "firewall"],
        "Mobile App Developer": ["android", "ios", "flutter", "react native"]
    }

    role_scores = {role: 0 for role in role_keywords}

    combined_text = jd + " " + resume

    for role_name, keywords in role_keywords.items():
        for kw in keywords:
            if kw in matched:
                role_scores[role_name] += 2
            elif kw in combined_text:
                role_scores[role_name] += 1

    role = max(role_scores, key=role_scores.get)

    if role_scores[role] == 0:
        role = "Software Developer"

    return jsonify({
        "name": data.get("name", "Candidate"),  # ✅ FIXED
        "role": role,
        "score": score,
        "ats": min(100, score + 5),
        "allMatched": matched,
        "allMissing": missing,
        "density": matched[:5]
    })

# ===== SAVE =====
@app.route("/api/save", methods=["POST"])
def save():
    data = request.get_json()

    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()

        cursor.execute("""
        INSERT INTO resumes (name, role, score, ats, matched, missing)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (
            data.get("name", "Candidate"),
            data.get("role", ""),
            data.get("score", 0),
            data.get("ats", 0),
            ",".join(data.get("allMatched", [])),
            ",".join(data.get("allMissing", []))
        ))

        conn.commit()
        conn.close()

        return jsonify({"status": "saved"})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

# ===== GET DATA =====
@app.route("/api/get_resumes")
def get_resumes():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("SELECT name, role, score, ats, matched, missing FROM resumes")
    rows = cursor.fetchall()

    conn.close()

    data = []
    for r in rows:
        data.append({
            "name": r[0],
            "role": r[1],
            "score": r[2],
            "ats": r[3],
            "allMatched": r[4].split(",") if r[4] else [],
            "allMissing": r[5].split(",") if r[5] else []
        })

    return jsonify(data)

@app.route("/api/delete", methods=["POST"])
def delete_resume():
    data = request.get_json()
    index = data.get("index")

    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()

        # get all ids in order
        cursor.execute("SELECT id FROM resumes")
        rows = cursor.fetchall()

        if index < 0 or index >= len(rows):
            return jsonify({"status": "error", "message": "Invalid index"})

        row_id = rows[index][0]

        cursor.execute("DELETE FROM resumes WHERE id = ?", (row_id,))
        conn.commit()
        conn.close()

        return jsonify({"status": "deleted"})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

# ===== AUTO OPEN CHROME =====
def open_browser():
    try:
        chrome_path = "C:/Program Files/Google/Chrome/Application/chrome.exe %s"
        webbrowser.get(chrome_path).open("http://127.0.0.1:5000")
    except:
        webbrowser.open("http://127.0.0.1:5000")

# ===== RUN =====
if __name__ == "__main__":
    threading.Timer(1.5, open_browser).start()
    app.run(debug=True)