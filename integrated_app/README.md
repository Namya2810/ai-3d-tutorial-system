# AI 3D Tutorial System - Integrated App

Ye folder tumhare 3 modules (VR/3D + face + gesture, Voice, aur naya
confusion engine) ko ek single PyQt6 desktop app mein jodta hai. Quiz aur
Student Profile alag backend services ke roop mein chalte hain - ye app
unko HTTP se call karta hai.

## Architecture

```
main.py
  -> SessionState (session_state.py)        shared "blackboard" - sab modules yahi padhte/likhte hain
  -> MainWindow (ui/app_window.py)
       -> Sidebar                            page switch karta hai
       -> HomePage
       -> Tutorial3DPage                     camera + face_module.py + gesture_sources.py + QWebEngineView (Three.js, tutorial_3d.html)
       -> AssistantPanel (voice/)            speech_to_text + intent_detector + gemini_ai(+groq) + text_to_speech
       -> QuizPage                           api_client.py se Quiz backend (FastAPI) ko call karta hai
       -> ProfilePage                        api_client.py se Profile backend (Flask) ko call karta hai
  -> confusion_engine.py                     har second SessionState padh ke ek score (0-1) nikalta hai
```

`confusion_engine.py` filhaal ek simple weighted formula hai (roadmap ke
hisaab se "pehle Random Forest/rules, deep learning baad mein"). Jab 10-20
students ka real data collect ho jaye, isi jagah trained model daal sakte ho
- `SessionState` se aane wale features same rahenge.

## Setup

### Recommended: preflight + one-command launch

Project root (`ELC`) se:

```bash
python software_preflight.py
python run_all.py
```

`software_preflight.py` Python, all 55 Biology/Chemistry/Physics tasks,
all tutorial videos, 3D/avatar assets, the 336-question quiz database and
runtime packages ko read-only mode mein check karta hai. `run_all.py` profile
dashboard (5000), quiz API (8000) aur desktop app ko ek saath start/stop karta
hai. Hardware is launch ke liye required nahi hai.

Automated flow tests run karne ke liye:

```bash
cd integrated_app
python -m unittest discover -s tests -v
```

Runtime thresholds `runtime_config.json` mein editable hain. Raw BLE glove
packets automatically `integrated_app/data/glove_sessions/glove_*.csv` mein
store hote hain (folder Git se intentionally ignored hai). Glove pointer
drift ho to task screen par `R` press karke recenter karein.

Confusion check-in voice se Yes/No accept karta hai, lekin unreliable audio
par kabhi guess nahi karta. Screen buttons ya `Y`/`N` keys deterministic,
fully-local fallback hain; explicit choice ke bina mini-tutorial force nahi hota.

### 1. Backends alag se chalao (2 alag terminals)

**Quiz backend** (tumhare `quiz/quiz/backend` folder se):
```bash
cd quiz/backend
pip install fastapi uvicorn sqlalchemy pydantic
python seed.py          # ek baar - sample questions daalta hai
uvicorn main:app --reload --port 8000
```

**Student Profile backend** (updated `student_profile_module` folder se -
ye ab Login/Profile ka web frontend bhi serve karta hai, jo desktop app ke
andar embed hoga):
```bash
cd student_profile_module
pip install -r requirements.txt
cp .env.example .env     # optional: hosted MongoDB use karna ho to MONGO_URI do
python app.py             # default port 5000
```
`MONGO_URI` na ho to profile/dashboard automatically local persistent JSON
storage use karta hai, isliye pre-hardware/offline testing blocked nahi hoti.
Ye zaroor chalta hona chahiye is app ke `python main.py` chalane se PEHLE -
warna Profile page mein "connection refused" dikhega (Profile tab pe jaake
reload/dobara click kar sakte ho jab backend up ho jaye).

### 2. Ye integrated desktop app chalao

```bash
cd integrated_app
pip install -r requirements.txt
```

`.env` file banao (VoiceModule wali `.env` se copy kar sakte ho):
```
GEMINI_API_KEY=your_key_here
GROQ_API_KEY=your_key_here     # optional - Gemini fail hone par fallback
```

Phir:
```bash
python main.py
```

## Kya kaam kar raha hai vs abhi manual/placeholder hai

| Piece | Status |
|---|---|
| Face -> SessionState | Live, working (camera, MediaPipe) |
| Gesture -> SessionState | Live, working - **camera se abhi**. Glove hardware (`gesture_sources.py` ka `GloveGestureSource`) ek ready stub hai; hardware aane par isi ke andar BLE code bharna hai, baaki kahin kuch badalna nahi padega |
| 3D viewer engine | **PyOpenGL se Three.js/QWebEngineView pe migrate ho gaya** (`ui/tutorial_3d.html`) - purana `model_viewer.py` black-screen de raha tha, isolated POC mein fix karke yahan laaya gaya. Gesture->rotate/zoom/grab poora validated hai |
| Voice help/repeat -> SessionState + **seedha mini-tutorial khulta hai** | Live, working (`app_window.py._check_voice_triggers`) |
| SessionState -> confusion_engine **live** score | Working (avatar check-in trigger karne ke liye) |
| SessionState -> confusion_engine **session-summary** score (mini-tutorials played included) | Working (Quiz difficulty ke liye - `compute_session_summary`) |
| Main tutorial ko segments + mini-tutorials mein todna | Working **demo version** - abhi time-based auto-advance hai (`segments.json`, `segment_tracker.py`), real video/3D tutorial content aane par real timestamps daalne honge |
| AI Avatar check-in (confusion detect hote hi "clear ho?" poochna) | **Trigger + poora voice conversation real hai** (`voice/avatar_checkin.py`) - sirf 3D avatar ka visual model abhi nahi hai, filhaal koi UI/model nahi dikhta jab wo bolta hai |
| Confusion score -> Quiz difficulty | Working (`generate_quiz` session-summary score pass karta hai) |
| **Segment-weighted quiz questions** (jis segment ka mini-tut chala uske questions zyada) | Nahi bana - Quiz backend (`quiz_logic.py`) ko `segment_tracker.progress_summary()` jaisa data lekar per-subtopic weighting karni hogi. Ye agla backend kaam hai |
| Quiz score -> Student Profile | Working (login ke baad) |
| Profile page | Embedded web page hai (Flask+Mongo), PyQt6 form nahi. Login/Signup/Profile display sab wahi se aata hai |
| `expected_gesture` (wrong-gesture detection) | Abhi hamesha `None` hai - jab tutorial steps define ho, `tutorial_3d_page.py` ke `_on_tick()` mein pass karo |
| Real 3D tutorial content + game-jaisa engaging feel | Abhi sirf ek placeholder `.glb` (beating heart) hai. Real content banne par `segments.json` aur is placeholder ko replace karna hai |
| Video Player / Unity-exported tutorial | Nahi bana - is app ka approach hai live 3D model + gesture, video player nahi |
| Dashboard (teacher view) | Nahi bana |
| Gamified profile/dashboard (Meta/game jaisa) | Nahi bana - abhi plain stats hain |

## Next steps

1. Quiz backend aur Profile backend chala ke, poora flow test karo:
   login -> 3D tutorial dekho/control karo -> voice se help maango -> quiz do -> profile mein score check karo.
2. `confusion_engine.py` ke WEIGHTS ko apne real usage ke hisaab se tune karo.
3. Jab tutorial steps ban jayein, `tutorial_3d_page.py` mein `expected_gesture` pass karna shuru karo taaki wrong-gesture signal bhi accurate ho.
4. Baad mein: `train_emotion_model.py` jaisa ek Random Forest model banao jo `SessionState` ke features (emotion ratio, attention ratio, wrong gestures, help requests, quiz accuracy, response time) leke confusion label predict kare - `confusion_engine.compute()` ke andar isi se replace karo.
