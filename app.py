
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Image
)
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.colors import HexColor
from flask import send_file
import tempfile
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from flask import send_file

import uuid

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    jsonify,
    send_from_directory
)

from datetime import datetime
from docx import Document
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

from utils.auth import (
    login_required,
    admin_required,
    instructor_required,
    student_required
)

import os
import re
import json
import requests
import mysql.connector
import razorpay

app = Flask(__name__)
load_dotenv()
def get_db_connection():
    conn = mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT")),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )
    return conn
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")

client = razorpay.Client(
    auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET)
)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-key")
# ✅ Upload folder config (IMPORTANT)
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash


print("DB_HOST =", os.getenv("DB_HOST"))
print("DB_NAME =", os.getenv("DB_NAME"))
print("DB_USER =", os.getenv("DB_USER"))
print("DB_PORT =", os.getenv("DB_PORT"))
def get_db():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
        port=int(os.getenv("DB_PORT"))
    )



def parse_quiz_docx(file_path, lesson_id):
    count = 0

    print("LESSON ID =", lesson_id)

    doc = Document(file_path)

    conn = get_db()
    cursor = conn.cursor()

    question = ""
    options = {}
    answer = ""

    for para in doc.paragraphs:

        print("RAW =", para.text)

        text = para.text.strip()

        if not text:
            continue

        if text.startswith("TOPIC"):
            continue

        # -------------------------
        # New Question
        # -------------------------

        if re.match(r'^\d+\.', text):

            if question:

                cursor.execute("""
                    INSERT INTO quiz_questions
                    (
                        lesson_id,
                        question,
                        option_a,
                        option_b,
                        option_c,
                        option_d,
                        correct_answer
                    )
                    VALUES (%s,%s,%s,%s,%s,%s,%s)
                """, (
                    lesson_id,
                    question,
                    options.get("A", ""),
                    options.get("B", ""),
                    options.get("C", ""),
                    options.get("D", ""),
                    answer
                ))

                count += 1
                print("INSERTED =", count, question)

            options = {}
            answer = ""

            q = text.split(".", 1)[1].strip()

            if "A)" in q and "B)" in q and "C)" in q and "D)" in q:

                question = q.split("A)")[0].strip()

                partA = q.split("A)")[1]
                optionA = partA.split("B)")[0].strip()

                partB = partA.split("B)")[1]
                optionB = partB.split("C)")[0].strip()

                partC = partB.split("C)")[1]
                optionC = partC.split("D)")[0].strip()

                partD = partC.split("D)")[1]

                if "Answer:" in partD:
                    optionD = partD.split("Answer:")[0].strip()
                    answer = partD.split("Answer:")[1].strip()
                else:
                    optionD = partD.strip()

                options["A"] = optionA
                options["B"] = optionB
                options["C"] = optionC
                options["D"] = optionD

            else:
                question = q

        elif text.startswith("A)"):
            options["A"] = text[2:].strip()

        elif text.startswith("B)"):
            options["B"] = text[2:].strip()

        elif text.startswith("C)"):
            options["C"] = text[2:].strip()

        elif text.startswith("D)"):
            options["D"] = text[2:].strip()

        elif text.startswith("Answer:"):
            answer = text.replace("Answer:", "").strip()

    if question:

        cursor.execute("""
            INSERT INTO quiz_questions
            (
                lesson_id,
                question,
                option_a,
                option_b,
                option_c,
                option_d,
                correct_answer
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s)
        """, (
            lesson_id,
            question,
            options.get("A", ""),
            options.get("B", ""),
            options.get("C", ""),
            options.get("D", ""),
            answer
        ))

        count += 1
        print("INSERTED =", count, question)

    conn.commit()

    print("TOTAL INSERTED =", count)

    cursor.close()
    conn.close()
from datetime import datetime
from dateutil.relativedelta import relativedelta

@app.route("/payment-success")
def payment_success():

    if "user_id" not in session:
        return redirect("/login")

    course_id = request.args.get("course_id")
    payment_id = request.args.get("payment_id")

    conn = get_db()
    cursor = conn.cursor()

    purchase_date = datetime.now()
    expiry_date = purchase_date + relativedelta(months=6)

    cursor.execute("""
        INSERT INTO purchases
        (
            user_id,
            email,
            course_id,
            amount,
            payment_id,
            payment_status,
            purchase_date,
            expiry_date
        )
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
    """, (
        session["user_id"],
        session["email"],
        course_id,
        1.00,
        payment_id,
        "success",
        purchase_date,
        expiry_date
    ))

    conn.commit()

    cursor.close()
    conn.close()

    return redirect(f"/course/{course_id}")



@app.route('/')
def home():

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    search = request.args.get('search')

    query = "SELECT * FROM courses"
    params = []

    if search:
        query += " WHERE title LIKE %s"
        params.append(f"%{search}%")

    cursor.execute(query, tuple(params))
    courses = cursor.fetchall()

    cursor.execute("SELECT * FROM courses ORDER BY id DESC LIMIT 8")
    new_courses = cursor.fetchall()

    purchased_courses = []

    if 'user_id' in session:

        cursor.execute("""
            SELECT course_id
            FROM purchases
            WHERE user_id=%s
            AND payment_status='success'
            AND expiry_date >= NOW()
        """, (session['user_id'],))

        purchased_courses = [
            row['course_id'] for row in cursor.fetchall()
        ]

    cursor.close()
    conn.close()

    return render_template(
        "home.html",
        courses=courses,
        new_courses=new_courses,
        purchased_courses=purchased_courses
    )
    
# ---------------- REGISTER ----------------
@app.route('/register', methods=['GET', 'POST'])
def register():

    if request.method == 'POST':

        name = request.form['name'].strip()
        email = request.form['email'].strip().lower()
        password = request.form['password']

        # ✅ Always Student
        role = "student"

        hashed_password = generate_password_hash(password)

        conn = get_db()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            "SELECT id FROM users WHERE email=%s",
            (email,)
        )

        if cursor.fetchone():
            flash("Email already registered.", "danger")
            cursor.close()
            conn.close()
            return redirect(url_for("register"))

        cursor.execute("""
            INSERT INTO users
            (name,email,password,role)
            VALUES(%s,%s,%s,%s)
        """,(
            name,
            email,
            hashed_password,
            role
        ))

        conn.commit()

        cursor.close()
        conn.close()

        flash("Registration Successful. Please Login.","success")

        return redirect(url_for("login"))

    return render_template("register.html")



# ---------------- LOGIN ----------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    course_id = request.args.get("course_id")
    
    if request.method == 'POST':
        course_id = request.form.get("course_id")
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
            session['email'] = user[2]      # 👈 New line
            session['role'] = user[4]

            print("LOGIN SUCCESS → ROLE:", session['role'])

            if course_id:
                return redirect(url_for('course_detail', course_id=course_id))
            else:
                return redirect(url_for('dashboard'))
        else:
            return "Invalid Email or Password ❌"

    return render_template('login.html')    





@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    role = session.get('role')

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    # User ke courses nikaalo
    if role == "admin":

        cursor.execute("""
        SELECT *
        FROM courses
        ORDER BY id DESC
        """)

    elif role == "instructor":

        cursor.execute("""
        SELECT *
        FROM courses
        WHERE instructor_id=%s
        ORDER BY id DESC
        """, (user_id,))

    else:

        cursor.execute("""
        SELECT c.*
        FROM courses c
        JOIN enrollments e
        ON c.id=e.course_id
        WHERE e.user_id=%s
        ORDER BY c.id DESC
        """, (user_id,))

    courses = cursor.fetchall()

    progress_percent = 0

    cursor.close()
    conn.close()

    print("CURRENT ROLE =", role)

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
        courses=courses,
        role=session.get("role"),
        user_name=session.get("user_name")
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
@login_required
@instructor_required # @admin_required
def add_course():
    if request.method == "POST":
        title = request.form.get('title')
        description = request.form.get('description')
        video_url = request.form.get('video_url')
        price = request.form.get('price', 0)
        category = request.form.get('category')
        level = request.form.get('level')
        thumbnail = request.form.get('thumbnail')
        
        pdf_file = request.files.get("course_pdf")
        pdf_path = ""
        
        if pdf_file and pdf_file.filename != "":
            filename = secure_filename(pdf_file.filename)
            os.makedirs("uploads/pdfs", exist_ok=True)
            pdf_file.save(os.path.join("uploads/pdfs", filename))
            pdf_path = "uploads/pdfs/" + filename

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
        
        # ध्यान दें: आपकी SQL टेबल में 'pdf_path' कॉलम होना जरूरी है
        cursor.execute("""
            INSERT INTO courses (
                title, description, instructor_id, video_url, price, category, level, thumbnail, pdf_path
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            title, description, session['user_id'], video_url, price, category, level, thumbnail, pdf_path
        ))
        
        conn.commit()
        course_id = cursor.lastrowid
        
        generate_ai_quiz(title, course_id)
        
        cursor.close()
        conn.close()
        
        return redirect(url_for("add_lesson", course_id=course_id))
        
    return render_template('add_course.html')




@app.route('/add-assignment/<int:course_id>')
@login_required
@instructor_required
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
@login_required
@admin_required
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

    selected_lesson_id = request.args.get("lesson", type=int)
    # Login check
    if 'user_id' not in session:
        flash("Please login first.", "warning")
        return redirect(url_for("login"))

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    # Course
    cursor.execute("SELECT * FROM courses WHERE id=%s", (course_id,))
    course = cursor.fetchone()

    if not course:
        cursor.close()
        conn.close()
        return "Course not found", 404

    user_id = session.get('user_id')

  # ===========================
# 🔒 Role Based Access
# ===========================

    user_role = session.get("role")

    # Sirf Student ke liye purchase check
    if user_role == "student":

        cursor.execute("""
            SELECT *
            FROM purchases
            WHERE user_id=%s
            AND course_id=%s
            AND payment_status='success'
            AND expiry_date >= NOW()
        """, (user_id, course_id))

        purchased = cursor.fetchone()

        if not purchased:
            cursor.close()
            conn.close()

            flash(
                "Please purchase this course first to access the content.",
                "warning"
            )

            return redirect(url_for("courses"))

# Admin aur Instructor ko direct access

    # Lessons
    cursor.execute("""
        SELECT *
        FROM lessons
        WHERE course_id=%s
        ORDER BY lesson_order ASC
    """, (course_id,))

    lessons = cursor.fetchall()

    # Selected lesson decide karo
    if selected_lesson_id:
            current_lesson = next(
            (lesson for lesson in lessons if lesson["id"] == selected_lesson_id),
            None
            )
    else:
            current_lesson = lessons[0] if lessons else None

    selected_lesson = request.args.get("lesson")
    print("Selected Lesson =", selected_lesson)

    
    # ==========================
# Lesson Unlock Logic
# ==========================

    cursor.execute("""
    SELECT lesson_id
    FROM lesson_progress
    WHERE student_id=%s
    AND quiz_passed=1
    """, (user_id,))

    passed_lessons = [row["lesson_id"] for row in cursor.fetchall()]

    for i in range(len(lessons)):

        if i == 0:
            lessons[i]["locked"] = False
            continue

        previous_id = lessons[i - 1]["id"]

        if previous_id in passed_lessons:
            lessons[i]["locked"] = False
        else:
            lessons[i]["locked"] = True
    

    # Completed lessons
    cursor.execute("""
        SELECT lesson_id
        FROM progress
        WHERE user_id=%s
    """, (user_id,))

    completed_lessons = [row['lesson_id'] for row in cursor.fetchall()]

    cursor.execute("""
        SELECT lesson_id
        FROM progress
        WHERE user_id=%s
        AND last_watched=TRUE
        ORDER BY id DESC
        LIMIT 1
        """, (user_id,))

    last = cursor.fetchone()
    last_lesson_id = last['lesson_id'] if last else None

    # Progress
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
        course_id=course_id,
        current_lesson=current_lesson
    )



@app.route('/lesson/<int:lesson_id>')
def lesson_detail(lesson_id):

    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT *
        FROM lessons
        WHERE id=%s
    """, (lesson_id,))

    lesson = cursor.fetchone()

    if not lesson:
        cursor.close()
        conn.close()
        return "Lesson not found", 404

    cursor.close()
    conn.close()

    return render_template(
        "lesson_detail.html",
        lesson=lesson
    )




@app.route("/manage-course/<int:course_id>")
@login_required
def manage_course(course_id):

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT * FROM courses WHERE id=%s",
        (course_id,)
    )
    course = cursor.fetchone()

    cursor.execute("""
        SELECT *
        FROM lessons
        WHERE course_id=%s
        ORDER BY lesson_order
    """, (course_id,))

    lessons = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "manage_course.html",
        course=course,
        lessons=lessons
    )
    

@app.route("/delete-lesson/<int:lesson_id>")
@login_required
def delete_lesson(lesson_id):

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    # Lesson ka course_id nikaalo
    cursor.execute(
        "SELECT course_id FROM lessons WHERE id=%s",
        (lesson_id,)
    )

    lesson = cursor.fetchone()

    if not lesson:
        cursor.close()
        conn.close()
        return "Lesson Not Found"

    course_id = lesson["course_id"]

    # Lesson delete karo
    cursor.execute(
        "DELETE FROM lessons WHERE id=%s",
        (lesson_id,)
    )

    conn.commit()

    cursor.close()
    conn.close()

    return redirect(url_for("manage_course", course_id=course_id))
    
    

@app.route("/delete-course/<int:course_id>")
@login_required
def delete_course(course_id):

    conn = get_db()
    cursor = conn.cursor()

    # course ke lessons delete
    cursor.execute(
        "DELETE FROM lessons WHERE course_id=%s",
        (course_id,)
    )

    # course delete
    cursor.execute(
        "DELETE FROM courses WHERE id=%s",
        (course_id,)
    )

    conn.commit()

    cursor.close()
    conn.close()

    return redirect(url_for("courses"))


    
    
@app.route("/edit-lesson/<int:lesson_id>", methods=["GET", "POST"])
@login_required
def edit_lesson(lesson_id):

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    if request.method == "POST":

        title = request.form["title"]
        description = request.form["description"]
        youtube_url = request.form["youtube_url"]
        lesson_order = request.form["lesson_order"]

        pdf_path = request.form.get("old_pdf", "")
        ppt_path = request.form.get("old_ppt", "")
        quiz_docx_path = request.form.get("old_quiz_docx", "")

        pdf = request.files.get("pdf_file")

        if pdf and pdf.filename:
            filename = secure_filename(pdf.filename)

            os.makedirs("uploads/pdfs", exist_ok=True)

            pdf.save(os.path.join("uploads/pdfs", filename))

            print("PDF SAVED:", filename)
            print("FULL PATH:", os.path.abspath(os.path.join("uploads/pdfs", filename)))
            print("EXISTS:", os.path.exists(os.path.join("uploads/pdfs", filename)))

            pdf_path = "uploads/pdfs/" + filename

        ppt = request.files.get("ppt_file")

        if ppt and ppt.filename:
            filename = secure_filename(ppt.filename)

            os.makedirs("uploads/ppts", exist_ok=True)

            ppt.save(os.path.join("uploads/ppts", filename))
            
            
            
            print("PPT SAVED:", filename)
            print("FULL PATH:", os.path.abspath(os.path.join("uploads/ppts", filename)))
            print("EXISTS:", os.path.exists(os.path.join("uploads/ppts", filename)))
            

            ppt_path = "uploads/ppts/" + filename



            # ==========================
            # Quiz DOCX Upload
            # ==========================

        quiz_docx = request.files.get("quiz_docx")

        print("QUIZ FILE =", quiz_docx)

        if quiz_docx:
            print("FILENAME =", quiz_docx.filename)

        if quiz_docx and quiz_docx.filename:

            filename = secure_filename(quiz_docx.filename)

            os.makedirs("uploads/quizzes", exist_ok=True)

            quiz_path = os.path.join("uploads/quizzes", filename)

            quiz_docx.save(quiz_path)
            quiz_docx_path = quiz_path

            print("QUIZ PATH =", quiz_docx_path)

            # Purane quiz delete
            cursor.execute(
            "DELETE FROM quiz_questions WHERE lesson_id=%s",
            (lesson_id,)
            )

            conn.commit()
            print("CURRENT LESSON ID =", lesson_id)
            print("IMPORTING INTO LESSON =", lesson_id)
                # Naya quiz import
            parse_quiz_docx(quiz_path, lesson_id)

            print("QUIZ UPDATED")

            

        cursor.execute("""
        UPDATE lessons
        SET
            title=%s,
            description=%s,
            youtube_url=%s,
            pdf_file=%s,
            ppt_file=%s,
            quiz_docx=%s,
            lesson_order=%s
        WHERE id=%s
        """, (
            title,
            description,
            youtube_url,
            pdf_path,
            ppt_path,
            quiz_docx_path,
            lesson_order,
            lesson_id
        ))

        conn.commit()

        cursor.execute(
            "SELECT course_id FROM lessons WHERE id=%s",
            (lesson_id,)
        )

        lesson = cursor.fetchone()

        cursor.close()
        conn.close()

        return redirect(
            url_for(
                "manage_course",
                course_id=lesson["course_id"]
            )
        )

    cursor.execute(
        "SELECT * FROM lessons WHERE id=%s",
        (lesson_id,)
    )

    lesson = cursor.fetchone()

    cursor.close()
    conn.close()

    return render_template(
        "edit_lesson.html",
        lesson=lesson
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
    
    cursor.execute("""
    SELECT course_id
    FROM lessons
    WHERE id=%s
    """, (lesson_id,))

    lesson = cursor.fetchone()
    course_id = lesson[0]

    # 🔥 insert/update
    cursor.execute("""
    INSERT INTO progress
    (user_id, course_id, lesson_id, completed, last_watched)
    VALUES (%s, %s, %s, 1, 1)
    """, (user_id, course_id, lesson_id))

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


@app.route("/create-test-db")
def create_test_db():

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS courses (
        id INT AUTO_INCREMENT PRIMARY KEY,
        title VARCHAR(255)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS quizzes (
        id INT AUTO_INCREMENT PRIMARY KEY,
        course_id INT,
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
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT,
        course_id INT,
        score INT,
        passed TINYINT(1)
    )
    """)

    cursor.execute("""
    INSERT INTO courses (title)
    VALUES (%s)
    """, ("Python Course",))

    conn.commit()
    cursor.close()
    conn.close()

    return "DB Created"

@app.route("/tables")
def tables():

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SHOW TABLES")

    tables = cursor.fetchall()

    cursor.close()
    conn.close()

    return str(tables)



@app.route("/quiz/<int:lesson_id>", methods=["GET", "POST"])
def quiz(lesson_id):

        if "user_id" not in session:
            return redirect(url_for("login"))

        user_id = session["user_id"]

        conn = get_db()
        cursor = conn.cursor(dictionary=True)

        # Lesson se course_id nikalo
        cursor.execute("""
            SELECT course_id
            FROM lessons
            WHERE id=%s
        """, (lesson_id,))




        lesson = cursor.fetchone()

        if not lesson:
            cursor.close()
            conn.close()
            return "Lesson not found"

        course_id = lesson["course_id"]

        print("URL LESSON ID =", lesson_id)

        cursor.execute("""
        SELECT *
        FROM quiz_questions
        WHERE lesson_id=%s
        ORDER BY id
        """, (lesson_id,))

        quizzes = cursor.fetchall()

        print("TOTAL QUIZZES =", len(quizzes))

        for q in quizzes:
            print(q)



        # POST
        if request.method == "POST":
            
            import uuid
            
            certificate_id = "AIC-" + str(uuid.uuid4())[:8].upper()      

            score = 0

            for quiz in quizzes:
                print("------------------")
                print("Question :", f"question_{quiz['id']}")
                print("Selected :", request.form.get(f"question_{quiz['id']}"))
                print("Correct  :", quiz["correct_answer"])
                selected = request.form.get(f"question_{quiz['id']}")
                print("------------------------")
                print("Selected :", selected)
                print("Correct  :", quiz["correct_answer"])
                if selected and selected.strip().upper() == quiz["correct_answer"].strip().upper():
                    score += 1

            total = len(quizzes)

            status = "Passed"
            certificate_id = None

            if status == "Passed":
                certificate_id = str(uuid.uuid4())[:8].upper()

            if total > 0 and score < total * 0.5:
                status = "Failed"

            # Result Save
            cursor.execute("""
                INSERT INTO results
                (
                    student_id,
                    course_id,
                    score,
                    total,
                    status,
                    certificate_id
                )
                VALUES
                (%s,%s,%s,%s,%s,%s)
            """, (
                user_id,
                course_id,
                score,
                total,
                status,
                certificate_id
            ))

            conn.commit()

            cursor.close()
            conn.close()
            
            
            # Lesson Progress Save
            if status == "Passed":

                conn = get_db()
                cursor = conn.cursor()

                cursor.execute("""
                    INSERT INTO lesson_progress
                    (
                        student_id,
                        lesson_id,
                        quiz_passed
                    )
                    VALUES
                    (%s,%s,1)
                    ON DUPLICATE KEY UPDATE
                    quiz_passed=1
                """, (
                    user_id,
                    lesson_id
                ))

                conn.commit()

            cursor.close()
            conn.close()

            # Course ke saare lessons lao
            conn = get_db()
            cursor = conn.cursor(dictionary=True)

            cursor.execute("""
                SELECT id
                FROM lessons
                WHERE course_id=%s
                ORDER BY id
                """, (course_id,))

            all_lessons = cursor.fetchall()


            lesson_ids = [row["id"] for row in all_lessons]

            print("lesson_ids =", lesson_ids)
            print("lesson_id =", lesson_id)

            current_index = lesson_ids.index(int(lesson_id))

            is_last_lesson = (current_index == len(lesson_ids) - 1)

            next_lesson_id = None

            if not is_last_lesson:
                next_lesson_id = lesson_ids[current_index + 1]

            cursor.close()
            conn.close()



            percentage = round((score / total) * 100) if total else 0

            return render_template(
               "quiz_results.html",
                score=score,
                total=total,
                percentage=percentage,
                status=status,
                lesson_id=lesson_id,
                course_id=course_id,
                next_lesson_id=next_lesson_id,
                is_last_lesson=is_last_lesson
            )

        cursor.close()
        conn.close()

        return render_template(
            "quiz.html",
            quizzes=quizzes,
            lesson_id=lesson_id,
            course_id=course_id
        )
        
   
   
@app.route("/certificate/<int:course_id>")
def certificate(course_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    # ==========================================
    # CHECK COURSE COMPLETION
    # ==========================================

    cursor.execute("""
        SELECT COUNT(*) AS total_lessons
        FROM lessons
        WHERE course_id=%s
    """, (course_id,))
    total_lessons = cursor.fetchone()["total_lessons"]

    cursor.execute("""
        SELECT COUNT(*) AS completed_lessons
        FROM lesson_progress lp
        JOIN lessons l ON l.id = lp.lesson_id
        WHERE lp.student_id=%s
        AND lp.quiz_passed=1
        AND l.course_id=%s
    """, (user_id, course_id))

    completed_lessons = cursor.fetchone()["completed_lessons"]

    if completed_lessons < total_lessons:
        cursor.close()
        conn.close()

        return f"""
        <h2>⚠ Course Not Completed</h2>
        <p>Please complete all lessons and quizzes before downloading certificate.</p>
        <a href='/course/{course_id}'>⬅ Back To Course</a>
        """

    # ==========================================
    # CERTIFICATE DATA
    # ==========================================

    cursor.execute("""
        SELECT
            r.certificate_id,
            r.completed_at,
            u.name,
            c.title
        FROM results r
        JOIN users u ON u.id = r.student_id
        JOIN courses c ON c.id = r.course_id
        WHERE r.student_id=%s
        AND r.course_id=%s
        AND r.status='Passed'
        ORDER BY r.id DESC
        LIMIT 1
    """, (user_id, course_id))

    data = cursor.fetchone()

    cursor.close()
    conn.close()

    if not data:
        return "Certificate not found."

    # ==========================================
    # CREATE PDF
    # ==========================================

    temp = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".pdf"
    )

    pdf = canvas.Canvas(
        temp.name,
        pagesize=landscape(A4)
    )

    width, height = landscape(A4)

    # ==========================================
    # FILE PATHS
    # ==========================================

    logo_path = os.path.join(
        "static",
        "images",
        "certificate",
        "AICore_System_logo.jpeg"
    )

    stamp_path = os.path.join(
        "static",
        "images",
        "certificate",
        "stamp.png"
    )

    sign_path = os.path.join(
        "static",
        "images",
        "certificate",
        "sign.png"
    )

    # ==========================================
    # OUTER BORDER
    # ==========================================

    pdf.setStrokeColor(colors.HexColor("#1E3A8A"))
    pdf.setLineWidth(5)

    pdf.rect(
        20,
        20,
        width - 40,
        height - 40
    )

    # ==========================================
    # WATERMARK LOGO
    # ==========================================

    if os.path.exists(logo_path):

        pdf.saveState()

        try:
            pdf.setFillAlpha(0.08)
        except:
            pass

        pdf.drawImage(
            logo_path,
            width / 2 - 120,
            height / 2 - 120,
            width=240,
            height=240,
            mask="auto"
        )

        pdf.restoreState()

    # ==========================================
    # TOP LOGO
    # ==========================================

    if os.path.exists(logo_path):

        pdf.drawImage(
            logo_path,
            width / 2 - 50,
            height - 120,
            width=100,
            height=80,
            mask="auto"
        )

    # ==========================================
    # COMPANY NAME
    # ==========================================

    pdf.setFillColor(colors.HexColor("#1E3A8A"))
    pdf.setFont("Helvetica-Bold", 28)

    pdf.drawCentredString(
        width / 2,
        height - 150,
        "AICORESYSTEM"
    )

    # ==========================================
    # CERTIFICATE TITLE
    # ==========================================

    pdf.setFillColor(colors.HexColor("#2563EB"))
    pdf.setFont("Helvetica-Bold", 22)

    pdf.drawCentredString(
        width / 2,
        height - 190,
        "CERTIFICATE OF COMPLETION"
    )

    # ==========================================
    # PRESENTED TO
    # ==========================================

    pdf.setFillColor(colors.black)
    pdf.setFont("Helvetica", 14)

    pdf.drawCentredString(
        width / 2,
        height - 240,
        "This Certificate is proudly presented to"
    )

    # ==========================================
    # STUDENT NAME
    # ==========================================

    pdf.setFont("Helvetica-Bold", 30)

    pdf.drawCentredString(
        width / 2,
        height - 290,
        str(data["name"])
    )

    # ==========================================
    # COURSE NAME
    # ==========================================

    pdf.setFont("Helvetica", 16)

    pdf.drawCentredString(
        width / 2,
        height - 340,
        "For successfully completing the course"
    )

    pdf.setFont("Helvetica-Bold", 20)

    pdf.drawCentredString(
        width / 2,
        height - 375,
        str(data["title"])
    )

    # ==========================================
    # CERTIFICATE DETAILS
    # ==========================================

    pdf.setFont("Helvetica", 12)

    pdf.drawCentredString(
        width / 2,
        height - 430,
        f"Certificate ID : {data['certificate_id']}"
    )

    pdf.drawCentredString(
        width / 2,
        height - 450,
        f"Date : {data['completed_at']}"
    )

    # ==========================================
    # STAMP
    # ==========================================

    if os.path.exists(stamp_path):

        pdf.drawImage(
            stamp_path,
            70,
            70,
            width=140,
            height=140,
            mask="auto"
        )

    # ==========================================
    # SIGNATURE IMAGE
    # ==========================================

    if os.path.exists(sign_path):

        pdf.drawImage(
            sign_path,
            width - 260,
            120,
            width=120,
            height=50,
            mask="auto"
        )

    # ==========================================
    # SIGNATURE LINE
    # ==========================================

    pdf.line(
        width - 280,
        110,
        width - 120,
        110
    )

    pdf.setFont("Helvetica-Bold", 12)

    pdf.drawCentredString(
        width - 200,
        90,
        "Usha Kumari"
    )

    pdf.setFont("Helvetica", 11)

    pdf.drawCentredString(
        width - 200,
        72,
        "CEO & Director"
    )

    pdf.drawCentredString(
        width - 200,
        56,
        "AICORESYSTEM"
    )

    # ==========================================
    # FOOTER BAR
    # ==========================================

    pdf.setFillColor(colors.HexColor("#1E3A8A"))

    pdf.rect(
        20,
        20,
        width - 40,
        25,
        fill=1
    )

    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica", 8)

    pdf.drawCentredString(
        width / 2,
        30,
        "www.aicoresystem.in | Ahmedabad, Gujarat | helpdesk@aicoresystem.in"
    )

    # ==========================================
    # SAVE PDF
    # ==========================================

    pdf.save()

    return send_file(
        temp.name,
        as_attachment=True,
        download_name="AICore_Certificate.pdf"
    )


    
@app.route("/my-results")
def my_results():

    conn = get_db()

    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT * FROM results
        WHERE student_id=%s
    """, (1,))

    results = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "my_results.html",
        results=results
    )

@app.route("/student-dashboard")
def student_dashboard():

    conn = get_db()

    cursor = conn.cursor(dictionary=True)

    # RESULTS
    cursor.execute("""
    SELECT * FROM results
    WHERE student_id=%s
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

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS results (
        id INT AUTO_INCREMENT PRIMARY KEY,
        student_id INT,
        course_id INT,
        score INT,
        total INT,
        status VARCHAR(50)
    )
    """)

    conn.commit()
    cursor.close()
    conn.close()

    return "Results Table Created"

def generate_ai_quiz(course_name, course_id):

    print("AI Quiz Function Working")

    import requests
    import json

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
"Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}",
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

    text = text.replace("```json", "")
    text = text.replace("```", "")
    text = text.strip()

    try:
        quizzes = json.loads(text)

    except Exception as e:
        print("JSON ERROR:", e)
        print(text)
        return

    conn = get_db()
    cursor = conn.cursor()

    for quiz in quizzes:

        cursor.execute("""
        INSERT INTO quizzes
        (course_id, question, option1, option2, option3, option4, correct_answer)

        VALUES (%s, %s, %s, %s, %s, %s, %s)
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
    cursor.close()
    conn.close()

    print("50 AI quizzes added successfully")



@app.route("/add_lesson/<int:course_id>", methods=["GET", "POST"])
def add_lesson(course_id):

    if request.method == "POST":

        title = request.form["title"]
        description = request.form["description"]
        youtube_url = request.form["youtube_url"]

        # Auto convert YouTube link to Embed URL
        if "youtu.be/" in youtube_url:
            video_id = youtube_url.split("/")[-1]
            youtube_url = f"https://www.youtube-nocookie.com/embed/{video_id}"

        elif "watch?v=" in youtube_url:
            video_id = youtube_url.split("watch?v=")[1].split("&")[0]
            youtube_url = f"https://www.youtube-nocookie.com/embed/{video_id}"

        lesson_order = request.form["lesson_order"]

        # ---------------- PDF Upload ----------------

        pdf_path = ""

        pdf = request.files.get("pdf_file")

        if pdf and pdf.filename:

            filename = secure_filename(pdf.filename)

            os.makedirs("uploads/pdfs", exist_ok=True)

            pdf.save(os.path.join("uploads/pdfs", filename))

            pdf_path = "uploads/pdfs/" + filename

            print("=" * 50)
            print("PDF SAVED")
            print("Filename :", filename)
            print("=" * 50)

        # ---------------- PPT Upload ----------------

        ppt_path = ""

        ppt = request.files.get("ppt_file")

        if ppt and ppt.filename:

            filename = secure_filename(ppt.filename)

            os.makedirs("uploads/ppts", exist_ok=True)

            ppt.save(os.path.join("uploads/ppts", filename))

            ppt_path = "uploads/ppts/" + filename

            print("=" * 50)
            print("PPT SAVED")
            print("Filename :", filename)
            print("=" * 50)

        # ---------------- Quiz DOCX Upload ----------------

        quiz_path = ""

        quiz = request.files.get("quiz_docx")

        if quiz and quiz.filename:

            filename = secure_filename(quiz.filename)

            os.makedirs("uploads/quizzes", exist_ok=True)

            quiz.save(os.path.join("uploads/quizzes", filename))

            quiz_path = "uploads/quizzes/" + filename

            print("=" * 50)
            print("QUIZ SAVED")
            print("Filename :", filename)
            print("=" * 50)

        # ---------------- Database ----------------

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
        INSERT INTO lessons
        (
            course_id,
            title,
            description,
            youtube_url,
            pdf_file,
            ppt_file,
            quiz_docx,
            lesson_order
        )
        VALUES
        (
            %s,%s,%s,%s,%s,%s,%s,%s
        )
        """, (
            course_id,
            title,
            description,
            youtube_url,
            pdf_path,
            ppt_path,
            quiz_path,
            lesson_order
        ))

        conn.commit()
        lesson_id = cursor.lastrowid

        if quiz_path:
            parse_quiz_docx(quiz_path, lesson_id)

        cursor.close()
        conn.close()

        return redirect(url_for("course_detail", course_id=course_id))

    return render_template("add_lesson.html", course_id=course_id)



@app.route("/check-purchase/<int:course_id>")
def check_purchase(course_id):

    if "user_id" not in session:
        return {"purchased": False}

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id
        FROM purchases
        WHERE user_id=%s
        AND course_id=%s
        AND payment_status='success'
        AND expiry_date >= NOW()
    """,(session["user_id"],course_id))

    purchased = cursor.fetchone() is not None

    cursor.close()
    conn.close()

    return {"purchased": purchased}



@app.route("/search-courses")
def search_courses():
    q = request.args.get("q", "")

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT id,title
        FROM courses
        WHERE title LIKE %s
    """, (f"%{q}%",))

    courses = cursor.fetchall()

    cursor.close()
    conn.close()

    return jsonify(courses)




# @app.route("/quiz/<int:course_id>")
# def quiz_page(course_id):

#     conn = get_db()

#     cursor = conn.cursor(dictionary=True)

#     cursor.execute(
#         "SELECT * FROM quizzes WHERE course_id=%s ORDER BY RAND() LIMIT 100",
#         (course_id,)
#     )

#     quizzes = cursor.fetchall()

#     conn.close()

#     return render_template(
#         "quiz.html",
#         quizzes=quizzes
#     )



# @app.route("/my_courses")
# def my_courses_page():

#     return render_template("my_courses.html")


import os

@app.route('/uploads/<path:filename>')
def uploaded_files(filename):
    return send_from_directory(
        os.path.join(app.root_path, 'uploads'),
        filename
    )

# if __name__ == "__main__":
#     app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))



if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=True
    )