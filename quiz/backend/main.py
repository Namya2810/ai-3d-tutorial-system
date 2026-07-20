from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List

try:
    from . import models, schemas, quiz_logic
    from .database import engine, get_db
except ImportError:
    import models, schemas, quiz_logic
    from database import engine, get_db

# Create DB tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Quiz Module API")

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
def health(db: Session = Depends(get_db)):
    return {
        "status": "ok",
        "subjects": db.query(models.Subject).count(),
        "questions": db.query(models.Question).count(),
    }

@app.get("/api/subjects", response_model=List[schemas.SubjectOut])
def get_subjects(db: Session = Depends(get_db)):
    subjects = db.query(models.Subject).all()
    return subjects

@app.get("/api/topics/{subject_id}", response_model=List[schemas.TopicOut])
def get_topics(subject_id: int, db: Session = Depends(get_db)):
    topics = db.query(models.Topic).filter(models.Topic.subject_id == subject_id).all()
    return topics

@app.get("/api/subtopics/{topic_id}", response_model=List[schemas.SubtopicOut])
def get_subtopics(topic_id: int, db: Session = Depends(get_db)):
    subtopics = db.query(models.Subtopic).filter(models.Subtopic.topic_id == topic_id).all()
    return subtopics

@app.post("/api/generate-quiz", response_model=List[schemas.QuestionOut])
def generate_quiz(request: schemas.QuizGenerateRequest, db: Session = Depends(get_db)):
    # Verify subtopic exists
    subtopic = db.query(models.Subtopic).filter(models.Subtopic.id == request.subtopic_id).first()
    if not subtopic:
        raise HTTPException(status_code=404, detail="Subtopic not found")
        
    questions = quiz_logic.generate_quiz_questions(db, request.subtopic_id, request.confusion_score)
    if len(questions) < 8:
        # For strict 8 questions requirement, if DB doesn't have enough, we might want to fail
        # or just return whatever we have. Let's return them.
        pass
        
    return questions

@app.post("/api/generate-session-quiz", response_model=List[schemas.SubtopicQuizOut])
def generate_session_quiz(request: schemas.SessionQuizGenerateRequest, db: Session = Depends(get_db)):
    # Verify topic exists
    topic = db.query(models.Topic).filter(models.Topic.id == request.topic_id).first()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    subtopic_sessions = {
        s.subtopic_id: {"play_count": s.play_count, "confusion_score": s.confusion_score}
        for s in request.subtopic_sessions
    }

    return quiz_logic.generate_session_quiz(db, request.topic_id, subtopic_sessions)

@app.post("/api/submit-quiz", response_model=schemas.QuizAttemptOut)
def submit_quiz(request: schemas.QuizSubmitRequest, db: Session = Depends(get_db)):
    db_attempt = models.QuizAttempt(
        subtopic_id=request.subtopic_id,
        confusion_score=request.confusion_score,
        score=request.score,
        time_taken=request.time_taken
    )
    db.add(db_attempt)
    db.commit()
    db.refresh(db_attempt)
    return db_attempt
