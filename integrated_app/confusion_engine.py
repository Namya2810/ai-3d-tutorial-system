"""
confusion_engine.py  (Phase 6 - roadmap ka missing link)

CHANGE (roadmap correction, no other signals): confusion score ab SIRF
emotion detection (face module) aur pulse rate (glove hardware) se banta
hai - wrong_gesture/help_requests/quiz_wrong/slow_response ab isme NAHI
jaate. Wo signals abhi bhi SessionState mein maujood hain, lekin unka kaam
ab "mini-tutorial kab kholna hai" decide karna hai (task_engine.py dekho),
confusion SCORE ka input nahi hain.

V1 = simple weighted rule-based formula (roadmap ne bhi bola tha "initially
deep learning mat use karo, simple rules se shuru karo"). Jab tumhare paas
10-20 students ka real glove+face data collect ho jaye, tab isi formula ki
jagah train_emotion_model.py jaisa model drop-in replace kar sakte ho -
SessionState se aane wale features same rahenge, sirf compute() ke andar
ka logic badlega.
"""

from dataclasses import dataclass
from app_config import setting


# Sirf do signal - dono "emotion detection + pulse rate" ke andar aate hain.
# Pulse abhi glove hardware na hone ki wajah se None ho sakta hai - us case
# mein emotion_weight 1.0 pe renormalize ho jaata hai (neeche compute() mein).
WEIGHTS = {
    "emotion": float(setting("confusion", "emotion_weight")),
    "pulse": float(setting("confusion", "pulse_weight")),
}


@dataclass
class ConfusionResult:
    score: float                 # 0.0 - 1.0
    label: str                   # "confused" | "attentive" | "neutral"
    breakdown: dict              # debugging ke liye - kis signal ne kitna contribute kiya


def _clamp01(x):
    return max(0.0, min(1.0, x))


def _label_for(score):
    if score >= float(setting("confusion", "confused_min")):
        return "confused"
    elif score <= float(setting("confusion", "attentive_max")):
        return "attentive"
    return "neutral"


def compute(session_state) -> ConfusionResult:
    """session_state: SessionState instance. Isi ke live emotion + pulse
    values se score banta hai - baaki sab signals (gesture/help/quiz/timing)
    yahan IGNORE hote hain, wo sirf mini-tut trigger conditions hain."""

    # Face module se: negative emotion aur non-attentive dono "emotion
    # detection" ka hissa hain, isliye average karke ek hi emotion-signal
    # banaya hai.
    emotion_signal = (
        session_state.recent_negative_emotion_ratio
        + session_state.recent_non_attentive_ratio
    ) / 2.0

    pulse_signal = session_state.pulse_stress_ratio  # None agar glove connected nahi

    if pulse_signal is None:
        # Glove abhi tak nahi laga - emotion-only fallback, weight 1.0 pe renormalize
        breakdown = {"emotion": emotion_signal}
        score = _clamp01(emotion_signal)
    else:
        breakdown = {
            "emotion": emotion_signal * WEIGHTS["emotion"],
            "pulse": pulse_signal * WEIGHTS["pulse"],
        }
        score = _clamp01(sum(breakdown.values()))

    session_state.record_live_score(score)
    if session_state.current_task_id:
        session_state.record_task_confusion(session_state.current_task_id, score)

    return ConfusionResult(score=score, label=_label_for(score), breakdown=breakdown)


# ------------------------------------------------------------------
# Session-end summary - SIRF dashboard ke liye ("last mein ek average
# confusion score to store in dashboard"). Quiz ki difficulty ab isse
# NAHI aati - wo har mini-tut ke apne task_confusion_score() se aati hai
# (dekho quiz_logic.generate_session_quiz + session_state.task_confusion_score).
# ------------------------------------------------------------------

def compute_session_average(session_state) -> ConfusionResult:
    """Session khatam hone par ek baar call karo, dashboard pe bhejne ke liye
    (api_client.log_confusion_summary). Simple average of every live tick
    recorded this session."""
    score = session_state.avg_live_score
    return ConfusionResult(score=score, label=_label_for(score), breakdown={"avg_live_score": score})
