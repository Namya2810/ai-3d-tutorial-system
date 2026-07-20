"""
answer_checker.py

Voice se diya gaya jawaab "sahi hai ya nahi" - HYBRID check (Namya ne yahi
decide kiya):
    1. Pehle keyword-matching - fast, free, offline. Zyadatar seedhe
       jawaabon ke liye yahin pe decide ho jaayega.
    2. Keyword match na mile (student ne apne alfaz mein ghuma ke bola) ->
       tabhi Gemini se poochte hain ki concept sahi hai ya nahi.

gemini_ai.py ka wahi client reuse kar rahe hain jo AssistantPanel already
use karta hai - alag API key/setup ki zaroorat nahi.
"""

from gemini_ai import client


def _keyword_check(student_text, expected_keywords, min_matches=1):
    if not student_text or not expected_keywords:
        return False
    text = student_text.lower()
    matches = sum(1 for kw in expected_keywords if kw.lower() in text)
    return matches >= min_matches


def _gemini_check(student_text, prompt, concept_hint):
    judge_prompt = f"""You are grading a student's SPOKEN answer in an educational app.
Be lenient about grammar/phrasing - judge only whether the core idea is correct.

Question asked: {prompt}
Expected concept: {concept_hint}
Student's answer: {student_text}

Reply with exactly one word: YES or NO."""

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=judge_prompt,
        )
        result_text = (response.text or "").strip().upper()
        return result_text.startswith("YES")
    except Exception:
        # Gemini unreachable/rate-limited -> safe default: mark incorrect
        # so the mini-tutorial opens. Better to over-help than to silently
        # pass a wrong answer because the API call failed.
        return False


def check_answer(student_text, task):
    """task: TaskEngine.current_task() dict (must be type == 'voice_question').
    Returns True/False."""
    expected_keywords = task.get("expected_keywords", [])
    min_matches = task.get("min_keyword_matches", 1)

    if _keyword_check(student_text, expected_keywords, min_matches):
        return True

    return _gemini_check(student_text, task["prompt"], task.get("concept_hint", ""))
