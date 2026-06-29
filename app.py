from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from datetime import datetime
import os
import mysql.connector
import requests
import json
import razorpay
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

RAZORPAY_KEY_ID = "rzp_live_SSgm493FHbxcNw"
RAZORPAY_KEY_SECRET = "aC5ihNgCzFyPi35dm1qSjgzk"

client = razorpay.Client(
    auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET)
)
app.secret_key = "secret123"

# ✅ Upload folder config (IMPORTANT)
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash

# ---------------- DB CONNECTION ----------------
def get_db():
    return mysql.connector.connect(
        host="127.0.0.1",
        user="root",
        password="AIcore@123",
        database="lms_db",
        port=3306
    )

# ---------------- ROLE CHECK ----------------
def role_required(role):
    def wrapper(func):
        def inner(*args, **kwargs):
            if session.get('role') != role:
                return "Access Denied ❌"
            return func(*args, **kwargs)
        inner.__name__ = func.__name__
        return inner
    return wrapper

@app.route('/')
def home():
    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    category = request.args.get('category')
    search = request.args.get('search')

    query = "SELECT * FROM courses WHERE video_url IS NOT NULL AND video_url != ''"
    params = []

    if category:
        query += " AND category=%s"
        params.append(category)

    if search:
        query += " AND title LIKE %s"
        params.append(f"%{search}%")

    cursor.execute(query, tuple(params))

    courses = cursor.fetchall()

# 🔥 NEW COURSES
    cursor.execute("SELECT * FROM courses ORDER BY id DESC LIMIT 8")
    new_courses = cursor.fetchall()
    
    

    cursor.close()
    conn.close()

    return render_template(
    'home.html',
    courses=courses,
    new_courses=new_courses
)
# ---------------- REGISTER ----------------
@app.route('/register', methods=['GET', 'POST'])
def register():
      if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']   # ✅ NEW

        hashed_password = generate_password_hash(password)

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
        if cursor.fetchone():
            return "Email already exists ❌"

        query = "INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, %s)"
        cursor.execute(query, (name, email, hashed_password, role))
        conn.commit()

        cursor.close()
        conn.close()

        return redirect(url_for('login'))

      return render_template('register.html')


# ---------------- LOGIN ----------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email'].strip()
        password = request.form['password'].strip()

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
        user = cursor.fetchone()

        cursor.close()
        conn.close()

        print("USER DATA:", user)

        if user:
            print("DB ROLE:", user[4])

        if user and check_password_hash(user[3], password):

            # ✅ FIXED (only this)
            session['user_id'] = user[0]
            session['user_name'] = user[1]
            session['role'] = user[4]

            print("LOGIN SUCCESS → ROLE:", session['role'])

            return redirect(url_for('dashboard'))
        else:
            return "Invalid Email or Password ❌"

    return render_template('login.html')    


# ---------------- DASHBOARD ----------------
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    role = session.get('role')

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    # ✅ 1. Get enrolled courses
    cursor.execute("""
        SELECT c.*
        FROM courses c
        JOIN enrollments e ON c.id = e.course_id
        WHERE e.student_id = %s
    """, (user_id,))
    courses = cursor.fetchall()

    # ✅ 2. Total lessons
    cursor.execute("""
        SELECT COUNT(*) as total
        FROM lessons l
        JOIN courses c ON l.course_id = c.id
        JOIN enrollments e ON e.course_id = c.id
        WHERE e.student_id = %s
    """, (user_id,))
    total_lessons = cursor.fetchone()['total']

    # ✅ 3. Completed lessons
    cursor.execute("""
        SELECT COUNT(*) as completed
        FROM progress
        WHERE user_id = %s AND completed = 1
    """, (user_id,))
    completed_lessons = cursor.fetchone()['completed']
    progress_percent = 70   # 🔥 TEST VALUE

    # ✅ 4. Progress %
    if total_lessons > 0:
        progress_percent = int((completed_lessons / total_lessons) * 100)
    else:
        progress_percent = 0

    cursor.close()
    conn.close()

    return render_template(
        'dashboard.html',
        courses=courses,
        progress_percent=progress_percent,
        user_name=session.get('user_name'),
        role=role
    )


# ---------------- ALL COURSES ----------------

@app.route('/courses')
def courses():

    category = request.args.get("category")

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    if category == "python":
        cursor.execute(
            "SELECT * FROM courses WHERE title LIKE '%python%'"
        )

    elif category == "ai":
        cursor.execute(
            "SELECT * FROM courses WHERE title LIKE '%ai%' OR title LIKE '%machine%'"
        )

    elif category == "web":
        cursor.execute(
            "SELECT * FROM courses WHERE title LIKE '%react%' OR title LIKE '%node%' OR title LIKE '%web%'"
        )

    elif category == "cyber":
        cursor.execute(
            "SELECT * FROM courses WHERE title LIKE '%cyber%'"
        )

    elif category == "data":
        cursor.execute(
            "SELECT * FROM courses WHERE title LIKE '%data%'"
        )

    else:
        cursor.execute("SELECT * FROM courses")

    courses = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "courses.html",
        courses=courses
    )


# ---------------- ENROLL ----------------
@app.route('/enroll/<int:course_id>')
def enroll(course_id):

    # 🔐 अगर login नहीं है → login page
    if 'user_id' not in session:
        return redirect('/login')

    # 🔐 अगर student नहीं है
    if session.get('role') != 'student':
        return "Only students can enroll ❌"

    user_id = session['user_id']

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM enrollments WHERE student_id=%s AND course_id=%s",
        (user_id, course_id)
    )

    if cursor.fetchone():
        return redirect(url_for('dashboard'))

    cursor.execute(
        "INSERT INTO enrollments (student_id, course_id) VALUES (%s, %s)",
        (user_id, course_id)
    )
    conn.commit()

    cursor.close()
    conn.close()

    return redirect(url_for('dashboard'))


# ---------------- ADD COURSE ----------------
@app.route('/add-course', methods=['GET', 'POST'])
@role_required('instructor')
def add_course():

    if request.method == "POST":

        title = request.form.get('title')
        description = request.form.get('description')
        video_url = request.form.get('video_url')

        if not video_url:

            title_lower = str(title).lower()

            if "python" in title_lower:
                video_url = "https://www.youtube.com/embed/rfscVS0vtbw"

            elif "java" in title_lower:
                video_url = "https://www.youtube.com/embed/eIrMbAQSU34"

            elif "react" in title_lower:
                video_url = "https://www.youtube.com/embed/bMknfKXIFA8"

            elif "javascript" in title_lower:
                video_url = "https://www.youtube.com/embed/PkZNo7MFNFg"

            else:
                video_url = "https://www.youtube.com/embed/rfscVS0vtbw"

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO courses
            (title, description, instructor_id, video_url)

            VALUES (%s, %s, %s, %s)
        """, (
            title,
            description,
            session['user_id'],
            video_url
        ))

        conn.commit()

        course_id = cursor.lastrowid

        generate_ai_quiz(title, course_id)

        cursor.close()
        conn.close()

        return redirect(url_for('dashboard'))

    return render_template('add_course.html')



@app.route('/add-assignment/<int:course_id>', methods=['GET', 'POST'])
@role_required('instructor')
def add_assignment(course_id):
    if request.method == 'POST':
        title = request.form['title']

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            "INSERT INTO assignments (course_id, title) VALUES (%s,%s)",
            (course_id, title)
        )
        conn.commit()

        cursor.close()
        conn.close()

        return redirect(url_for('dashboard'))

    return render_template('add_assignment.html', course_id=course_id)

@app.route('/assignments/<int:course_id>')
def view_assignments(course_id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM assignments WHERE course_id=%s",
        (course_id,)
    )
    assignments = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('assignments.html', assignments=assignments, course_id=course_id)



@app.route('/submit/<int:assignment_id>', methods=['POST'])
def submit_assignment(assignment_id):
    print("🔥 SUBMIT CLICKED") 
    import os
    import uuid
    from datetime import datetime

    file = request.files['file']

    # original filename
    original_name = file.filename

    # extension
    ext = original_name.split('.')[-1]

    # short name
    short_name = original_name.split('.')[0].replace(" ", "_")[:10]

    # timestamp
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")

    # random id
    random_id = str(uuid.uuid4())[:4]

    # final filename
    filename = f"{session['user_id']}_{timestamp}_{random_id}_{short_name}.{ext}"

    # save file
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))


    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO submissions (assignment_id, student_id, file) VALUES (%s,%s,%s)",
        (assignment_id, session['user_id'], filename)
    )
    conn.commit()

    cursor.execute("SELECT course_id FROM assignments WHERE id=%s", (assignment_id,))
    course = cursor.fetchone()
    course_id = course[0]

    # 🔥 फिर close
    cursor.close()
    conn.close()

    flash("Assignment Submitted Successfully ✅")
    return redirect(url_for('view_assignments', course_id=course_id))

# ---------------- ADMIN APPROVE COURSE ----------------
@app.route('/approve/<int:course_id>')
@role_required('admin')
def approve(course_id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE courses SET status='approved' WHERE id=%s",
        (course_id,)
    )
    conn.commit()

    cursor.close()
    conn.close()

    return redirect(url_for('dashboard'))


# ---------------- LOGOUT ----------------
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/submissions/<int:assignment_id>')
def view_submissions_new(assignment_id):

    conn = get_db()
    cursor = conn.cursor(dictionary=True)   # 👈 बहुत जरूरी

    cursor.execute("""
        SELECT s.id, s.file, s.marks, u.name
        FROM submissions s
        JOIN users u ON s.student_id = u.id
        WHERE s.assignment_id = %s
    """, (assignment_id,))

    data = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('submissions.html', data=data)

@app.route('/give-marks/<int:submission_id>', methods=['POST'])
def give_marks(submission_id):
    marks = request.form['marks']

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE submissions SET marks=%s WHERE id=%s",
        (marks, submission_id)
    )
    conn.commit()

    cursor.execute("SELECT assignment_id FROM submissions WHERE id=%s", (submission_id,))
    assignment = cursor.fetchone()

    cursor.close()
    conn.close()

    return redirect(url_for('view_submissions_new', assignment_id=assignment[0]))

@app.route('/my-marks')
def my_marks():
    if session.get('role') != 'student':
        return "Access Denied ❌"

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT a.title, s.marks
        FROM submissions s
        JOIN assignments a ON s.assignment_id = a.id
        WHERE s.student_id = %s
    """, (session['user_id'],))

    data = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('my_marks.html', data=data)


@app.route('/course/<int:course_id>')
def course_detail(course_id):

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    # course
    cursor.execute("SELECT * FROM courses WHERE id=%s", (course_id,))
    course = cursor.fetchone()

    # lessons
    cursor.execute("SELECT * FROM lessons WHERE course_id=%s", (course_id,))
    lessons = cursor.fetchall()

    user_id = session.get('user_id')

    # 🔒 purchase check
    cursor.execute(
        "SELECT * FROM purchases WHERE user_id=%s AND course_id=%s",
        (user_id, course_id)
    )

    purchased = cursor.fetchone()

    if not purchased:
        return "❌ Please buy this course first"

    # completed lessons
    cursor.execute("""
        SELECT lesson_id FROM progress 
        WHERE user_id=%s
    """, (user_id,))

    completed_lessons = [row['lesson_id'] for row in cursor.fetchall()]

    # last watched
    cursor.execute("""
        SELECT lesson_id FROM progress 
        WHERE user_id=%s AND last_watched=TRUE
    """, (user_id,))

    last = cursor.fetchone()
    last_lesson_id = last['lesson_id'] if last else None

    # progress %
    total = len(lessons)
    completed = len(completed_lessons)

    progress_percent = int((completed / total) * 100) if total > 0 else 0

    if progress_percent > 100:
        progress_percent = 100

    cursor.close()
    conn.close()

    return render_template(
    "course_detail.html",
    course=course,
    lessons=lessons,
    completed_lessons=completed_lessons,
    last_lesson_id=last_lesson_id,
    progress_percent=progress_percent,
    course_id=course_id
)
@app.route('/mark_complete/<int:lesson_id>')
def mark_complete(lesson_id):

    # 🔥 user_id लो
    user_id = session.get('user_id')

    # ❗ अगर login नहीं है
    if not user_id:
        return "User not logged in ❌"

    conn = get_db()
    cursor = conn.cursor()

    # 🔥 पहले old last_watched reset करो
    cursor.execute("""
    UPDATE progress SET last_watched=0 
    WHERE user_id=%s
    """, (user_id,))

    # 🔥 insert/update
    cursor.execute("""
    INSERT INTO progress (user_id, lesson_id, completed, last_watched)
    VALUES (%s, %s, 1, 1)
    """, (user_id, lesson_id))

    conn.commit()

    cursor.close()
    conn.close()

    return "done"

@app.route('/mark_last_watched/<int:lesson_id>')
def mark_last_watched(lesson_id):
    user_id = session.get('user_id')

    conn = get_db()
    cursor = conn.cursor()

    # reset old
    cursor.execute("UPDATE progress SET last_watched = 0 WHERE user_id = %s", (user_id,))

    # set new
    cursor.execute("""
        UPDATE progress 
        SET last_watched = 1 
        WHERE user_id = %s AND lesson_id = %s
    """, (user_id, lesson_id))

    conn.commit()
    cursor.close()
    conn.close()

    return "OK"

@app.route('/buy/<int:course_id>')
def buy_course(course_id):

    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']

    conn = get_db()
    cursor = conn.cursor()

    # already purchased check
    cursor.execute(
        "SELECT * FROM purchases WHERE user_id=%s AND course_id=%s",
        (user_id, course_id)
    )

    existing = cursor.fetchone()

    if not existing:
        cursor.execute(
            "INSERT INTO purchases (user_id, course_id) VALUES (%s,%s)",
            (user_id, course_id)
        )
        conn.commit()

    cursor.close()
    conn.close()

    return redirect(f'/course/{course_id}')
@app.route('/my-courses')
def my_courses():

    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT courses.*
        FROM purchases
        JOIN courses
        ON purchases.course_id = courses.id
        WHERE purchases.user_id=%s
    """, (user_id,))

    courses = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        'my_courses.html',
        courses=courses
    )

@app.route("/certificate/<int:course_id>")
def certificate(course_id):

    conn = sqlite3.connect(r"C:\Users\Deep\OneDrive\Desktop\python_ragister\lms.db")
    conn.row_factory = sqlite3.Row

    cursor = conn.cursor()

    cursor.execute(
    "SELECT * FROM courses WHERE id=?",
    (course_id,)
)

    course = cursor.fetchone()
    today = datetime.now().strftime("%d %B %Y")
    conn.close()

    return f"""
<html>

<head>
<style>

body{{
margin:0;
padding:0;
font-family:Arial;
background:#0f172a;
}}

.certificate{{
width:1100px;
height:750px;
margin:40px auto;
background:white;
border:20px solid #facc15;
padding:60px;
box-sizing:border-box;
text-align:center;
position:relative;
}}

h1{{
font-size:55px;
color:#0f172a;
margin-top:40px;
}}

h2{{
font-size:42px;
color:#2563eb;
margin-top:30px;
}}

p{{
font-size:24px;
color:#334155;
}}

.badge{{
font-size:28px;
margin-top:20px;
color:#16a34a;
}}

.footer{{
position:absolute;
bottom:50px;
left:60px;
right:60px;
display:flex;
justify-content:space-between;
font-size:20px;
}}

.print-btn{{
margin-top:40px;
padding:15px 35px;
border:none;
border-radius:12px;
background:#2563eb;
color:white;
font-size:18px;
cursor:pointer;
}}

</style>
</head>

<body>

<div class="certificate">

<h1>🎓 Certificate of Completion</h1>

<p>This certificate is proudly presented to</p>

<h2>Deep</h2>

<p>for successfully completing</p>

<h2>{course['title']}</h2>

<p class="badge">
✅ Completed on {today}
</p>

<div class="footer">

<div>
___________________
<br>
Instructor
</div>

<div>
Certificate ID:
#{course['id']}2025
</div>

</div>

<button
class="print-btn"
onclick="window.print()">
⬇ Download PDF
</button>

</div>

</body>
</html>
"""

@app.route("/create-test-db")
def create_test_db():

    conn = sqlite3.connect("lms.db")
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS courses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT
    )
    """)
    cursor.execute("""
CREATE TABLE IF NOT EXISTS quizzes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id INTEGER,
    question TEXT,
    option1 TEXT,
    option2 TEXT,
    option3 TEXT,
    option4 TEXT,
    correct_answer TEXT
)
""")
    cursor.execute("""
CREATE TABLE IF NOT EXISTS quiz_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    course_id INTEGER,
    score INTEGER,
    passed INTEGER
)
""")

    cursor.execute("""
    INSERT INTO courses (title)
    VALUES ('Python Course')
    """)

    conn.commit()
    conn.close()

    return "DB Created"

@app.route("/tables")
def tables():

    conn = sqlite3.connect("lms.db")
    cursor = conn.cursor()

    cursor.execute("""
    SELECT name FROM sqlite_master
    WHERE type='table'
    """)

    tables = cursor.fetchall()

    conn.close()

    return str(tables)

@app.route("/quiz/<int:course_id>", methods=["GET", "POST"])
def quiz(course_id):

    conn = sqlite3.connect("lms.db")
    conn.row_factory = sqlite3.Row

    cursor = conn.cursor()

    cursor.execute(
    """
    SELECT * FROM quizzes
WHERE course_id=?
ORDER BY RANDOM()
LIMIT 50
    """,
    (course_id,)
)

    quizzes = cursor.fetchall()

    if request.method == "POST":

        score = 0

        for quiz in quizzes:

            selected_answer = request.form.get(
                f"question_{quiz['id']}"
            )

            if selected_answer == quiz["correct_answer"]:
                score += 1

        total = len(quizzes)

        status = "Passed"

        if score < total * 0.7:
            status = "Failed"

        # SAVE RESULT
        cursor.execute("""
        INSERT INTO results
        (student_id, course_id, score, total, status)

        VALUES (?, ?, ?, ?, ?)
        """, (
            1,
            course_id,
            score,
            total,
            status
        ))

        conn.commit()
        conn.close()

        # PASS
        if score >= total * 0.7:

            return f"""
            <h1>🎉 Passed</h1>

            <h2>Score: {score}/{total}</h2>

            <a href="/certificate/{course_id}">
                Download Certificate
            </a>
            """

        # FAIL
        else:

            return f"""
            <h1>❌ Failed</h1>

            <h2>Score: {score}/{total}</h2>
            """

    conn.close()

    return render_template(
        "quiz.html",
        quizzes=quizzes
    )

@app.route("/my-results")
def my_results():

    conn = sqlite3.connect("lms.db")
    conn.row_factory = sqlite3.Row

    cursor = conn.cursor()

    cursor.execute("""
    SELECT * FROM results
    WHERE student_id=?
    """, (1,))

    results = cursor.fetchall()

    conn.close()

    return render_template(
        "my_results.html",
        results=results
    )

@app.route("/student-dashboard")
def student_dashboard():

    conn = sqlite3.connect("lms.db")
    conn.row_factory = sqlite3.Row

    cursor = conn.cursor()

    # RESULTS
    cursor.execute("""
    SELECT * FROM results
    WHERE student_id=?
    """, (1,))

    results = cursor.fetchall()

    # COURSES
    cursor.execute("""
    SELECT * FROM courses
    """)

    courses = cursor.fetchall()

    conn.close()

    return render_template(
        "student_dashboard.html",
        results=results,
        courses=courses
    )

@app.route("/create-results-table")
def create_results_table():

    conn = sqlite3.connect("lms.db")
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER,
        course_id INTEGER,
        score INTEGER,
        total INTEGER,
        status TEXT
    )
    """)

    conn.commit()
    conn.close()

    return "Results Table Created"

def generate_ai_quiz(course_name, course_id):

    print("AI Quiz Function Working")

    import requests
    import json
    import sqlite3

    prompt = f"""
    Generate 50 MCQ quiz questions for {course_name} course.

    Return ONLY JSON format like this:

    [
        {{
            "question": "What is Python?",
            "option1": "Language",
            "option2": "Car",
            "option3": "Bike",
            "option4": "Phone",
            "answer": "Language"
        }}
    ]
    """

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",

        headers={
            "Authorization": "Bearer YOUR_API_KEY",
            "HTTP-Referer": "http://localhost:5000",
            "X-Title": "My LMS",
            "Content-Type": "application/json"
        },

        json={
            "model": "deepseek/deepseek-chat",
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }
    )

    data = response.json()

    print("AI RESPONSE:")
    print(data)

    if "choices" not in data:
        print("AI FAILED")
        return

    text = data["choices"][0]["message"]["content"]

    print(text)

    # CLEAN RESPONSE
    text = text.replace("```json", "")
    text = text.replace("```", "")
    text = text.strip()

    # SAFE JSON LOAD
    try:
        quizzes = json.loads(text)

    except Exception as e:
        print("JSON ERROR:", e)
        print(text)
        return

    conn = sqlite3.connect("lms.db")

    cursor = conn.cursor()

    for quiz in quizzes:

        cursor.execute("""
        INSERT INTO quizzes
        (course_id, question, option1, option2, option3, option4, correct_answer)

        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            course_id,
            quiz["question"],
            quiz["option1"],
            quiz["option2"],
            quiz["option3"],
            quiz["option4"],
            quiz["answer"]
        ))

    conn.commit()
    conn.close()

    print("50 AI quizzes added successfully")

generate_ai_quiz("Python", 1)


@app.route("/quiz/<int:course_id>")
def quiz_page(course_id):

    conn = get_db()

    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT * FROM quizzes WHERE course_id=%s ORDER BY RAND() LIMIT 100",
        (course_id,)
    )

    quizzes = cursor.fetchall()

    conn.close()

    return render_template(
        "quiz.html",
        quizzes=quizzes
    )



@app.route("/my_courses")
def my_courses_page():

    return render_template("my_courses.html")

if __name__ == '__main__':
    app.run(debug=True)