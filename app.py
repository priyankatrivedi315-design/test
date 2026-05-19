# =======================
# BUDGET TRACKER (FLASK)
# =======================

from flask import Flask, render_template, request, redirect, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from functools import wraps
import os

# ================= APP =================
app = Flask(__name__)

app.secret_key = "secret123"

# ================= DATABASE CONFIG =================
def build_database_uri():
    return os.getenv("SQLALCHEMY_DATABASE_URI", "sqlite:///budget.db")


app.config["SQLALCHEMY_DATABASE_URI"] = build_database_uri()
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_pre_ping": True
}

db = SQLAlchemy(app)

# ================= DATABASE MODELS =================
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    balance = db.Column(db.Float, default=35000)


class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.String(50))


class Goal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    name = db.Column(db.String(100))
    target = db.Column(db.Float)
    saved = db.Column(db.Float, default=0)
    deadline = db.Column(db.String(50))
    category = db.Column(db.String(50))
    completed = db.Column(db.Boolean, default=False)


class Budget(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    name = db.Column(db.String(100))
    limit = db.Column(db.Float)
    color = db.Column(db.String(20), default="#a855f7")


with app.app_context():
    db.create_all()

# ================= HELPERS =================
def current_user():
    if "user_id" in session:
        return User.query.get(session["user_id"])
    return None


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return redirect("/")
        return f(*args, **kwargs)

    return decorated_function


# ================= AUTH =================
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            session["user_id"] = user.id
            return redirect("/dashboard")

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email")
        password = generate_password_hash(
            request.form.get("password")
        )

        # Check existing user
        existing_user = User.query.filter_by(email=email).first()

        if existing_user:
            return redirect("/register")

        new_user = User(
            email=email,
            password=password
        )

        db.session.add(new_user)
        db.session.commit()

        return redirect("/")

    return render_template("register.html")


@app.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect("/")


# ================= DASHBOARD =================
@app.route("/dashboard", methods=["GET", "POST"])
@login_required
def dashboard():
    user = current_user()

    expenses = Expense.query.filter_by(
        user_id=user.id
    ).all()

    if request.method == "POST":
        title = request.form.get("title")
        amount = float(request.form.get("amount", 0))

        date = datetime.now().strftime("%Y-%m-%d %H:%M")

        # Deduct balance
        user.balance -= amount

        expense = Expense(
            user_id=user.id,
            title=title,
            amount=amount,
            date=date
        )

        db.session.add(expense)
        db.session.commit()

        return redirect("/dashboard")

    total_spent = sum(exp.amount for exp in expenses)

    return render_template(
        "dashboard.html",
        user=user,
        expenses=expenses,
        total_spent=total_spent
    )


# ================= TRANSACTIONS =================
@app.route("/transactions")
@login_required
def transactions():
    user = current_user()

    expenses = Expense.query.filter_by(
        user_id=user.id
    ).all()

    return render_template(
        "transactions.html",
        user=user,
        expenses=expenses
    )


# ================= WALLET =================
@app.route("/wallet")
@login_required
def wallet():
    user = current_user()

    expenses = Expense.query.filter_by(
        user_id=user.id
    ).all()

    return render_template(
        "wallet.html",
        user=user,
        expenses=expenses
    )


# ================= GOALS =================
@app.route("/goals")
@login_required
def goals():
    user = current_user()

    goals = Goal.query.filter_by(
        user_id=user.id
    ).all()

    return render_template(
        "goals.html",
        user=user,
        goals=goals
    )


# ================= BUDGET =================
@app.route("/budget")
@login_required
def budget():
    user = current_user()

    expenses = Expense.query.filter_by(
        user_id=user.id
    ).all()

    budgets = Budget.query.filter_by(
        user_id=user.id
    ).all()

    return render_template(
        "budget.html",
        user=user,
        expenses=expenses,
        budgets=budgets
    )


# ================= ANALYTICS =================
@app.route("/summary")
@login_required
def summary():
    user = current_user()

    expenses = Expense.query.filter_by(
        user_id=user.id
    ).all()

    labels = [expense.title for expense in expenses]
    values = [expense.amount for expense in expenses]

    return render_template(
        "analytics.html",
        user=user,
        labels=labels,
        values=values,
        expenses=expenses
    )


# ================= RUN =================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
