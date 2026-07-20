import os
import time
from dotenv import load_dotenv
from google import genai

# Optional: only needed if you want the Groq fallback (see below)
try:
    from groq import Groq
    _groq_available = True
except ImportError:
    _groq_available = False

# Resolve the app's own .env regardless of the terminal launch directory.
VOICE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.dirname(VOICE_DIR)
load_dotenv(os.path.join(APP_DIR, ".env"))

_gemini_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=_gemini_key) if _gemini_key else None

groq_client = None
if _groq_available and os.getenv("GROQ_API_KEY"):
    groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

TUTOR_INSTRUCTIONS = (
    "You are an educational AI tutor. Explain concepts in very simple "
    "language. Keep answers between 5-8 lines.\n\n"
    "IMPORTANT: The student is speaking via voice-to-text, so their input "
    "often won't be phrased as a formal question with a question mark - "
    "it might be a statement like 'I wanted to know about X' or 'tell me "
    "the functions of Y'. Treat any such statement as the actual question "
    "and answer it directly. Do NOT ask the student to repeat or clarify "
    "their question unless the topic itself is genuinely impossible to "
    "identify from what they said."
)


def ask_ai(question):
    """Try Gemini first. If it fails (rate limit, server overload, bad
    key, etc.), automatically fall back to Groq if it's configured.
    """
    gemini_error = None

    # ---- Try Gemini first (optional; app must also start offline) ----
    prompt = f"""
{TUTOR_INSTRUCTIONS}

Student Question:
{question}
"""
    max_attempts = 2  # quick retry, just for transient 503s
    for attempt in range(max_attempts if client is not None else 0):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )
            return response.text
        except Exception as e:
            gemini_error = e
            is_last_attempt = attempt == max_attempts - 1
            if "503" in str(e) and not is_last_attempt:
                time.sleep(2)
                continue
            break  # any other error: stop retrying Gemini, try fallback

    # ---- Gemini failed: fall back to Groq if available ----
    if groq_client is not None:
        try:
            completion = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": TUTOR_INSTRUCTIONS},
                    {"role": "user", "content": question},
                ],
            )
            return completion.choices[0].message.content
        except Exception as groq_error:
            return (
                "Sorry, I couldn't reach the AI service. "
                f"(Gemini: {gemini_error}) (Groq: {groq_error})"
            )

    # ---- No cloud service configured: useful offline response ----
    if client is None and groq_client is None:
        return (
            "The AI service is currently offline. You can continue the 3D lesson, "
            "mini-tutorials and quizzes normally. Add GEMINI_API_KEY to the app's "
            ".env file to enable open-ended tutor answers."
        )
    return f"Sorry, I couldn't reach the AI service. ({gemini_error})"
