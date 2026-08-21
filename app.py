import os
from uuid import uuid4
from datetime import datetime
from functools import wraps
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, abort, flash, jsonify, redirect, render_template, request, send_from_directory, url_for
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_, func
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

load_dotenv()
BASE = Path(__file__).resolve().parent
# Set UPLOAD_DIR in production to a persistent mounted directory. The default
# stays inside the project so uploads work immediately on a local installation.
UPLOADS = Path(os.getenv("UPLOAD_DIR", str(BASE / "static" / "uploads")))
UPLOADS.mkdir(parents=True, exist_ok=True)
ALLOWED = {"pdf", "ppt", "pptx", "doc", "docx", "jpg", "jpeg", "png"}

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.getenv("SECRET_KEY", "change-this-in-production"),
    SQLALCHEMY_DATABASE_URI=os.getenv("DATABASE_URL", "sqlite:///smartstudy.db"),
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    # PythonAnywhere closes idle MySQL connections after five minutes.
    SQLALCHEMY_ENGINE_OPTIONS={"pool_recycle": 280, "pool_pre_ping": True},
    UPLOAD_FOLDER=str(UPLOADS),
    MAX_CONTENT_LENGTH=50 * 1024 * 1024,
)
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

class Department(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    subjects = db.relationship("Subject", backref="department", lazy=True)

class Subject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey("department.id"), nullable=False)
    academic_year = db.Column(db.String(30), default="4")
    semester = db.Column(db.String(30), default="1")

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default="student", nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey("department.id"))
    academic_year = db.Column(db.String(30))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    department = db.relationship("Department")

class Resource(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False, index=True)
    description = db.Column(db.Text, default="")
    resource_type = db.Column(db.String(50), nullable=False)
    file_path = db.Column(db.String(255), default="")
    department_id = db.Column(db.Integer, db.ForeignKey("department.id"), nullable=False)
    academic_year = db.Column(db.String(30), nullable=False)
    semester = db.Column(db.String(30), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey("subject.id"))
    unit = db.Column(db.String(40), default="")
    topic = db.Column(db.String(150), default="")
    tags = db.Column(db.String(500), default="")
    exam_type = db.Column(db.String(80), default="")
    uploader_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    view_count = db.Column(db.Integer, default=0)
    download_count = db.Column(db.Integer, default=0)
    approval_status = db.Column(db.String(20), default="approved")
    department = db.relationship("Department")
    subject = db.relationship("Subject")
    uploader = db.relationship("User", foreign_keys=[uploader_id])
    ratings = db.relationship("Rating", backref="resource", cascade="all, delete-orphan", lazy=True)
    summary = db.relationship("Summary", backref="resource", uselist=False, cascade="all, delete-orphan")
    @property
    def average_rating(self):
        return round(sum(r.rating for r in self.ratings) / len(self.ratings), 1) if self.ratings else 0

class Bookmark(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    resource_id = db.Column(db.Integer, db.ForeignKey("resource.id"), nullable=False)
    category = db.Column(db.String(50), default="Read Later")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint("user_id", "resource_id", name="unique_bookmark"),)
    resource = db.relationship("Resource")

class Rating(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    resource_id = db.Column(db.Integer, db.ForeignKey("resource.id"), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    review = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship("User")
    __table_args__ = (db.UniqueConstraint("user_id", "resource_id", name="unique_rating"),)

class Summary(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    resource_id = db.Column(db.Integer, db.ForeignKey("resource.id"), unique=True, nullable=False)
    summary = db.Column(db.Text, nullable=False)
    key_concepts = db.Column(db.Text, default="")
    important_points = db.Column(db.Text, default="")
    generated_at = db.Column(db.DateTime, default=datetime.utcnow)

class Activity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    resource_id = db.Column(db.Integer, db.ForeignKey("resource.id"))
    activity_type = db.Column(db.String(30), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id): return db.session.get(User, int(user_id))

def roles(*allowed):
    def decorator(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role not in allowed: abort(403)
            return fn(*args, **kwargs)
        return wrapped
    return decorator

def track(resource_id, kind):
    if current_user.is_authenticated:
        db.session.add(Activity(user_id=current_user.id, resource_id=resource_id, activity_type=kind))

def resource_query():
    q = Resource.query.filter_by(approval_status="approved")
    term = request.args.get("q", "").strip()
    if term:
        q = q.outerjoin(Subject)
        words = term.split()
        for word in words:
            p = f"%{word}%"
            q = q.filter(or_(Resource.title.ilike(p), Resource.description.ilike(p), Resource.topic.ilike(p), Resource.tags.ilike(p), Resource.unit.ilike(p), Subject.name.ilike(p)))
    fields = {"department": Resource.department_id, "year": Resource.academic_year, "semester": Resource.semester, "subject": Resource.subject_id, "unit": Resource.unit, "type": Resource.resource_type}
    for key, col in fields.items():
        if request.args.get(key): q = q.filter(col == request.args[key])
    return q

def recommendations(user=None, subject_id=None, limit=6):
    query = Resource.query.filter_by(approval_status="approved")
    if subject_id: query = query.filter_by(subject_id=subject_id)
    elif user and user.department_id: query = query.filter_by(department_id=user.department_id)
    return sorted(query.all(), key=lambda r: (r.average_rating * 3 + r.view_count / 10 + (2 if user and r.subject_id in [a.resource.subject_id for a in Bookmark.query.filter_by(user_id=user.id).all()] else 0)), reverse=True)[:limit]

@app.route("/")
def index():
    return render_template("index.html", popular=Resource.query.filter_by(approval_status="approved").order_by(Resource.view_count.desc()).limit(3).all(), recent=Resource.query.order_by(Resource.upload_date.desc()).limit(3).all())

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        if User.query.filter_by(email=request.form["email"].lower()).first(): flash("That email is already registered.", "error")
        else:
            user = User(name=request.form["name"], email=request.form["email"].lower(), password_hash=generate_password_hash(request.form["password"]), role=request.form.get("role", "student"), department_id=request.form.get("department") or None, academic_year=request.form.get("academic_year"))
            db.session.add(user); db.session.commit(); login_user(user); return redirect(url_for("dashboard"))
    return render_template("register.html", departments=Department.query.all())

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = User.query.filter_by(email=request.form["email"].lower()).first()
        if user and check_password_hash(user.password_hash, request.form["password"]): login_user(user); return redirect(url_for("dashboard"))
        flash("Invalid email or password.", "error")
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout(): logout_user(); return redirect(url_for("index"))

@app.route("/dashboard")
@login_required
def dashboard():
    if current_user.role == "admin":
        return render_template("admin.html", users=User.query.count(), resources=Resource.query.count(), pending=Resource.query.filter_by(approval_status="pending").count(), departments=Department.query.count(), popular=recommendations(limit=5))
    mine = Resource.query.filter_by(uploader_id=current_user.id).all()
    activities = Activity.query.filter_by(user_id=current_user.id, activity_type="view").order_by(Activity.created_at.desc()).limit(5).all()
    return render_template("dashboard_live.html", mine=mine, bookmarks=Bookmark.query.filter_by(user_id=current_user.id).all(), recent=[a.resource_id for a in activities], recommended=recommendations(current_user), is_faculty=current_user.role == "faculty")

@app.route("/resources")
def browse_resources():
    return render_template("resources.html", resources=resource_query().order_by(Resource.upload_date.desc()).all(), departments=Department.query.all(), subjects=Subject.query.all())

@app.route("/resource/<int:resource_id>")
def resource_detail(resource_id):
    resource = db.get_or_404(Resource, resource_id); resource.view_count += 1; track(resource.id, "view"); db.session.commit()
    marked = current_user.is_authenticated and Bookmark.query.filter_by(user_id=current_user.id, resource_id=resource.id).first()
    return render_template("resource_details.html", resource=resource, marked=marked, related=recommendations(current_user if current_user.is_authenticated else None, resource.subject_id))

@app.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    if request.method == "POST":
        file = request.files.get("file")
        if not file or not file.filename: flash("Choose a file to store with this resource.", "error"); return redirect(request.url)
        if "." not in file.filename or file.filename.rsplit(".", 1)[-1].lower() not in ALLOWED: flash("Unsupported file type.", "error"); return redirect(request.url)
        ext = file.filename.rsplit(".", 1)[-1].lower()
        filename = f"{uuid4().hex}.{ext}"
        file.save(UPLOADS / filename)
        department_id = int(request.form["department"])
        subject_id = request.form.get("subject") or None
        new_subject = request.form.get("new_subject", "").strip()
        if new_subject:
            subject = Subject.query.filter_by(name=new_subject, department_id=department_id, academic_year=request.form["academic_year"], semester=request.form["semester"]).first()
            if not subject:
                subject = Subject(name=new_subject, department_id=department_id, academic_year=request.form["academic_year"], semester=request.form["semester"])
                db.session.add(subject); db.session.flush()
            subject_id = subject.id
        if not subject_id:
            (UPLOADS / filename).unlink(missing_ok=True)
            flash("Select an existing course or add a new one.", "error")
            return redirect(request.url)
        # Shared-library mode: every valid upload is immediately discoverable.
        # Moderation can be reintroduced later with an explicit admin workflow.
        r = Resource(title=request.form["title"], description=request.form.get("description", ""), resource_type=request.form["resource_type"], file_path=filename, department_id=department_id, academic_year=request.form["academic_year"], semester=request.form["semester"], subject_id=subject_id, unit=request.form.get("unit", ""), topic=request.form.get("topic", ""), tags=request.form.get("tags", ""), exam_type=request.form.get("exam_type", ""), uploader_id=current_user.id, approval_status="approved")
        db.session.add(r); db.session.flush(); track(r.id, "upload"); db.session.commit(); flash("Resource uploaded successfully.", "success"); return redirect(url_for("resource_detail", resource_id=r.id))
    return render_template("upload_resource.html", departments=Department.query.all(), subjects=Subject.query.all())

@app.route("/question-papers")
def question_papers():
    return render_template("resources.html", resources=resource_query().filter_by(resource_type="Question Paper").all(), departments=Department.query.all(), subjects=Subject.query.all(), question_papers=True)

@app.route("/bookmarks")
@login_required
def bookmarks(): return render_template("bookmarks.html", bookmarks=Bookmark.query.filter_by(user_id=current_user.id).order_by(Bookmark.created_at.desc()).all())

@app.route("/my-uploads")
@login_required
def my_uploads():
    items = Resource.query.filter_by(uploader_id=current_user.id).order_by(Resource.upload_date.desc()).all()
    return render_template("my_uploads.html", resources=items)

@app.post("/api/bookmark/<int:resource_id>")
@login_required
def toggle_bookmark(resource_id):
    item = Bookmark.query.filter_by(user_id=current_user.id, resource_id=resource_id).first()
    if item: db.session.delete(item); saved = False
    else: db.session.add(Bookmark(user_id=current_user.id, resource_id=resource_id, category=request.json.get("category", "Read Later") if request.is_json else "Read Later")); track(resource_id, "bookmark"); saved = True
    db.session.commit(); return jsonify(saved=saved)

@app.post("/api/rating/<int:resource_id>")
@login_required
def rate(resource_id):
    data = request.get_json(); value = int(data.get("rating", 0))
    if value not in range(1, 6): return jsonify(error="Rating must be 1–5."), 400
    item = Rating.query.filter_by(user_id=current_user.id, resource_id=resource_id).first()
    if item: item.rating, item.review = value, data.get("review", "")
    else: db.session.add(Rating(user_id=current_user.id, resource_id=resource_id, rating=value, review=data.get("review", "")))
    db.session.commit(); return jsonify(average=db.get_or_404(Resource, resource_id).average_rating)

@app.get("/api/suggestions")
def suggestions():
    q = request.args.get("q", "")
    if len(q) < 2: return jsonify([])
    return jsonify([r.title for r in Resource.query.filter(Resource.title.ilike(f"%{q}%")).limit(6).all()])

@app.get("/api/recommendations")
def recommendation_api():
    subject = request.args.get("subject", type=int)
    items = recommendations(current_user if current_user.is_authenticated else None, subject)
    return jsonify([{"id": r.id, "title": r.title, "type": r.resource_type, "rating": r.average_rating, "subject": r.subject.name if r.subject else "General"} for r in items])

@app.get("/api/live-activity")
@login_required
def live_activity():
    """Shared activity feed; polled by clients for PythonAnywhere WSGI compatibility."""
    after = request.args.get("after", 0, type=int)
    activities = Activity.query.filter(Activity.id > after).order_by(Activity.id.desc()).limit(12).all()
    items = []
    for activity in reversed(activities):
        resource = db.session.get(Resource, activity.resource_id) if activity.resource_id else None
        actor = db.session.get(User, activity.user_id)
        if resource and actor:
            action = {"upload": "uploaded", "view": "viewed", "download": "downloaded", "bookmark": "bookmarked"}.get(activity.activity_type, activity.activity_type)
            items.append({"id": activity.id, "text": f"{actor.name} {action} {resource.title}", "resource_id": resource.id, "at": activity.created_at.strftime("%H:%M")})
    return jsonify(items=items, latest_id=activities[0].id if activities else after, resource_count=Resource.query.filter_by(approval_status="approved").count())

@app.post("/api/summary/<int:resource_id>")
@login_required
def generate_summary(resource_id):
    resource = db.get_or_404(Resource, resource_id)
    # A deterministic local summary keeps the prototype functional without an API key.
    text = (resource.description + " " + resource.tags + " " + resource.topic).strip() or resource.title
    summary = Summary.query.filter_by(resource_id=resource.id).first()
    generated = f"{resource.title} focuses on {resource.topic or resource.subject.name if resource.subject else 'the listed study topic'}. This resource helps learners review {text[:280]}. Use it alongside related material to connect concepts, examples, and exam preparation."
    if not summary: summary = Summary(resource_id=resource.id, summary=generated, key_concepts=resource.tags or resource.topic, important_points=f"Review {resource.unit or 'the key unit'}; practise likely exam questions; revisit definitions."); db.session.add(summary)
    db.session.commit(); return jsonify(summary=summary.summary, concepts=summary.key_concepts, points=summary.important_points)

@app.route("/download/<int:resource_id>")
def download(resource_id):
    r = db.get_or_404(Resource, resource_id)
    if not r.file_path: abort(404)
    r.download_count += 1; track(r.id, "download"); db.session.commit()
    return send_from_directory(app.config["UPLOAD_FOLDER"], r.file_path, as_attachment=True)

@app.route("/file/<int:resource_id>")
def preview_file(resource_id):
    """Serve the stored resource in-browser so it can be retrieved later."""
    r = db.get_or_404(Resource, resource_id)
    if not r.file_path: abort(404)
    return send_from_directory(app.config["UPLOAD_FOLDER"], r.file_path)

@app.post("/admin/resource/<int:resource_id>/<action>")
@login_required
@roles("admin")
def moderate(resource_id, action):
    r = db.get_or_404(Resource, resource_id)
    if action == "approve": r.approval_status = "approved"
    elif action == "remove": db.session.delete(r)
    db.session.commit(); return redirect(url_for("dashboard"))

def seed():
    # Seed defensively: Flask's development reloader can briefly import twice.
    if User.query.filter_by(email="admin@smartstudy.test").first(): return
    cs = Department.query.filter_by(name="Computer Science").first()
    ece = Department.query.filter_by(name="Electronics & Communication").first()
    if not cs: cs = Department(name="Computer Science"); db.session.add(cs)
    if not ece: ece = Department(name="Electronics & Communication"); db.session.add(ece)
    db.session.flush()
    dbms = Subject.query.filter_by(name="Database Management Systems", department_id=cs.id).first()
    ml = Subject.query.filter_by(name="Machine Learning", department_id=cs.id).first()
    if not dbms: dbms = Subject(name="Database Management Systems", department_id=cs.id, academic_year="3", semester="1"); db.session.add(dbms)
    if not ml: ml = Subject(name="Machine Learning", department_id=cs.id, academic_year="4", semester="1"); db.session.add(ml)
    db.session.flush()
    faculty = User(name="Dr. Priya Nair", email="faculty@smartstudy.test", password_hash=generate_password_hash("faculty123"), role="faculty", department_id=cs.id, academic_year="4")
    admin = User(name="Platform Admin", email="admin@smartstudy.test", password_hash=generate_password_hash("admin123"), role="admin", department_id=cs.id)
    student = User(name="Aarav Student", email="student@smartstudy.test", password_hash=generate_password_hash("student123"), role="student", department_id=cs.id, academic_year="4")
    db.session.add_all([faculty, admin, student]); db.session.flush()
    resources = [
      Resource(title="DBMS Unit 3: Normalization Notes", description="Clear notes on functional dependencies, normal forms and lossless decomposition.", resource_type="Notes", department_id=cs.id, academic_year="3", semester="1", subject_id=dbms.id, unit="Unit 3", topic="Normalization", tags="dbms, normalization, functional dependencies, 3nf, bcnf", uploader_id=faculty.id, view_count=142),
      Resource(title="Machine Learning End Semester 2025", description="University previous question paper with regression, classification and clustering.", resource_type="Question Paper", department_id=cs.id, academic_year="4", semester="1", subject_id=ml.id, unit="All Units", topic="Machine Learning", tags="machine learning, question paper, regression, classification", exam_type="End Semester", uploader_id=faculty.id, view_count=195),
      Resource(title="ML Quick Revision: Supervised Learning", description="Exam-ready revision guide for classification and regression algorithms.", resource_type="Important Questions", department_id=cs.id, academic_year="4", semester="1", subject_id=ml.id, unit="Unit 2", topic="Supervised Learning", tags="ml, regression, classification, revision", uploader_id=faculty.id, view_count=88),
    ]
    db.session.add_all(resources); db.session.commit()
    db.session.add_all([Rating(user_id=student.id, resource_id=resources[0].id, rating=5, review="Excellent exam preparation notes."), Rating(user_id=student.id, resource_id=resources[1].id, rating=4, review="Very useful practice paper.")]); db.session.commit()

def initialize_database():
    """Run manually on first local/production deployment, not during WSGI import."""
    with app.app_context():
        db.create_all()
        seed()

if __name__ == "__main__":
    initialize_database()
    app.run(debug=True)
