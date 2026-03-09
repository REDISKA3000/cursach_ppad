"""Resume generation API routes"""
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session
import json
import os
from typing import Optional
from app.db import get_db
from app.repositories.users import UserRepository
from app.repositories.conversations import ConversationRepository
from app.repositories.resumes import ResumeRepository
from app.services.orchestration import OrchestrationService
from app.services.file_parser import FileParser
from app.services.export_service import ExportService
from app.config import UPLOADS_DIR, EXPORTS_DIR
import logging
import uuid

logger = logging.getLogger(__name__)
router = APIRouter()
orchestration = OrchestrationService()

@router.post("/api/upload-resume")
async def upload_resume(
    file: UploadFile = File(...),
    user_id: int = Form(...),
    conversation_id: int = Form(...),
    db: Session = Depends(get_db)
):
    """Upload and process resume file"""
    try:
        # Save uploaded file
        file_content = await file.read()
        filename = f"{uuid.uuid4()}_{file.filename}"
        file_path = os.path.join(UPLOADS_DIR, filename)
        
        with open(file_path, 'wb') as f:
            f.write(file_content)
        
        # Parse file
        resume_text = FileParser.parse_file(file_path)
        
        if not resume_text:
            resume_text = file_content.decode('utf-8', errors='ignore')
        
        # Process resume through agent
        candidate_profile = orchestration.process_resume(resume_text)
        
        # Save to conversation
        msg = ConversationRepository.add_message(
            db,
            conversation_id,
            "system",
            f"Загружен файл: {file.filename}"
        )
        
        return {
            "status": "ok",
            "resume_text": resume_text[:500],  # Return snippet
            "candidate_profile": candidate_profile.model_dump(),
            "warnings": candidate_profile.raw_warnings,
            "questions": orchestration.get_clarifying_questions(candidate_profile)
        }
    except Exception as e:
        logger.error(f"Error uploading resume: {e}")
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
        
        return {
            "status": "ok",
            "resume_id": resume_gen.id,
            "candidate_profile": candidate_profile.model_dump(),
            "vacancy_profile": vacancy_profile.model_dump(),
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
        "status": f"🟢 OpenAI ({OPENAI_MODEL})" if provider.enabled else "🟡 Mock LLM (fallback)",
        "api_key_present": bool(OPENAI_API_KEY),
    }