import random
from sqlalchemy.orm import Session

try:
    import models
except ImportError:
    from . import models

def get_difficulty_distribution(confusion_score: float):
    """
    Returns a dictionary with the required number of easy, medium, and hard questions.
    Confusion 80-100: 6 Easy, 2 Medium
    Confusion 60-79: 4 Easy, 3 Medium, 1 Hard
    Confusion 40-59: 2 Easy, 4 Medium, 2 Hard
    Confusion 20-39: 1 Easy, 3 Medium, 4 Hard
    Confusion 0-19: 2 Medium, 6 Hard
    """
    if confusion_score >= 80:
        return {"easy": 6, "medium": 2, "hard": 0}
    elif confusion_score >= 60:
        return {"easy": 4, "medium": 3, "hard": 1}
    elif confusion_score >= 40:
        return {"easy": 2, "medium": 4, "hard": 2}
    elif confusion_score >= 20:
        return {"easy": 1, "medium": 3, "hard": 4}
    else:
        return {"easy": 0, "medium": 2, "hard": 6}

# --- Session-wide quiz (all mini-tuts of a topic, weighted by replay + per-tut confusion) ---

# ASSUMPTIONS (tune here once real student data comes in, no logic changes needed):
# - A mini-tutorial that was never opened this session still gets a small baseline quiz,
#   all at medium difficulty (no confusion signal exists for it yet).
MIN_QUESTIONS_PER_SUBTOPIC = 2

# Same easy/medium/hard *ratios* as get_difficulty_distribution, just expressed as fractions
# of 8 so they can be rescaled to any question count (not just 8).
_DIFFICULTY_RATIO_BANDS = [
    (80, {"easy": 6 / 8, "medium": 2 / 8, "hard": 0 / 8}),
    (60, {"easy": 4 / 8, "medium": 3 / 8, "hard": 1 / 8}),
    (40, {"easy": 2 / 8, "medium": 4 / 8, "hard": 2 / 8}),
    (20, {"easy": 1 / 8, "medium": 3 / 8, "hard": 4 / 8}),
    (0,  {"easy": 0 / 8, "medium": 2 / 8, "hard": 6 / 8}),
]


def _scale_distribution(confusion_score: float, count: int):
    """Scales the easy/medium/hard ratio for a given confusion score down/up to sum exactly
    to `count`, using largest-remainder rounding so nothing is lost/duplicated."""
    ratios = next(r for floor, r in _DIFFICULTY_RATIO_BANDS if confusion_score >= floor)
    raw = {k: v * count for k, v in ratios.items()}
    floored = {k: int(v) for k, v in raw.items()}
    remainder = count - sum(floored.values())
    # hand out leftover slots to whichever buckets had the largest fractional remainder
    order = sorted(raw, key=lambda k: raw[k] - floored[k], reverse=True)
    for k in order[:remainder]:
        floored[k] += 1
    return floored


def generate_session_quiz(db: Session, topic_id: int, subtopic_sessions: dict):
    """
    Builds one quiz spanning every mini-tutorial under `topic_id`.

    subtopic_sessions: {subtopic_id: {"play_count": int, "confusion_score": float}}
    Any subtopic under the topic that is missing from this dict is treated as unplayed
    (play_count=0), per requirement: default 1-2 medium questions for every mini-tut.

    Returns: list of {"subtopic_id", "subtopic_name", "questions": [...]}
    """
    subtopics = db.query(models.Subtopic).filter(models.Subtopic.topic_id == topic_id).all()

    result = []
    for subtopic in subtopics:
        session_info = subtopic_sessions.get(subtopic.id, {})
        play_count = session_info.get("play_count", 0)

        if play_count <= 0:
            # Not opened this session -> baseline, medium-only, no confusion signal to lean on
            distribution = {"easy": 0, "medium": MIN_QUESTIONS_PER_SUBTOPIC, "hard": 0}
        else:
            count = max(MIN_QUESTIONS_PER_SUBTOPIC, play_count)
            confusion_score = session_info.get("confusion_score", 50.0)
            distribution = _scale_distribution(confusion_score, count)

        quiz_questions = []
        for difficulty, needed in distribution.items():
            if needed == 0:
                continue
            pool = db.query(models.Question).filter(
                models.Question.subtopic_id == subtopic.id,
                models.Question.difficulty == difficulty,
            ).all()
            quiz_questions.extend(random.sample(pool, min(len(pool), needed)))

        random.shuffle(quiz_questions)
        result.append({
            "subtopic_id": subtopic.id,
            "subtopic_name": subtopic.name,
            "questions": quiz_questions,
        })

    return result


def generate_quiz_questions(db: Session, subtopic_id: int, confusion_score: float):
    distribution = get_difficulty_distribution(confusion_score)
    
    quiz_questions = []
    for difficulty, count in distribution.items():
        if count == 0:
            continue
        
        # Fetch all questions for this subtopic and difficulty
        questions = db.query(models.Question).filter(
            models.Question.subtopic_id == subtopic_id,
            models.Question.difficulty == difficulty
        ).all()
        
        # If there are not enough questions in DB, just take what's available
        # In a real app we'd handle fallback or ensure DB is sufficiently seeded
        sampled = random.sample(questions, min(len(questions), count))
        quiz_questions.extend(sampled)
        
    # Shuffle the final 8 questions
    random.shuffle(quiz_questions)
    return quiz_questions
