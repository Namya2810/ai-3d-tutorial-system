from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.orm import relationship
import datetime

try:
    from .database import Base
except ImportError:
    from database import Base

class Subject(Base):
    __tablename__ = "subjects"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    topics = relationship("Topic", back_populates="subject")

class Topic(Base):
    __tablename__ = "topics"
    id = Column(Integer, primary_key=True, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"))
    name = Column(String, index=True)
    subject = relationship("Subject", back_populates="topics")
    subtopics = relationship("Subtopic", back_populates="topic")

class Subtopic(Base):
    __tablename__ = "subtopics"
    id = Column(Integer, primary_key=True, index=True)
    topic_id = Column(Integer, ForeignKey("topics.id"))
    name = Column(String, index=True)
    video_link = Column(String, nullable=True)
    topic = relationship("Topic", back_populates="subtopics")
    questions = relationship("Question", back_populates="subtopic")

class Question(Base):
    __tablename__ = "questions"
    id = Column(Integer, primary_key=True, index=True)
    subtopic_id = Column(Integer, ForeignKey("subtopics.id"))
    difficulty = Column(String)  # "easy", "medium", "hard"
    question = Column(String)
    optionA = Column(String)
    optionB = Column(String)
    optionC = Column(String)
    optionD = Column(String)
    correct_answer = Column(String) # 'A', 'B', 'C', or 'D'
    explanation = Column(String)
    
    subtopic = relationship("Subtopic", back_populates="questions")

class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"
    id = Column(Integer, primary_key=True, index=True)
    subtopic_id = Column(Integer, ForeignKey("subtopics.id"))
    confusion_score = Column(Float)
    score = Column(Integer)
    time_taken = Column(Integer) # in seconds
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
