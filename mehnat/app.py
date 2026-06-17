from flask import Flask, render_template, request, redirect, session
import sqlite3
from datetime import datetime, timedelta
import random

app = Flask(__name__)
app.secret_key = "mehnat_secret_key"

USERS = {
    "rohan": "mehnat123",
    "ansh": "mehnat123",
    "praveen": "mehnat123"
}

QUOTES = [
    "Josh Meter High Rakho 🚀",
    "Padhna Hai, Phodna Hai 💥",
    "Keher Machani Hai ⚡",
    "Aag Lagani Hai 🔥",
    "Aaj Kaam, Kal Naam 🏆"
]


def get_db():
    conn = sqlite3.connect("mehnat.db")
    conn.row_factory = sqlite3.Row
    return conn


def mehnat_day():
    now = datetime.now()

    if now.hour < 3 or (now.hour == 3 and now.minute < 30):
        return (now - timedelta(days=1)).strftime("%Y-%m-%d")

    return now.strftime("%Y-%m-%d")


def init_db():
    conn = get_db()

    conn.execute("""
    CREATE TABLE IF NOT EXISTS users(
        username TEXT PRIMARY KEY,
        total_points INTEGER DEFAULT 0
    )
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS goals(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        goal TEXT,
        completed INTEGER DEFAULT 0,
        day TEXT
    )
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS screen_time(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        minutes INTEGER,
        day TEXT
    )
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS processed_days(
        day TEXT PRIMARY KEY
    )
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS daily_scores(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        day TEXT,
        raw_points INTEGER,
        final_points INTEGER
    )
    """)

    for user in USERS:
        conn.execute(
            """
            INSERT OR IGNORE INTO users
            (username,total_points)
            VALUES (?,?)
            """,
            (user, 0)
        )

    conn.commit()
    conn.close()


def process_day(day):

    conn = get_db()

    already = conn.execute(
        """
        SELECT *
        FROM processed_days
        WHERE day=?
        """,
        (day,)
    ).fetchone()

    if already:
        conn.close()
        return

    users = conn.execute(
        "SELECT username FROM users"
    ).fetchall()

    for user in users:

        username = user["username"]

        goals = conn.execute(
            """
            SELECT *
            FROM goals
            WHERE username=?
            AND day=?
            """,
            (username, day)
        ).fetchall()

        if not goals:
            continue

        completed = sum(
            1 for g in goals
            if g["completed"] == 1
        )

        raw_points = completed * 20

        all_complete = all(
            g["completed"] == 1
            for g in goals
        )

        if all_complete:
            final_points = raw_points
        else:
            final_points = raw_points // 2

        conn.execute(
            """
            INSERT INTO daily_scores
            (username,day,raw_points,final_points)
            VALUES(?,?,?,?)
            """,
            (
                username,
                day,
                raw_points,
                final_points
            )
        )

        conn.execute(
            """
            UPDATE users
            SET total_points =
            total_points + ?
            WHERE username=?
            """,
            (
                final_points,
                username
            )
        )

    screen_times = conn.execute(
        """
        SELECT username, minutes
        FROM screen_time
        WHERE day=?
        """,
        (day,)
    ).fetchall()

    if screen_times:

        lowest = min(
            row["minutes"]
            for row in screen_times
        )

        winners = [
            row["username"]
            for row in screen_times
            if row["minutes"] == lowest
        ]

        for winner in winners:

            conn.execute(
                """
                UPDATE users
                SET total_points =
                total_points + 50
                WHERE username=?
                """,
                (winner,)
            )

    conn.execute(
        """
        INSERT INTO processed_days(day)
        VALUES(?)
        """,
        (day,)
    )

    conn.commit()
    conn.close()


def process_previous_day():

    yesterday = (
        datetime.now() - timedelta(days=1)
    ).strftime("%Y-%m-%d")

    process_day(yesterday)


@app.route("/")
def home():

    if "user" in session:
        return redirect("/dashboard")

    return render_template("login.html")


@app.route("/login", methods=["POST"])
def login():

    username = request.form["username"].lower()
    password = request.form["password"]

    if username in USERS and USERS[username] == password:

        session["user"] = username

        return redirect("/dashboard")

    return redirect("/")


@app.route("/logout")
def logout():

    session.clear()

    return redirect("/")


@app.route("/dashboard")
def dashboard():

    process_previous_day()

    if "user" not in session:
        return redirect("/")

    user = session["user"]

    conn = get_db()

    goals = conn.execute(
        """
        SELECT *
        FROM goals
        WHERE username=?
        AND day=?
        """,
        (user, mehnat_day())
    ).fetchall()

    leaderboard = conn.execute(
        """
        SELECT *
        FROM users
        ORDER BY total_points DESC
        """
    ).fetchall()

    total = conn.execute(
        """
        SELECT total_points
        FROM users
        WHERE username=?
        """,
        (user,)
    ).fetchone()

    completed = len(
        [g for g in goals if g["completed"] == 1]
    )

    pending = len(goals) - completed

    raw_points = completed * 20

    conn.close()

    return render_template(
        "dashboard.html",
        user=user,
        goals=goals,
        leaderboard=leaderboard,
        total_points=total["total_points"],
        completed=completed,
        pending=pending,
        raw_points=raw_points,
        quote=random.choice(QUOTES)
    )


@app.route("/add_goal", methods=["POST"])
def add_goal():

    if "user" not in session:
        return redirect("/")

    goal = request.form["goal"]

    conn = get_db()

    conn.execute(
        """
        INSERT INTO goals
        (username,goal,day)
        VALUES(?,?,?)
        """,
        (
            session["user"],
            goal,
            mehnat_day()
        )
    )

    conn.commit()
    conn.close()

    return redirect("/dashboard")


@app.route("/complete/<int:goal_id>")
def complete(goal_id):

    if "user" not in session:
        return redirect("/")

    conn = get_db()

    conn.execute(
        """
        UPDATE goals
        SET completed=1
        WHERE id=?
        """,
        (goal_id,)
    )

    conn.commit()
    conn.close()

    return redirect("/dashboard")


@app.route("/screen_time", methods=["POST"])
def screen_time():

    if "user" not in session:
        return redirect("/")

    hours = int(request.form["hours"])
    minutes = int(request.form["minutes"])

    total_minutes = (hours * 60) + minutes

    conn = get_db()

    conn.execute(
        """
        INSERT INTO screen_time
        (username,minutes,day)
        VALUES(?,?,?)
        """,
        (
            session["user"],
            total_minutes,
            mehnat_day()
        )
    )

    conn.commit()
    conn.close()

    return redirect("/dashboard")


@app.route("/weekly")
def weekly():

    if "user" not in session:
        return redirect("/")

    return render_template("weekly.html")

import os

init_db()

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000))
    )
