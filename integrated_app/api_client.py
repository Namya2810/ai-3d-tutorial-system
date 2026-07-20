"""
api_client.py

Quiz backend (FastAPI, roadmap Phase 8) aur Student Profile backend (Flask,
roadmap Phase 9) alag services ke roop mein chalte hain - is app se sirf
HTTP calls jaate hain. Dono backend ko separately run karna hoga (README
dekho).

Sab functions fail-safe hain: agar backend down ho (abhi test kar rahe ho
bina backend chalaye), exception raise nahi hoga - bas None/empty return
hoga aur error print hoga, taaki poora demo crash na ho.
"""

import requests

QUIZ_API_URL = "http://localhost:8000/api"
PROFILE_API_URL = "http://localhost:5000/api"

TIMEOUT = 5  # seconds


def _get(url):
    try:
        res = requests.get(url, timeout=TIMEOUT)
        res.raise_for_status()
        return res.json()
    except Exception as e:
        print(f"[api_client] GET {url} failed: {e}")
        return None


def _post(url, payload):
    try:
        res = requests.post(url, json=payload, timeout=TIMEOUT)
        res.raise_for_status()
        return res.json()
    except Exception as e:
        print(f"[api_client] POST {url} failed: {e}")
        return None


# ---------------- Quiz backend ----------------

def get_subjects():
    return _get(f"{QUIZ_API_URL}/subjects") or []


def get_topics(subject_id):
    return _get(f"{QUIZ_API_URL}/topics/{subject_id}") or []


def get_subtopics(topic_id):
    return _get(f"{QUIZ_API_URL}/subtopics/{topic_id}") or []


def generate_quiz(subtopic_id, confusion_score_0_to_1):
    """quiz_logic.py confusion_score ko 0-100 scale expect karta hai (dekho
    quiz/backend/quiz_logic.py: >=80, >=60, >=40, >=20 thresholds)."""
    confusion_score_0_to_100 = confusion_score_0_to_1 * 100
    return _post(
        f"{QUIZ_API_URL}/generate-quiz",
        {"subtopic_id": subtopic_id, "confusion_score": confusion_score_0_to_100},
    ) or []


def generate_session_quiz(topic_id, subtopic_sessions):
    """Session khatam hone par ek hi call se poore topic ke saare mini-tuts
    ka quiz banwao. subtopic_sessions: TaskEngine.quiz_session_payload() ka
    output seedha yahan pass karo - [{subtopic_id, play_count,
    confusion_score(0-100)}, ...]. Har subtopic apni khud ki difficulty
    apne confusion_score se leta hai, aur unplayed subtopics floor-of-2
    medium questions pe fallback karte hain (backend side logic)."""
    return _post(
        f"{QUIZ_API_URL}/generate-session-quiz",
        {"topic_id": topic_id, "subtopic_sessions": subtopic_sessions},
    ) or []


def submit_quiz(subtopic_id, confusion_score_0_to_1, score, time_taken_seconds):
    return _post(
        f"{QUIZ_API_URL}/submit-quiz",
        {
            "subtopic_id": subtopic_id,
            "confusion_score": confusion_score_0_to_1 * 100,
            "score": score,
            "time_taken": int(time_taken_seconds),
        },
    )


# ---------------- Student profile backend ----------------

def signup(student_id, password, name):
    return _post(f"{PROFILE_API_URL}/signup", {"student_id": student_id, "password": password, "name": name})


def login(student_id, password):
    return _post(f"{PROFILE_API_URL}/login", {"student_id": student_id, "password": password})


def get_student(student_id):
    return _get(f"{PROFILE_API_URL}/student/{student_id}")


def log_tutorial_watched(student_id, tutorial_name):
    return _post(f"{PROFILE_API_URL}/student/{student_id}/tutorial", {"tutorial_name": tutorial_name})


def log_quiz_score(student_id, quiz_name, score, total):
    return _post(
        f"{PROFILE_API_URL}/student/{student_id}/quiz",
        {"quiz_name": quiz_name, "score": score, "total": total},
    )


def log_topic_strength(student_id, topic, is_weak):
    return _post(f"{PROFILE_API_URL}/student/{student_id}/topic", {"topic": topic, "is_weak": is_weak})


def log_response_time(student_id, seconds):
    return _post(f"{PROFILE_API_URL}/student/{student_id}/response_time", {"seconds": seconds})


def log_confusion_summary(student_id, avg_confusion_0_to_1):
    """Session khatam hone par ek baar: confusion_engine.compute_session_average()
    ka result yahan bhejo, dashboard ke confusion_events mein jud jaayega."""
    return _post(
        f"{PROFILE_API_URL}/student/{student_id}/confusion",
        {"score": avg_confusion_0_to_1},
    )
