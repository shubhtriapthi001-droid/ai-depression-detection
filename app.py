import os
from functools import wraps

from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from flask_cors import CORS

from database.models import Assessment, Progress, User, db

load_dotenv()

QUESTIONS = [
    "Little interest or pleasure in doing things.",
    "Feeling down, depressed, or hopeless.",
    "Trouble falling or staying asleep, or sleeping too much.",
    "Feeling tired or having little energy.",
    "Poor appetite or overeating.",
    "Feeling bad about yourself, or that you are a failure or have let yourself or your family down.",
    "Trouble concentrating on things, such as reading the newspaper or watching television.",
    "Moving or speaking so slowly that other people could have noticed? Or the opposite, being so fidgety or restless that you have been moving around a lot more than usual.",
    "Thoughts that you would be better off dead or of hurting yourself in some way.",
]
OPTIONS = ["Not at all", "Several days", "More than half the days", "Nearly every day"]


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-only-change-me")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///app.db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)
    CORS(app)
    with app.app_context():
        db.create_all()

    def current_user():
        return User.query.get(session["user_id"]) if session.get("user_id") else None

    def login_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_user():
                return redirect(url_for("login", next=request.path))
            return view(*args, **kwargs)
        return wrapped

    def severity(score):
        if score <= 4:
            return "Minimal"
        if score <= 9:
            return "Mild"
        if score <= 14:
            return "Moderate"
        if score <= 19:
            return "Moderately severe"
        return "Severe"

    def personalized_support(answers, severity_band):
        support = {
            "general": {
                "Minimal": "Keep noticing how you feel, protect your routines, and use small wellbeing practices that feel realistic for you.",
                "Mild": "Choose one manageable supportive step today and consider talking with someone you trust if these experiences continue.",
                "Moderate": "Consider arranging a conversation with a qualified mental health professional while using small, practical routines for daily support.",
                "Moderately severe": "Professional support is especially worth considering. Ask a qualified clinician or counsellor to help you review what you have been experiencing.",
                "Severe": "Please seek professional support as soon as possible. A qualified clinician can help you understand your experiences and discuss appropriate care.",
            },
            "symptoms": [],
        }
        symptom_suggestions = [
            (0, "Interest and enjoyment", "Try one low-pressure activity you used to enjoy, or explore a small new activity without expecting yourself to feel perfect."),
            (1, "Mood support", "Share how you have been feeling with a trusted person. Starting with one honest sentence is enough."),
            (2, "Sleep and rest", "Keep a gentle wind-down routine, make sleep and wake times more consistent, and seek professional advice if sleep difficulties continue."),
            (3, "Energy", "Break the day into one or two manageable tasks, take regular pauses, and treat rest as part of caring for yourself."),
            (6, "Concentration", "Try shorter study or work blocks with planned breaks. Write down the next smallest task instead of holding the whole list in your head."),
        ]
        for index, title, message in symptom_suggestions:
            if answers[index] > 0:
                support["symptoms"].append({"title": title, "message": message})
        if answers[0] > 0 or answers[1] > 0:
            support["symptoms"].append({
                "title": "Stay connected",
                "message": "Consider a gentle check-in with a supportive friend, family member, teacher, or counsellor. Connection can be a message, call, or shared meal.",
            })
        support["safety"] = answers[8] > 0
        return support

    def assessment_payload(assessment):
        return {
            "id": assessment.id,
            "score": assessment.total_score,
            "severity": assessment.severity_band,
            "answers": assessment.answers,
            "date": assessment.created_at.strftime("%b %d, %Y"),
            "safety_flag": int(assessment.answers[8]) > 0,
            "support": personalized_support(assessment.answers, assessment.severity_band),
        }

    @app.context_processor
    def inject_globals():
        return {"current_user": current_user(), "project_name": "AI Depression Tracker"}

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if request.method == "POST":
            data = request.form
            name, email, password = data.get("name", "").strip(), data.get("email", "").strip().lower(), data.get("password", "")
            try:
                age = int(data.get("age", "0"))
            except ValueError:
                age = 0
            if not name or "@" not in email or not 13 <= age <= 120 or len(password) < 8 or password != data.get("confirm_password"):
                return render_template("register.html", error="Please check your details. Use an 8+ character password and a valid age.", form=data)
            if User.query.filter_by(email=email).first():
                return render_template("register.html", error="An account with this email already exists.", form=data)
            user = User(name=name, email=email, age=age, gender=data.get("gender", "Prefer not to say"))
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            session["user_id"] = user.id
            return redirect(url_for("questionnaire"))
        return render_template("register.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            user = User.query.filter_by(email=request.form.get("email", "").strip().lower()).first()
            if not user or not user.check_password(request.form.get("password", "")):
                return render_template("login.html", error="Email or password not recognised.")
            session.clear()
            session["user_id"] = user.id
            return redirect(request.args.get("next") or url_for("progress"))
        return render_template("login.html")

    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("index"))

    @app.route("/questionnaire")
    @login_required
    def questionnaire():
        return render_template("questionnaire.html", questions=QUESTIONS, options=OPTIONS)

    @app.route("/analyze")
    @login_required
    def analyze():
        return render_template("analysis.html")

    @app.route("/results")
    @login_required
    def results():
        assessment = Assessment.query.filter_by(user_id=session["user_id"]).order_by(Assessment.created_at.desc(), Assessment.id.desc()).first()
        if not assessment:
            return redirect(url_for("questionnaire"))
        return render_template("results.html", assessment=assessment_payload(assessment))

    @app.route("/recommendations")
    @login_required
    def recommendations():
        assessment = Assessment.query.filter_by(user_id=session["user_id"]).order_by(Assessment.created_at.desc(), Assessment.id.desc()).first()
        return render_template("recommendations.html", assessment=assessment_payload(assessment) if assessment else None)

    @app.route("/progress")
    @login_required
    def progress():
        assessments = Assessment.query.filter_by(user_id=session["user_id"]).order_by(Assessment.created_at.asc()).all()
        return render_template("progress.html", assessments=[assessment_payload(item) for item in assessments])

    @app.route("/locator")
    def locator():
        return render_template("locator.html", maps_key=os.getenv("GOOGLE_MAPS_API_KEY", ""))

    @app.route("/about")
    def about():
        return render_template("about.html")

    @app.post("/api/register")
    def api_register():
        data = request.get_json(silent=True) or {}
        if User.query.filter_by(email=data.get("email", "").lower()).first():
            return jsonify(error="Email already registered"), 409
        try:
            age = int(data.get("age", 0))
        except (TypeError, ValueError):
            age = 0
        if not data.get("name") or "@" not in data.get("email", "") or not 13 <= age <= 120 or len(data.get("password", "")) < 8:
            return jsonify(error="Name, valid email, age 13-120, and an 8+ character password are required"), 400
        user = User(name=data["name"].strip(), email=data["email"].lower().strip(), age=age, gender=data.get("gender", "Prefer not to say"))
        user.set_password(data["password"])
        db.session.add(user)
        db.session.commit()
        session["user_id"] = user.id
        return jsonify(message="Account created", user_id=user.id), 201

    @app.post("/api/login")
    def api_login():
        data = request.get_json(silent=True) or {}
        user = User.query.filter_by(email=data.get("email", "").lower().strip()).first()
        if not user or not user.check_password(data.get("password", "")):
            return jsonify(error="Invalid credentials"), 401
        session["user_id"] = user.id
        return jsonify(message="Logged in")

    @app.post("/api/assessment")
    @login_required
    def api_assessment():
        data = request.get_json(silent=True) or {}
        answers = data.get("answers")
        if not isinstance(answers, list) or len(answers) != 9 or any(not isinstance(item, int) or item not in range(4) for item in answers):
            return jsonify(error="Exactly nine answers, each scored 0 to 3, are required"), 400
        item = Assessment(user_id=session["user_id"], answers=answers, total_score=sum(answers), severity_band=severity(sum(answers)))
        db.session.add(item)
        db.session.flush()
        db.session.add(Progress(user_id=session["user_id"], assessment_id=item.id, score=item.total_score))
        db.session.commit()
        return jsonify(assessment_payload(item)), 201

    @app.get("/api/results")
    @login_required
    def api_results():
        item = Assessment.query.filter_by(user_id=session["user_id"]).order_by(Assessment.created_at.desc(), Assessment.id.desc()).first()
        return jsonify(assessment_payload(item) if item else None)

    @app.get("/api/progress")
    @login_required
    def api_progress():
        items = Assessment.query.filter_by(user_id=session["user_id"]).order_by(Assessment.created_at.asc()).all()
        return jsonify([assessment_payload(item) for item in items])

    @app.delete("/api/account")
    @login_required
    def api_delete_account():
        user = current_user()
        db.session.delete(user)
        db.session.commit()
        session.clear()
        return jsonify(message="Account deleted")

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("error.html", code=404, message="The page could not be found."), 404

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
