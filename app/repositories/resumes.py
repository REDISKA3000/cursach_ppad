"""Resume repository"""
from sqlalchemy.orm import Session
from datetime import datetime
import json
from app.models import ResumeGeneration
import logging

logger = logging.getLogger(__name__)

class ResumeRepository:
    @staticmethod
    def create_resume_generation(
        db: Session,
        user_id: int,
        original_resume_text: str,
        candidate_profile_json: dict,
        generated_resume_text: str,
        conversation_id: int = None,
        original_vacancy_text: str = None,
        vacancy_profile_json: dict = None,
        strategy_brief_json: dict = None,
        technical_report_json: dict = None,
        title: str = "Generated Resume"
    ) -> ResumeGeneration:
        """Create new resume generation record"""
        resume_gen = ResumeGeneration(
            user_id=user_id,
            conversation_id=conversation_id,
            title=title,
            original_resume_text=original_resume_text,
            original_vacancy_text=original_vacancy_text,
            candidate_profile_json=candidate_profile_json,
            vacancy_profile_json=vacancy_profile_json,
            strategy_brief_json=strategy_brief_json,
            generated_resume_text=generated_resume_text,
            technical_report_json=technical_report_json
        )
        db.add(resume_gen)
        db.commit()
        db.refresh(resume_gen)
        return resume_gen
    
    @staticmethod
    def get_resume_generation(db: Session, resume_id: int) -> ResumeGeneration:
        """Get resume generation by ID"""
        return db.query(ResumeGeneration).filter(ResumeGeneration.id == resume_id).first()
    
    @staticmethod
    def get_user_resumes(db: Session, user_id: int) -> list:
        """Get all resume generations for user"""
        return db.query(ResumeGeneration).filter(ResumeGeneration.user_id == user_id).order_by(ResumeGeneration.created_at.desc()).all()
    
    @staticmethod
    def get_conversation_resume(db: Session, conversation_id: int) -> ResumeGeneration:
        """Get resume generation for conversation"""
        return db.query(ResumeGeneration).filter(ResumeGeneration.conversation_id == conversation_id).first()
    
    @staticmethod
    def delete_resume_generation(db: Session, resume_id: int):
        """Delete resume generation"""
        resume_gen = ResumeRepository.get_resume_generation(db, resume_id)
        if resume_gen:
            db.delete(resume_gen)
            db.commit()
