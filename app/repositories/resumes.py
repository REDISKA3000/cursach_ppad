"""Resume repository"""
from sqlalchemy.orm import Session
from datetime import datetime
import json
from app.models import ExternalVacancy, JobBoardVacancy, ResumeAdaptation, ResumeGeneration, SourceResume
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


class SourceResumeRepository:
    @staticmethod
    def get_current(db: Session, user_id: int) -> SourceResume:
        """Get the latest source resume for a user."""
        return (
            db.query(SourceResume)
            .filter(SourceResume.user_id == user_id)
            .order_by(SourceResume.updated_at.desc(), SourceResume.created_at.desc())
            .first()
        )

    @staticmethod
    def upsert_current(
        db: Session,
        user_id: int,
        raw_text: str,
        candidate_profile_json: dict,
        file_name: str = None,
    ) -> SourceResume:
        """Create or update user's current source resume."""
        source = SourceResumeRepository.get_current(db, user_id)
        if source:
            source.raw_text = raw_text
            source.candidate_profile_json = candidate_profile_json
            source.file_name = file_name or source.file_name
            source.updated_at = datetime.utcnow()
        else:
            source = SourceResume(
                user_id=user_id,
                file_name=file_name,
                raw_text=raw_text,
                candidate_profile_json=candidate_profile_json,
            )
            db.add(source)

        db.commit()
        db.refresh(source)
        return source


class ResumeAdaptationRepository:
    @staticmethod
    def create(
        db: Session,
        *,
        user_id: int,
        source_resume_id: int,
        title: str,
        vacancy_text: str,
        vacancy_profile_json: dict,
        strategy_brief_json: dict,
        generated_resume_text: str,
        technical_report_json: dict,
        status: str = "completed",
        fit_score: float = None,
        company_name: str = None,
        vacancy_source_type: str = "text",
        vacancy_source_url: str = None,
    ) -> ResumeAdaptation:
        adaptation = ResumeAdaptation(
            user_id=user_id,
            source_resume_id=source_resume_id,
            title=title,
            vacancy_text=vacancy_text,
            vacancy_source_type=vacancy_source_type,
            vacancy_source_url=vacancy_source_url,
            vacancy_profile_json=vacancy_profile_json,
            strategy_brief_json=strategy_brief_json,
            generated_resume_text=generated_resume_text,
            technical_report_json=technical_report_json,
            status=status,
            fit_score=fit_score,
            company_name=company_name,
        )
        db.add(adaptation)
        db.commit()
        db.refresh(adaptation)
        return adaptation

    @staticmethod
    def update_generated(
        db: Session,
        adaptation: ResumeAdaptation,
        *,
        title: str,
        vacancy_profile_json: dict,
        strategy_brief_json: dict,
        generated_resume_text: str,
        technical_report_json: dict,
        status: str = "completed",
        fit_score: float = None,
        company_name: str = None,
    ) -> ResumeAdaptation:
        adaptation.title = title
        adaptation.vacancy_profile_json = vacancy_profile_json
        adaptation.strategy_brief_json = strategy_brief_json
        adaptation.generated_resume_text = generated_resume_text
        adaptation.technical_report_json = technical_report_json
        adaptation.status = status
        adaptation.fit_score = fit_score if fit_score is not None else adaptation.fit_score
        adaptation.company_name = company_name
        adaptation.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(adaptation)
        return adaptation

    @staticmethod
    def get(db: Session, adaptation_id: int) -> ResumeAdaptation:
        return db.query(ResumeAdaptation).filter(ResumeAdaptation.id == adaptation_id).first()

    @staticmethod
    def list_for_user(db: Session, user_id: int) -> list:
        return (
            db.query(ResumeAdaptation)
            .filter(ResumeAdaptation.user_id == user_id)
            .order_by(ResumeAdaptation.created_at.desc())
            .all()
        )


class ExternalVacancyRepository:
    @staticmethod
    def create_or_update(
        db: Session,
        *,
        user_id: int,
        source: str,
        source_url: str,
        title: str,
        company: str = "",
        location: str = "",
        salary: str = "",
        description: str = "",
        normalized_text: str = "",
    ) -> ExternalVacancy:
        vacancy = (
            db.query(ExternalVacancy)
            .filter(
                ExternalVacancy.user_id == user_id,
                ExternalVacancy.source_url == source_url,
            )
            .first()
        )
        if vacancy:
            vacancy.source = source
            vacancy.title = title or vacancy.title
            vacancy.company = company or vacancy.company
            vacancy.location = location or vacancy.location
            vacancy.salary = salary or vacancy.salary
            vacancy.description = description or vacancy.description
            vacancy.normalized_text = normalized_text or vacancy.normalized_text
            vacancy.updated_at = datetime.utcnow()
        else:
            vacancy = ExternalVacancy(
                user_id=user_id,
                source=source,
                source_url=source_url,
                title=title,
                company=company,
                location=location,
                salary=salary,
                description=description,
                normalized_text=normalized_text,
            )
            db.add(vacancy)

        db.commit()
        db.refresh(vacancy)
        return vacancy

    @staticmethod
    def get(db: Session, vacancy_id: int) -> ExternalVacancy:
        return db.query(ExternalVacancy).filter(ExternalVacancy.id == vacancy_id).first()

    @staticmethod
    def list_for_user(db: Session, user_id: int) -> list:
        return (
            db.query(ExternalVacancy)
            .filter(ExternalVacancy.user_id == user_id)
            .order_by(ExternalVacancy.updated_at.desc(), ExternalVacancy.created_at.desc())
            .all()
        )


class JobBoardVacancyRepository:
    @staticmethod
    def upsert_by_url(
        db: Session,
        *,
        source: str,
        source_url: str,
        title: str,
        company: str = "",
        location: str = "",
        salary: str = "",
        description: str = "",
        normalized_text: str = "",
        tags: list[str] = None,
    ) -> JobBoardVacancy:
        vacancy = (
            db.query(JobBoardVacancy)
            .filter(JobBoardVacancy.source_url == source_url)
            .first()
        )
        if vacancy:
            vacancy.source = source or vacancy.source
            vacancy.title = title or vacancy.title
            vacancy.company = company or vacancy.company
            vacancy.location = location or vacancy.location
            vacancy.salary = salary or vacancy.salary
            vacancy.description = description or vacancy.description
            vacancy.normalized_text = normalized_text or vacancy.normalized_text
            vacancy.tags_json = tags or vacancy.tags_json
            vacancy.collected_at = datetime.utcnow()
            vacancy.updated_at = datetime.utcnow()
        else:
            vacancy = JobBoardVacancy(
                source=source,
                source_url=source_url,
                title=title,
                company=company,
                location=location,
                salary=salary,
                description=description,
                normalized_text=normalized_text,
                tags_json=tags or [],
                collected_at=datetime.utcnow(),
            )
            db.add(vacancy)

        db.commit()
        db.refresh(vacancy)
        return vacancy

    @staticmethod
    def get(db: Session, vacancy_id: int) -> JobBoardVacancy:
        return db.query(JobBoardVacancy).filter(JobBoardVacancy.id == vacancy_id).first()

    @staticmethod
    def count(db: Session) -> int:
        return db.query(JobBoardVacancy).count()

    @staticmethod
    def latest_collected_at(db: Session):
        vacancy = (
            db.query(JobBoardVacancy)
            .order_by(JobBoardVacancy.collected_at.desc(), JobBoardVacancy.updated_at.desc())
            .first()
        )
        return vacancy.collected_at if vacancy else None

    @staticmethod
    def list_all(db: Session) -> list:
        return (
            db.query(JobBoardVacancy)
            .order_by(JobBoardVacancy.collected_at.desc(), JobBoardVacancy.updated_at.desc())
            .all()
        )

    @staticmethod
    def delete_known_demo_rows(db: Session) -> int:
        rows = (
            db.query(JobBoardVacancy)
            .filter(
                JobBoardVacancy.source == "getmatch",
                JobBoardVacancy.source_url.like("%34390-one-day-offer-dlia-data-science?s=offers%"),
                JobBoardVacancy.company == "One Day Offer",
            )
            .all()
        )
        count = len(rows)
        for row in rows:
            db.delete(row)
        if count:
            db.commit()
        return count
