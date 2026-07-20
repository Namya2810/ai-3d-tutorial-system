from pydantic import BaseModel
from typing import List, Optional
import datetime

class SubjectBase(BaseModel):
    name: str

class SubjectOut(SubjectBase):
    id: int
    model_config = {"from_attributes": True}

class TopicBase(BaseModel):
    name: str
    subject_id: int

class TopicOut(TopicBase):
    id: int
    model_config = {"from_attributes": True}

class SubtopicBase(BaseModel):
    name: str
    topic_id: int

class SubtopicOut(SubtopicBase):
    id: int
    model_config = {"from_attributes": True}

class QuestionOut(BaseModel):
    id: int
    difficulty: str
    question: str
    optionA: str
    optionB: str
    optionC: str
    optionD: str
    correct_answer: str
    explanation: Optional[str] = None
    model_config = {"from_attributes": True}

class QuizGenerateRequest(BaseModel):
    subtopic_id: int
    confusion_score: float

class SubtopicSessionInfo(BaseModel):
    subtopic_id: int
    play_count: int = 0
    confusion_score: float = 50.0  # that mini-tut's own live confusion score, not a session average

class SessionQuizGenerateRequest(BaseModel):
    topic_id: int
    subtopic_sessions: List[SubtopicSessionInfo] = []

class SubtopicQuizOut(BaseModel):
    subtopic_id: int
    subtopic_name: str
    questions: List[QuestionOut]

class QuizSubmitRequest(BaseModel):
    subtopic_id: int
    confusion_score: float
    score: int
    time_taken: int

class QuizAttemptOut(QuizSubmitRequest):
    id: int
    created_at: datetime.datetime
    model_config = {"from_attributes": True}
