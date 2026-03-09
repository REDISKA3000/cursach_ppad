from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.db import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(255), unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    resumes = relationship("ResumeGeneration", back_populates="user", cascade="all, delete-orphan")

class Conversation(Base):
    __tablename__ = "conversations"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    status = Column(String(50), default="active")  # active, completed, archived
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")
    resumes = relationship("ResumeGeneration", back_populates="conversation", cascade="all, delete-orphan")

class Message(Base):
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), index=True)
    role = Column(String(50))  # "assistant", "user", "system"
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    conversation = relationship("Conversation", back_populates="messages")

class ResumeGeneration(Base):
    __tablename__ = "resume_generations"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=True)
    title = Column(String(255), default="Generated Resume")
    original_resume_text = Column(Text)
    original_vacancy_text = Column(Text, nullable=True)
    candidate_profile_json = Column(JSON)
    vacancy_profile_json = Column(JSON, nullable=True)
    strategy_brief_json = Column(JSON, nullable=True)
    generated_resume_text = Column(Text)
    technical_report_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", back_populates="resumes")
    conversation = relationship("Conversation", back_populates="resumes")
