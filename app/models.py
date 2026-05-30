from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, Float
from sqlalchemy.orm import relationship
from app.db import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(255), unique=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=True)
    password_hash = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    resumes = relationship("ResumeGeneration", back_populates="user", cascade="all, delete-orphan")
    source_resumes = relationship("SourceResume", back_populates="user", cascade="all, delete-orphan")
    adaptations = relationship("ResumeAdaptation", back_populates="user", cascade="all, delete-orphan")
    external_vacancies = relationship("ExternalVacancy", back_populates="user", cascade="all, delete-orphan")

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


class SourceResume(Base):
    __tablename__ = "source_resumes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    file_name = Column(String(255), nullable=True)
    raw_text = Column(Text)
    candidate_profile_json = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="source_resumes")
    adaptations = relationship("ResumeAdaptation", back_populates="source_resume", cascade="all, delete-orphan")


class ResumeAdaptation(Base):
    __tablename__ = "resume_adaptations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    source_resume_id = Column(Integer, ForeignKey("source_resumes.id"), index=True)
    title = Column(String(255), default="Adapted Resume")
    vacancy_text = Column(Text)
    vacancy_source_type = Column(String(50), default="text")
    vacancy_source_url = Column(String(1000), nullable=True)
    vacancy_profile_json = Column(JSON, nullable=True)
    strategy_brief_json = Column(JSON, nullable=True)
    generated_resume_text = Column(Text)
    technical_report_json = Column(JSON, nullable=True)
    status = Column(String(50), default="completed")
    fit_score = Column(Float, nullable=True)
    company_name = Column(String(255), nullable=True)
    export_pdf_path = Column(String(500), nullable=True)
    export_docx_path = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="adaptations")
    source_resume = relationship("SourceResume", back_populates="adaptations")


class ExternalVacancy(Base):
    __tablename__ = "external_vacancies"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    source = Column(String(80), index=True)
    source_url = Column(String(1000), nullable=True)
    title = Column(String(500), default="")
    company = Column(String(255), default="")
    location = Column(String(255), default="")
    salary = Column(String(255), nullable=True)
    description = Column(Text)
    normalized_text = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="external_vacancies")


class JobBoardVacancy(Base):
    __tablename__ = "job_board_vacancies"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String(80), index=True)
    source_url = Column(String(1000), nullable=True, index=True)
    title = Column(String(500), default="")
    company = Column(String(255), default="")
    location = Column(String(255), default="")
    salary = Column(String(255), nullable=True)
    description = Column(Text)
    normalized_text = Column(Text)
    tags_json = Column(JSON, nullable=True)
    collected_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
