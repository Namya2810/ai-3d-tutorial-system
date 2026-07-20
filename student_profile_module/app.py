import os
import json
import threading
from pathlib import Path
from flask import Flask, request, jsonify, render_template
try:
    from pymongo import MongoClient
except ImportError:  # Local/offline mode does not require pymongo.
    MongoClient = None
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()  # loads variables from a local .env file during development

app = Flask(__name__)

MONGO_URI = os.environ.get("MONGO_URI")


class LocalStudentCollection:
    """Small persistent Mongo-like adapter for a single-laptop demo.

    It intentionally supports only the operators used by this API. Setting
    MONGO_URI switches the same routes to MongoDB without changing the UI.
    """

    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()

    def _load(self):
        if not self.path.exists():
            return []
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []

    def _save(self, rows):
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(rows, indent=2, default=str), encoding="utf-8")
        temporary.replace(self.path)

    def find_one(self, query):
        with self.lock:
            return next((dict(row) for row in self._load()
                         if all(row.get(k) == v for k, v in query.items())), None)

    def insert_one(self, doc):
        with self.lock:
            rows = self._load()
            saved = dict(doc)
            saved.setdefault("_id", saved.get("student_id"))
            rows.append(saved)
            self._save(rows)
            doc["_id"] = saved["_id"]

    def update_one(self, query, update):
        with self.lock:
            rows = self._load()
            for row in rows:
                if not all(row.get(k) == v for k, v in query.items()):
                    continue
                for key, value in update.get("$set", {}).items():
                    row[key] = value
                for key, value in update.get("$addToSet", {}).items():
                    values = row.setdefault(key, [])
                    if value not in values:
                        values.append(value)
                for key, value in update.get("$push", {}).items():
                    row.setdefault(key, []).append(value)
                break
            self._save(rows)


if MONGO_URI and MongoClient:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
    db = client["elc_tutorial_system"]
    students_collection = db["student_profiles"]
    STORAGE_MODE = "mongodb"
else:
    students_collection = LocalStudentCollection(
        Path(__file__).resolve().parent / "data" / "student_profiles.json"
    )
    STORAGE_MODE = "local-json"


def new_student_document(student_id, name, password_hash):
    return {
        "student_id": student_id,
        "name": name,
        "password_hash": password_hash,
        "tutorials_watched": [],
        "weak_topics": [],
        "strong_topics": [],
        "quiz_scores": [],
        "response_times": [],
        "confusion_events": [],
        "created_at": datetime.utcnow(),
        "last_active": datetime.utcnow(),
    }


def public_view(doc):
    doc = dict(doc)
    doc["_id"] = str(doc.get("_id", doc.get("student_id", "")))
    doc.pop("password_hash", None)
    return doc


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "storage": STORAGE_MODE})


@app.route("/api/signup", methods=["POST"])
def signup():
    data = request.json or {}
    student_id = (data.get("student_id") or "").strip()
    password = data.get("password") or ""
    name = data.get("name", "Student")

    if not student_id or not password:
        return jsonify({"error": "Student ID and password are required"}), 400

    if students_collection.find_one({"student_id": student_id}):
        return jsonify({"error": "This Student ID already has an account"}), 409

    doc = new_student_document(student_id, name, generate_password_hash(password))
    students_collection.insert_one(doc)
    return jsonify(public_view(doc))


@app.route("/api/login", methods=["POST"])
def login():
    data = request.json or {}
    student_id = (data.get("student_id") or "").strip()
    password = data.get("password") or ""

    student = students_collection.find_one({"student_id": student_id})
    if not student or not check_password_hash(student["password_hash"], password):
        return jsonify({"error": "Invalid Student ID or password"}), 401

    students_collection.update_one(
        {"student_id": student_id}, {"$set": {"last_active": datetime.utcnow()}}
    )
    return jsonify(public_view(student))


@app.route("/api/student/<student_id>", methods=["GET"])
def get_student(student_id):
    student = students_collection.find_one({"student_id": student_id})
    if not student:
        return jsonify({"error": "Student not found"}), 404
    return jsonify(public_view(student))


@app.route("/api/student/<student_id>/tutorial", methods=["POST"])
def add_tutorial_watched(student_id):
    data = request.json
    tutorial_name = data.get("tutorial_name")
    students_collection.update_one(
        {"student_id": student_id},
        {"$addToSet": {"tutorials_watched": tutorial_name}, "$set": {"last_active": datetime.utcnow()}},
    )
    return jsonify({"status": "ok"})


@app.route("/api/student/<student_id>/quiz", methods=["POST"])
def add_quiz_score(student_id):
    data = request.json
    quiz_entry = {
        "quiz": data.get("quiz_name"),
        "score": data.get("score"),
        "total": data.get("total"),
        "timestamp": datetime.utcnow().isoformat(),
    }
    students_collection.update_one(
        {"student_id": student_id},
        {"$push": {"quiz_scores": quiz_entry}, "$set": {"last_active": datetime.utcnow()}},
    )
    return jsonify({"status": "ok"})


@app.route("/api/student/<student_id>/topic", methods=["POST"])
def update_topic_strength(student_id):
    data = request.json
    topic = data.get("topic")
    is_weak = data.get("is_weak", True)
    field = "weak_topics" if is_weak else "strong_topics"
    students_collection.update_one(
        {"student_id": student_id},
        {"$addToSet": {field: topic}, "$set": {"last_active": datetime.utcnow()}},
    )
    return jsonify({"status": "ok"})


@app.route("/api/student/<student_id>/response_time", methods=["POST"])
def add_response_time(student_id):
    data = request.json
    seconds = data.get("seconds")
    students_collection.update_one(
        {"student_id": student_id}, {"$push": {"response_times": seconds}}
    )
    return jsonify({"status": "ok"})


@app.route("/api/student/<student_id>/confusion", methods=["POST"])
def add_confusion_event(student_id):
    """Session-end average confusion score (confusion_engine.compute_session_average),
    dashboard ke confusion_events list mein jama hota hai taaki teacher dashboard
    class-wide confusion patterns dikha sake."""
    data = request.json or {}
    score = data.get("score")
    if score is None:
        return jsonify({"error": "score is required"}), 400

    event = {"score": score, "timestamp": datetime.utcnow().isoformat()}
    students_collection.update_one(
        {"student_id": student_id},
        {"$push": {"confusion_events": event}, "$set": {"last_active": datetime.utcnow()}},
    )
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
