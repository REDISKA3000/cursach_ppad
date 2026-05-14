import logging
import os
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.config import UPLOADS_DIR, EXPORTS_DIR
from app.db import get_db
from app.repositories.conversations import ConversationRepository
from app.repositories.resumes import ResumeAdaptationRepository, ResumeRepository, SourceResumeRepository
from app.repositories.users import UserRepository
from app.schemas.candidate import CandidateProfile
from app.schemas.resume import GeneratedResume, TechnicalReport
from app.schemas.strategy import StrategyBrief
from app.schemas.vacancy import VacancyProfile
from app.models import User
from app.services.export_service import ExportService
from app.services.file_parser import FileParser
from app.services.auth_service import get_current_user
from app.services.orchestration import OrchestrationService

logger = logging.getLogger(__name__)
router = APIRouter()
orchestration = OrchestrationService()

_TECHNICAL_WARNING_MARKERS = (
    "badrequest",
    "retryerror",
    "fallback used",
    "exception fallback",
    "profile extracted using hh.ru parsing",
    "profile extracted using section-based parsing",
)


def _get_or_create_demo_context(db: Session) -> tuple[int, int]:
    """Create the demo user and an active conversation when needed."""
    user = UserRepository.get_or_create_demo_user(db)
    conversations = ConversationRepository.get_user_conversations(db, user.id)
    conversation = conversations[0] if conversations else ConversationRepository.create_conversation(db, user.id)
    return user.id, conversation.id


def _sanitize_user_warnings(warnings: list[str]) -> list[str]:
    sanitized = []
    for warning in warnings or []:
        text = str(warning).strip()
        if not text:
            continue
        lowered = text.lower()
        if any(marker in lowered for marker in _TECHNICAL_WARNING_MARKERS):
            continue
        sanitized.append(text)
    return sanitized


def _candidate_profile_payload(profile) -> dict:
    payload = profile.model_dump()
    payload["raw_warnings"] = _sanitize_user_warnings(profile.raw_warnings)
    return payload


def _vacancy_profile_payload(profile) -> dict:
    payload = profile.model_dump()
    payload["raw_warnings"] = _sanitize_user_warnings(profile.raw_warnings)
    return payload


def _user_id_from_conversation(db: Session, conversation_id: Optional[int]) -> Optional[int]:
    if not conversation_id:
        return None
    conversation = ConversationRepository.get_conversation(db, conversation_id)
    return conversation.user_id if conversation else None


def _source_resume_payload(source) -> dict:
    if not source:
        return {}
    profile = CandidateProfile(**(source.candidate_profile_json or {}))
    candidate_payload = _candidate_profile_payload(profile)
    return {
        "id": source.id,
        "user_id": source.user_id,
        "file_name": source.file_name,
        "raw_text": source.raw_text,
        "raw_excerpt": (source.raw_text or "")[:500],
        "candidate_profile": candidate_payload,
        "created_at": source.created_at.isoformat() if source.created_at else "",
        "updated_at": source.updated_at.isoformat() if source.updated_at else "",
        "warnings": candidate_payload["raw_warnings"],
        "questions": orchestration.get_clarifying_questions(profile),
    }


def _adaptation_summary(adaptation) -> str:
    strategy = adaptation.strategy_brief_json or {}
    report = adaptation.technical_report_json or {}
    vacancy = adaptation.vacancy_profile_json or {}
    if strategy.get("recommendations_short"):
        return strategy["recommendations_short"]
    covered = report.get("covered_must_haves") or []
    if covered:
        return f"Покрыты ключевые требования: {', '.join(covered[:3])}"
    if vacancy.get("role"):
        return f"Адаптация под роль: {vacancy['role']}"
    return "Адаптированная версия резюме сохранена."


def _adaptation_payload(adaptation, include_details: bool = False) -> dict:
    payload = {
        "id": adaptation.id,
        "user_id": adaptation.user_id,
        "source_resume_id": adaptation.source_resume_id,
        "title": adaptation.title,
        "summary": _adaptation_summary(adaptation),
        "status": adaptation.status,
        "fit_score": adaptation.fit_score,
        "company_name": adaptation.company_name,
        "created_at": adaptation.created_at.isoformat() if adaptation.created_at else "",
        "updated_at": adaptation.updated_at.isoformat() if adaptation.updated_at else "",
    }
    if include_details:
        payload.update({
            "vacancy_text": adaptation.vacancy_text,
            "vacancy_profile": adaptation.vacancy_profile_json or {},
            "strategy_brief": adaptation.strategy_brief_json or {},
            "generated_resume": {
                "title": adaptation.title,
                "text": adaptation.generated_resume_text,
                "technical_report": adaptation.technical_report_json or {},
            },
            "technical_report": adaptation.technical_report_json or {},
        })
    return payload


def _save_upload_to_text(file: UploadFile, file_content: bytes) -> tuple[str, str]:
    filename = f"{uuid.uuid4()}_{file.filename}"
    file_path = os.path.join(UPLOADS_DIR, filename)
    with open(file_path, "wb") as f:
        f.write(file_content)
    text = FileParser.parse_file(file_path)
    if not text:
        text = file_content.decode("utf-8", errors="ignore")
    return filename, text


def _run_adaptation_pipeline(source, vacancy_text: str) -> tuple[VacancyProfile, StrategyBrief, GeneratedResume]:
    candidate_profile = CandidateProfile(**(source.candidate_profile_json or {}))
    vacancy_profile = orchestration.process_vacancy(vacancy_text)
    strategy_brief = orchestration.build_strategy(candidate_profile, vacancy_profile)
    generated_resume = orchestration.generate_resume(candidate_profile, vacancy_profile, strategy_brief)
    return vacancy_profile, strategy_brief, generated_resume


@router.get("/api/session/bootstrap")
async def bootstrap_session(db: Session = Depends(get_db)):
    """Bootstrap demo user and conversation for the frontend flow."""
    user_id, conversation_id = _get_or_create_demo_context(db)
    return {
        "status": "ok",
        "user_id": user_id,
        "conversation_id": conversation_id,
    }

@router.post("/api/upload-resume")
async def upload_resume(
    file: UploadFile = File(...),
    user_id: int = Form(...),
    conversation_id: int = Form(...),
    db: Session = Depends(get_db)
):
    """Upload and process resume file"""
    try:
        file_content = await file.read()
        filename, resume_text = _save_upload_to_text(file, file_content)
        candidate_profile = orchestration.process_resume(resume_text)
        source_resume = SourceResumeRepository.upsert_current(
            db,
            user_id,
            resume_text,
            candidate_profile.model_dump(),
            file_name=file.filename,
        )
        
        # Save to conversation
        msg = ConversationRepository.add_message(
            db,
            conversation_id,
            "system",
            f"Загружен файл: {file.filename}"
        )
        
        candidate_payload = _candidate_profile_payload(candidate_profile)

        return {
            "status": "ok",
            "source_resume": _source_resume_payload(source_resume),
            "resume_text": resume_text,
            "resume_excerpt": resume_text[:500],
            "candidate_profile": candidate_payload,
            "warnings": candidate_payload["raw_warnings"],
            "questions": orchestration.get_clarifying_questions(candidate_profile)
        }
    except Exception as e:
        logger.error(f"Error uploading resume: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/analyze/resume-text")
async def analyze_resume_text(
    resume_text: str = Form(...),
    conversation_id: int = Form(...),
    user_id: Optional[int] = Form(None),
    db: Session = Depends(get_db)
):
    """Analyze pasted resume text without requiring file upload."""
    try:
        candidate_profile = orchestration.process_resume(resume_text)
        resolved_user_id = user_id or _user_id_from_conversation(db, conversation_id)
        source_resume = None
        if resolved_user_id:
            source_resume = SourceResumeRepository.upsert_current(
                db,
                resolved_user_id,
                resume_text,
                candidate_profile.model_dump(),
                file_name="Текстовое резюме",
            )

        ConversationRepository.add_message(
            db,
            conversation_id,
            "system",
            "Резюме проанализировано из текстового ввода"
        )

        candidate_payload = _candidate_profile_payload(candidate_profile)

        return {
            "status": "ok",
            "source_resume": _source_resume_payload(source_resume) if source_resume else None,
            "resume_text": resume_text,
            "candidate_profile": candidate_payload,
            "warnings": candidate_payload["raw_warnings"],
            "questions": orchestration.get_clarifying_questions(candidate_profile),
        }
    except Exception as e:
        logger.error(f"Error analyzing resume text: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/source-resume")
async def get_source_resume(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get user's current source resume."""
    try:
        source = SourceResumeRepository.get_current(db, current_user.id)
        if not source:
            return {"status": "empty", "source_resume": None}
        return {"status": "ok", "source_resume": _source_resume_payload(source)}
    except Exception as e:
        logger.error(f"Error getting source resume: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/source-resume/upload")
async def upload_source_resume(
    file: UploadFile = File(...),
    conversation_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload/update user's source resume and run CandidateProfile only."""
    try:
        file_content = await file.read()
        filename, resume_text = _save_upload_to_text(file, file_content)
        candidate_profile = orchestration.process_resume(resume_text)
        source = SourceResumeRepository.upsert_current(
            db,
            current_user.id,
            resume_text,
            candidate_profile.model_dump(),
            file_name=file.filename,
        )
        if conversation_id:
            ConversationRepository.add_message(db, conversation_id, "system", f"Обновлено базовое резюме: {file.filename}")
        return {"status": "ok", "source_resume": _source_resume_payload(source)}
    except Exception as e:
        logger.error(f"Error uploading source resume: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/source-resume/text")
async def source_resume_from_text(
    resume_text: str = Form(...),
    conversation_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create/update source resume from pasted text and run CandidateProfile only."""
    try:
        candidate_profile = orchestration.process_resume(resume_text)
        source = SourceResumeRepository.upsert_current(
            db,
            current_user.id,
            resume_text,
            candidate_profile.model_dump(),
            file_name="Текстовое резюме",
        )
        if conversation_id:
            ConversationRepository.add_message(db, conversation_id, "system", "Обновлено базовое резюме из текста")
        return {"status": "ok", "source_resume": _source_resume_payload(source)}
    except Exception as e:
        logger.error(f"Error saving source resume text: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/analyze/preview")
async def analyze_preview(
    resume_text: str = Form(...),
    vacancy_text: str = Form(...),
    conversation_id: int = Form(...),
    db: Session = Depends(get_db)
):
    """Return intermediate profiles and strategy before final resume generation."""
    try:
        candidate_profile = orchestration.process_resume(resume_text)
        vacancy_profile = orchestration.process_vacancy(vacancy_text)
        strategy_brief = orchestration.build_strategy(candidate_profile, vacancy_profile)

        ConversationRepository.add_message(
            db,
            conversation_id,
            "system",
            "Подготовлен промежуточный анализ резюме и вакансии"
        )

        candidate_payload = _candidate_profile_payload(candidate_profile)
        vacancy_payload = _vacancy_profile_payload(vacancy_profile)

        return {
            "status": "ok",
            "candidate_profile": candidate_payload,
            "vacancy_profile": vacancy_payload,
            "strategy_brief": strategy_brief.model_dump(),
            "warnings": {
                "candidate": candidate_payload["raw_warnings"],
                "vacancy": vacancy_payload["raw_warnings"],
            },
            "questions": orchestration.get_clarifying_questions(candidate_profile),
        }
    except Exception as e:
        logger.error(f"Error generating preview: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/generate/full")
async def generate_resume_full(
    user_id: int = Form(...),
    conversation_id: int = Form(...),
    resume_text: str = Form(...),
    vacancy_text: str = Form(...),
    db: Session = Depends(get_db)
):
    """Generate adapted resume"""
    try:
        # Run full orchestration flow
        candidate_profile, vacancy_profile, strategy_brief, generated_resume = orchestration.full_flow(
            resume_text,
            vacancy_text
        )
        
        # Save to database
        resume_gen = ResumeRepository.create_resume_generation(
            db,
            user_id,
            resume_text,
            candidate_profile.model_dump(),
            generated_resume.resume_text,
            conversation_id=conversation_id,
            original_vacancy_text=vacancy_text,
            vacancy_profile_json=vacancy_profile.model_dump(),
            strategy_brief_json=strategy_brief.model_dump(),
            technical_report_json=generated_resume.technical_report.model_dump(),
            title=generated_resume.title
        )
        
        # Update conversation
        ConversationRepository.add_message(
            db,
            conversation_id,
            "system",
            f"Сгенерировано резюме #{resume_gen.id}"
        )
        
        candidate_payload = _candidate_profile_payload(candidate_profile)
        vacancy_payload = _vacancy_profile_payload(vacancy_profile)

        return {
            "status": "ok",
            "resume_id": resume_gen.id,
            "candidate_profile": candidate_payload,
            "vacancy_profile": vacancy_payload,
            "strategy_brief": strategy_brief.model_dump(),
            "generated_resume": {
                "title": generated_resume.title,
                "text": generated_resume.resume_text,
                "technical_report": generated_resume.technical_report.model_dump()
            }
        }
    except Exception as e:
        logger.error(f"Error generating resume: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/adaptations")
async def list_adaptations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List user's source-based resume adaptations."""
    try:
        adaptations = ResumeAdaptationRepository.list_for_user(db, current_user.id)
        return {
            "status": "ok",
            "adaptations": [_adaptation_payload(item) for item in adaptations],
        }
    except Exception as e:
        logger.error(f"Error listing adaptations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/adaptations")
async def create_adaptation(
    vacancy_text: str = Form(""),
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create adaptation from current source resume and vacancy."""
    try:
        source = SourceResumeRepository.get_current(db, current_user.id)
        if not source:
            raise HTTPException(status_code=400, detail="Сначала загрузите базовое резюме")

        if file:
            file_content = await file.read()
            _, parsed_text = _save_upload_to_text(file, file_content)
            vacancy_text = parsed_text or vacancy_text

        if not vacancy_text or not vacancy_text.strip():
            raise HTTPException(status_code=400, detail="Добавьте текст вакансии")

        vacancy_profile, strategy_brief, generated_resume = _run_adaptation_pipeline(source, vacancy_text)
        title = generated_resume.title or vacancy_profile.role or "Адаптированное резюме"
        adaptation = ResumeAdaptationRepository.create(
            db,
            user_id=current_user.id,
            source_resume_id=source.id,
            title=title,
            vacancy_text=vacancy_text,
            vacancy_profile_json=vacancy_profile.model_dump(),
            strategy_brief_json=strategy_brief.model_dump(),
            generated_resume_text=generated_resume.resume_text,
            technical_report_json=generated_resume.technical_report.model_dump(),
            fit_score=strategy_brief.fit_score,
        )
        return {"status": "ok", "adaptation": _adaptation_payload(adaptation, include_details=True)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating adaptation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/adaptations/{adaptation_id}")
async def get_adaptation(
    adaptation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get one source-based adaptation."""
    try:
        adaptation = ResumeAdaptationRepository.get(db, adaptation_id)
        if not adaptation:
            raise HTTPException(status_code=404, detail="Adaptation not found")
        if adaptation.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Adaptation not found")
        return {"status": "ok", "adaptation": _adaptation_payload(adaptation, include_details=True)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting adaptation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/adaptations/{adaptation_id}/regenerate")
async def regenerate_adaptation(
    adaptation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Regenerate adaptation from its stored source resume."""
    try:
        adaptation = ResumeAdaptationRepository.get(db, adaptation_id)
        if not adaptation:
            raise HTTPException(status_code=404, detail="Adaptation not found")
        if adaptation.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Adaptation not found")
        source = adaptation.source_resume
        if not source:
            raise HTTPException(status_code=400, detail="Source resume not found")

        vacancy_profile, strategy_brief, generated_resume = _run_adaptation_pipeline(source, adaptation.vacancy_text)
        updated = ResumeAdaptationRepository.update_generated(
            db,
            adaptation,
            title=generated_resume.title or vacancy_profile.role or adaptation.title,
            vacancy_profile_json=vacancy_profile.model_dump(),
            strategy_brief_json=strategy_brief.model_dump(),
            generated_resume_text=generated_resume.resume_text,
            technical_report_json=generated_resume.technical_report.model_dump(),
            fit_score=strategy_brief.fit_score,
        )
        return {"status": "ok", "adaptation": _adaptation_payload(updated, include_details=True)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error regenerating adaptation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/adaptations/{adaptation_id}/download/pdf")
async def download_adaptation_pdf(
    adaptation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download source-based adaptation as PDF."""
    try:
        adaptation = ResumeAdaptationRepository.get(db, adaptation_id)
        if not adaptation:
            raise HTTPException(status_code=404, detail="Adaptation not found")
        if adaptation.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Adaptation not found")

        tech_report = TechnicalReport(**(adaptation.technical_report_json or {}))
        generated = GeneratedResume(
            title=adaptation.title,
            resume_text=adaptation.generated_resume_text,
            technical_report=tech_report,
        )
        pdf_bytes = ExportService.export_pdf(generated)
        filename = f"adaptation_{adaptation_id}.pdf"
        file_path = os.path.join(EXPORTS_DIR, filename)
        with open(file_path, "wb") as f:
            f.write(pdf_bytes)
        adaptation.export_pdf_path = file_path
        db.commit()
        return FileResponse(file_path, media_type="application/pdf", filename=filename)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading adaptation PDF: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/resumes")
async def list_resumes(user_id: int, db: Session = Depends(get_db)):
    """List user's resumes"""
    try:
        resumes = ResumeRepository.get_user_resumes(db, user_id)
        resume_data = []
        for r in resumes:
            resume_data.append({
                "id": r.id,
                "title": r.title,
                "created_at": r.created_at.isoformat() if r.created_at else "",
                "updated_at": r.updated_at.isoformat() if r.updated_at else ""
            })
        return {"resumes": resume_data}
    except Exception as e:
        logger.error(f"Error listing resumes: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/resumes/{resume_id}")
async def get_resume(resume_id: int, db: Session = Depends(get_db)):
    """Get specific resume"""
    try:
        resume = ResumeRepository.get_resume_generation(db, resume_id)
        if not resume:
            raise HTTPException(status_code=404, detail="Resume not found")
        
        return {
            "id": resume.id,
            "title": resume.title,
            "resume_text": resume.generated_resume_text,
            "candidate_profile": resume.candidate_profile_json,
            "vacancy_profile": resume.vacancy_profile_json,
            "strategy_brief": resume.strategy_brief_json,
            "technical_report": resume.technical_report_json,
            "created_at": resume.created_at.isoformat() if resume.created_at else ""
        }
    except Exception as e:
        logger.error(f"Error getting resume: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/resumes/{resume_id}/download/txt")
async def download_resume_txt(resume_id: int, db: Session = Depends(get_db)):
    """Download resume as TXT"""
    try:
        resume = ResumeRepository.get_resume_generation(db, resume_id)
        if not resume:
            raise HTTPException(status_code=404, detail="Resume not found")
        
        # Create file
        filename = f"resume_{resume_id}.txt"
        file_path = os.path.join(EXPORTS_DIR, filename)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(resume.generated_resume_text)
        
        return FileResponse(file_path, media_type="text/plain", filename=filename)
    except Exception as e:
        logger.error(f"Error downloading TXT: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/resumes/{resume_id}/download/pdf")
async def download_resume_pdf(resume_id: int, db: Session = Depends(get_db)):
    """Download resume as PDF"""
    try:
        resume = ResumeRepository.get_resume_generation(db, resume_id)
        if not resume:
            raise HTTPException(status_code=404, detail="Resume not found")
        
        # Generate PDF
        from app.schemas.resume import GeneratedResume, TechnicalReport
        
        tech_report = TechnicalReport(**resume.technical_report_json) if resume.technical_report_json else TechnicalReport()
        generated = GeneratedResume(
            title=resume.title,
            resume_text=resume.generated_resume_text,
            technical_report=tech_report
        )
        
        pdf_bytes = ExportService.export_pdf(generated)
        
        # Save to file
        filename = f"resume_{resume_id}.pdf"
        file_path = os.path.join(EXPORTS_DIR, filename)
        
        with open(file_path, 'wb') as f:
            f.write(pdf_bytes)
        
        return FileResponse(file_path, media_type="application/pdf", filename=filename)
    except Exception as e:
        logger.error(f"Error downloading PDF: {e}")
        raise HTTPException(status_code=500, detail=str(e))
@router.get("/api/model-info")
async def get_model_info():
    """Get information about current LLM model"""
    from app.services.llm_provider import get_llm_provider
    from app.config import OPENAI_API_KEY, OPENAI_MODEL
    
    provider = get_llm_provider()
    
    return {
        "provider": provider.name,
        "model": OPENAI_MODEL,
        "enabled": provider.enabled,
        "status": "",
        "api_key_present": bool(OPENAI_API_KEY),
    }
